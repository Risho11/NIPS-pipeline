"""Round evidence, plain Markdown reports, and small recovery checkpoints."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path

from mas_analysis import build_figures

# These are outputs of the adapter, not new measurements on the next invocation.
REPORT_COLUMNS = ("initial_report", "final_report", "LLM_suggestion", "mas_report_path")


def write_atomic(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames or [], list(reader)


def csv_text(fields, rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def observation_inputs(llm_path, warm_start, condition_name, initial, constraints):
    """Read precise evidence, excluding adapter-owned report columns from llm.csv."""
    inputs = {}
    for name in ("llm", "agg", "reps"):
        path = llm_path if name == "llm" else llm_path.parent / f"{name}.csv"
        if not path.exists():
            if name == "llm" and not initial:
                raise ValueError(f"Missing campaign observations: {path}")
            continue
        fields, rows = read_csv(path)
        if name == "llm":
            names = [row.get("name") for row in rows]
            if not initial and (names.count(condition_name) != 1 or names[-1] != condition_name):
                raise ValueError("The next experiment requires one exact latest promoted condition")
            if initial and rows:
                raise ValueError("Campaign already has observations; resume instead of initializing")
            if len(set(names)) != len(names):
                raise ValueError("Duplicate promoted condition identities in llm.csv")
            fields = [key for key in fields if key not in REPORT_COLUMNS]
            rows = [{key: row.get(key, "") for key in fields} for row in rows]
        inputs[f"{name}.csv"] = csv_text(fields, rows)
    if warm_start is not None:
        fields, rows = read_csv(warm_start)
        if not rows or "name" not in fields:
            raise ValueError("Warm-start history needs named observation rows")
        inputs["warm_start.csv"] = csv_text(fields, rows)
    inputs["context.json"] = json.dumps({
        "source_condition": condition_name, "initial": initial, "constraints": constraints,
        "source_paths": {"llm": str(llm_path), "warm_start": str(warm_start) if warm_start else None},
    }, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return inputs


class RoundRecords:
    """Own the evidence and accepted artifacts for one condition's reasoning round.

    Checkpoints contain fields needed to resume, while report prose is read as a
    whole Markdown file. No Markdown syntax is used as a machine data format.
    """
    def __init__(self, llm_path, condition_name, warm_start, initial, constraints):
        self.llm_path = Path(llm_path).resolve()
        self.condition_name, self.warm_start = condition_name, warm_start
        self.initial, self.constraints = initial, constraints
        self.inputs = observation_inputs(self.llm_path, warm_start, condition_name, initial, constraints)
        fingerprint = hashlib.sha256(json.dumps(self.inputs, sort_keys=True).encode()).hexdigest()
        self.root = self.llm_path.parent / "mas"
        self.round_id = hashlib.sha256(("initial" if initial else condition_name).encode()).hexdigest()[:20]
        self.directory = self.root / "rounds" / self.round_id
        self.state_path = self.root / "state.json"
        self.state = (json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists()
                      else {"thread_id": None, "rounds": {}})
        self.record = self.state["rounds"].setdefault(self.round_id, {
            "fingerprint": fingerprint, "previous_round": self.state.get("last_round"), "stages": {},
        })
        if self.record["fingerprint"] != fingerprint:
            raise ValueError("Round inputs or constraints changed; inspect before starting a new round")
        for name, content in self.inputs.items():
            path = self.directory / "inputs" / name
            if path.exists() and path.read_bytes() != content.encode("utf-8"):
                raise ValueError(f"Frozen evidence changed: {path}")
            if not path.exists():
                write_atomic(path, content)
        if "figures" not in self.record:
            evidence = self.directory / "inputs/llm.csv"
            if not evidence.exists():
                evidence = self.directory / "inputs/warm_start.csv"
            if evidence.exists():
                figures = build_figures(evidence, self.directory / "figures")
            else:
                figures = []
                (self.directory / "figures").mkdir(parents=True, exist_ok=True)
            self.record["figures"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                      for path in figures}
        self.check_evidence()
        self.save_state()

    def save_state(self):
        write_atomic(self.state_path, json.dumps(self.state, ensure_ascii=False, indent=2, allow_nan=False))

    def check_evidence(self):
        if observation_inputs(self.llm_path, self.warm_start, self.condition_name,
                              self.initial, self.constraints) != self.inputs:
            raise ValueError("Experimental evidence changed during the round")
        for name, content in self.inputs.items():
            if (self.directory / "inputs" / name).read_bytes() != content.encode("utf-8"):
                raise ValueError("Frozen evidence changed during the round")
        for name, expected in self.record["figures"].items():
            if hashlib.sha256((self.directory / "figures" / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Accepted evidence figure changed")

    def prompt_context(self):
        previous = self.record.get("previous_round")
        previous_report = "none; initialize from observations"
        if previous:
            previous_report = str(self.root / "rounds" / previous / "hypotheses.md")
        return (
            f"Read frozen inputs: {self.directory / 'inputs'}\n"
            f"Inspect figures/tables: {self.directory / 'figures'}\n"
            f"Accepted reports in this round: {self.directory}\n"
            f"Accepted structured fields and thread IDs: {self.state_path}\n"
            f"Previous accepted hypotheses: {previous_report}\n"
        )

    def load_report(self, name, model):
        checkpoint = self.record["stages"].get(name)
        if checkpoint is None:
            return None
        if not isinstance(checkpoint, dict):
            raise ValueError("Retired prototype checkpoint; archive it before starting a new campaign")
        path = self.directory / f"{name}.md"
        content = path.read_bytes()
        fields = json.dumps(checkpoint["fields"], sort_keys=True, allow_nan=False).encode("utf-8")
        if hashlib.sha256(fields + b"\n" + content).hexdigest() != checkpoint["sha256"]:
            raise ValueError(f"Saved report changed after acceptance: {path}")
        return model.model_validate({**checkpoint["fields"], "report": content.decode("utf-8")})

    def save_report(self, name, report, review=None):
        self.check_evidence()
        prose = report.report
        if review is not None:
            prose += (f"\n\n## Independent QA\n\nVerdict: {review.verdict.upper()}. "
                      f"Author: `{report.author_thread_id}`; reviewer: `{report.reviewer_thread_id}`.\n")
            for finding in review.findings:
                prose += f"\n- {finding}\n"
        if name == "hypotheses":
            prose += (f"\n\n## Main selection\n\n{report.selected_hypothesis_id or 'None'}: "
                      f"{report.selection_reason}\n")
        write_atomic(self.directory / f"{name}.md", prose)
        fields = report.model_dump(mode="json", exclude={"report"})
        fields_json = json.dumps(fields, sort_keys=True, allow_nan=False).encode("utf-8")
        self.record["stages"][name] = {
            "sha256": hashlib.sha256(fields_json + b"\n" + prose.encode("utf-8")).hexdigest(),
            "fields": fields,
        }
        self.save_state()
        # Subsequent requests see exactly the same report on a fresh run or resume.
        return report.model_copy(update={"report": prose})

    def export_decision(self, analysis, decision):
        self.check_evidence()
        if not self.initial:
            fields, rows = read_csv(self.llm_path)
            matches = [row for row in rows if row.get("name") == self.condition_name]
            if len(matches) != 1:
                raise ValueError("Cannot attach MAS reports without one exact condition row")
            for key in REPORT_COLUMNS:
                if key not in fields:
                    fields.append(key)
            row = matches[0]
            row["initial_report"] = row["final_report"] = analysis.report
            row["LLM_suggestion"] = decision.model_dump_json()
            row["mas_report_path"] = str(self.directory / "decision.md")
            write_atomic(self.llm_path, csv_text(fields, rows))
        self.state["last_round"] = self.round_id
        self.record["action"] = decision.action
        self.save_state()
