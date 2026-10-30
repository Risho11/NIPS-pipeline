"""One Codex main thread: analysis -> hypotheses -> design -> final decision."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import threading

from mas_records import RoundRecords
from mas_schema import (AnalysisReport, ExperimentDecision, ExperimentDesign,
                        HypothesisUpdate, MaterialContext, validate_conditions, validate_review)

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRE_CODEX_MODES = {"dynamic"}
DEFAULT_OBJECTIVE = (
    "Improve reproducible elastic modulus and compression-estimated pore fraction "
    "within feasible conditions and acceptable membrane quality. Describe Pareto "
    "tradeoffs without inventing a weighted sum; use experiments to test hypotheses."
)
_LOCK = threading.Lock()


def _sdk():
    from openai_codex import Codex, CodexConfig
    return Codex(CodexConfig(cwd=str(REPO_ROOT), codex_bin=os.environ.get("NIPS_CODEX_BIN")))


def _open_thread(codex, records):
    from openai_codex import ApprovalMode, Sandbox
    options = dict(cwd=str(REPO_ROOT), sandbox=Sandbox.read_only,
                   approval_mode=ApprovalMode.deny_all,
                   developer_instructions=(REPO_ROOT / "docs/mas/workflow.md").read_text(encoding="utf-8"))
    thread_id = records.state["thread_id"]
    if thread_id:
        thread = codex.thread_resume(thread_id, **options)
    else:
        thread = codex.thread_start(ephemeral=False, **options)
    records.state["thread_id"] = thread.id
    records.save_state()
    return thread


def _request_reviewed_report(thread, records, stage, model, author, reviewer):
    """Request an author and independent reviewer, then verify their native results."""
    schema = model.model_json_schema()
    # Operational IDs and main's selection are added by main, not authored by the specialist.
    author_schema = model.model_json_schema()
    for key in ("author_thread_id", "reviewer_thread_id", "selected_hypothesis_id", "selection_reason"):
        if key in author_schema["properties"]:
            del author_schema["properties"][key]
            author_schema["required"].remove(key)
    prompt = (
        f"Perform only {stage}. Read docs/mas/data-contract.md.\n{records.prompt_context()}"
        f"Explicitly delegate to fresh {author}, then distinct fresh {reviewer}; "
        "read their role AGENTS.md and wait for completion. Author returns ONLY JSON matching: "
        f"{json.dumps(author_schema)}\n"
        "Reviewer returns ONLY JSON with verdict, exact reviewed_content (complete author JSON), "
        "and findings. Follow the revision limit in workflow.md. Return the accepted author fields "
        "unchanged, add actual author_thread_id/reviewer_thread_id, and close completed agents. "
        "For hypotheses, after QA you as main choose a non-refuted selected_hypothesis_id "
        "(or null) and explain selection_reason. Do not edit files or contact devices/services."
    )
    result = thread.run(prompt, output_schema=schema)
    if getattr(result.status, "value", result.status) != "completed":
        raise RuntimeError(f"Codex {stage} turn did not complete")
    report = model.model_validate_json(result.final_response)
    review = validate_review(result, report, thread.id)
    used_threads = {checkpoint["fields"][key]
                    for checkpoint in records.record["stages"].values()
                    for key in ("author_thread_id", "reviewer_thread_id")
                    if key in checkpoint["fields"]}
    if used_threads.intersection({report.author_thread_id, report.reviewer_thread_id}):
        raise ValueError("Each stage requires fresh author and QA threads")
    return report, review


def analyze_experiments(thread, records) -> AnalysisReport:
    """Observe measurements and graphs; save only after analysis QA passes."""
    cached = records.load_report("analysis", AnalysisReport)
    if cached is not None:
        return cached
    report, review = _request_reviewed_report(
        thread, records, "analysis", AnalysisReport, "experiment-analyst", "experiment-analysis-qa",
    )
    return records.save_report("analysis", report, review)


def update_hypotheses(thread, records) -> HypothesisUpdate:
    """Update the reviewed list, then let main select the next hypothesis."""
    cached = records.load_report("hypotheses", HypothesisUpdate)
    if cached is not None:
        return cached
    report, review = _request_reviewed_report(
        thread, records, "hypotheses", HypothesisUpdate, "hypothesis-updater", "hypothesis-qa",
    )
    return records.save_report("hypotheses", report, review)


def design_experiment(thread, records, hypotheses, bounds) -> ExperimentDesign:
    """Test the selected hypothesis with feasible, independently reviewed conditions."""
    design = records.load_report("experiment_design", ExperimentDesign)
    review = None
    if design is None:
        design, review = _request_reviewed_report(
            thread, records, "experiment_design", ExperimentDesign,
            "experiment-designer", "experiment-design-qa",
        )
    if design.experiment is not None:
        if design.experiment.hypothesis_id != hypotheses.selected_hypothesis_id:
            raise ValueError("Design does not test the selected hypothesis")
        validate_conditions(design.experiment.next_params.model_dump(), bounds,
                            records.constraints["materials"], records.constraints["locked_additive_wt"])
    if review is not None:
        return records.save_report("experiment_design", design, review)
    return design


def make_decision(thread, records, design, bounds) -> ExperimentDecision:
    """Main adopts the exact reviewed design or records hold/stop without conditions."""
    decision = records.load_report("decision", ExperimentDecision)
    if decision is None:
        prompt = (
            f"Perform only the final decision.\n{records.prompt_context()}"
            "Decide run, hold, or stop yourself. Run adopts exactly the reviewed experiment.next_params; "
            "hold/stop uses null. Explain the reason and uncertainty, reference the three accepted "
            "reports, and do not claim a global optimum. Do not execute experiments or edit files."
        )
        result = thread.run(prompt, output_schema=ExperimentDecision.model_json_schema())
        if getattr(result.status, "value", result.status) != "completed":
            raise RuntimeError("Codex decision turn did not complete")
        decision = ExperimentDecision.model_validate_json(result.final_response)
    if decision.action == "run":
        if design.experiment is None or decision.next_params != design.experiment.next_params:
            raise ValueError("Final execution conditions differ from the QA-reviewed design")
        validate_conditions(decision.next_params.model_dump(), bounds,
                            records.constraints["materials"], records.constraints["locked_additive_wt"])
    if "decision" not in records.record["stages"]:
        return records.save_report("decision", decision)
    return decision


def generate_reports_and_suggestion(
    condition_name, agg_llm_path, activeLearning, locked_additive_wt=None,
    al_search_mode="dynamic", exploration_history_points=None, warm_start_csv=None,
    material_context=None, *, initial=False, codex_factory=None, objective=DEFAULT_OBJECTIVE,
):
    """Run four visible operations; return the existing pipeline's decision dictionary.

    Model and robot calls are replaced by test doubles during development validation.
    Existing OpenRouter modes never enter this adapter. One process owns a campaign.
    """
    if al_search_mode not in REQUIRE_CODEX_MODES:
        raise ValueError(f"Not a Codex mode: {al_search_mode}")
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("A dynamic round is already running")
    try:
        materials = MaterialContext.model_validate(material_context)
        records = RoundRecords(Path(agg_llm_path), condition_name, warm_start_csv, initial, {
            "materials": materials.model_dump(), "locked_additive_wt": locked_additive_wt,
            "objective": objective, "stock_metadata": activeLearning.bounds.send_metadata(),
            "ranges": activeLearning.current_ranges(locked_additive_wt=locked_additive_wt),
        })
        pending = not all(name in records.record["stages"]
                          for name in ("analysis", "hypotheses", "experiment_design", "decision"))
        with ((codex_factory or _sdk)() if pending else nullcontext()) as codex:
            thread = _open_thread(codex, records) if pending else None

            analysis = analyze_experiments(thread, records)
            hypotheses = update_hypotheses(thread, records)
            design = design_experiment(thread, records, hypotheses, activeLearning.bounds)
            decision = make_decision(thread, records, design, activeLearning.bounds)

        records.export_decision(analysis, decision)
        params = decision.next_params
        return {
            "action": decision.action, "reason": decision.reason,
            "next_params": {**params.model_dump(), **materials.model_dump()} if params is not None else None,
            "report_path": str(records.directory / "decision.md"),
        }
    finally:
        _LOCK.release()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate MAS reports only; never submit a robot run")
    parser.add_argument("--llm-csv", type=Path, required=True)
    parser.add_argument("--condition")
    parser.add_argument("--warm-start", type=Path)
    parser.add_argument("--material-context", type=Path, required=True,
                        help="JSON with five operator material/bath fields; see data-contract.md")
    parser.add_argument("--locked-additive-wt", type=float)
    parser.add_argument("--initial", action="store_true")
    args = parser.parse_args()
    if not args.initial and not args.condition:
        parser.error("--condition is required unless --initial is set")
    import activeLearning_29 as al
    result = generate_reports_and_suggestion(
        args.condition, args.llm_csv, al, locked_additive_wt=args.locked_additive_wt,
        warm_start_csv=args.warm_start, initial=args.initial,
        material_context=json.loads(args.material_context.read_text(encoding="utf-8")),
    )
    print(json.dumps(result, indent=2))
