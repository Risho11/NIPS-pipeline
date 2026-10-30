"""Offline MAS protocol tests: mocked SDK, temporary evidence, no model/device calls."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/pipeline"))
import codex_context as adapter
import polymer_additive_bounds as bounds
from mas_records import read_csv, csv_text
from mas_schema import (AnalysisReport, ExperimentDecision, ExperimentDesign, ExperimentParameters,
                        HypothesisUpdate, MaterialContext, validate_conditions, validate_review)

MATERIALS = {"polymer_type": "Polysulfone", "solvent_type": "PolarClean",
             "cosolvent_type": "none", "nips_bath_solvent": "PolarClean",
             "nips_bath_solvent_wt_percent": 10.0}
PARAMS = {"mixing_temp": 25, "bath_temp": 5, "pullcast_speed": 10, "nitrogen": True,
          "coupon_to_bath_wait_time": 30, "nips_bath_wait_time": 1200,
          "polymer_wt": 17, "additive_wt": 0}
AL = NS(bounds=bounds, current_ranges=lambda **kw: "Use the declared laboratory ranges")


def native_result(stage, payload, mutate_review=None):
    authored = {key: value for key, value in payload.items() if key not in {
        "author_thread_id", "reviewer_thread_id", "selected_hypothesis_id", "selection_reason",
    }}
    review = {"verdict": "pass", "reviewed_content": copy.deepcopy(authored), "findings": []}
    if mutate_review:
        mutate_review(review)
    states = {
        payload["author_thread_id"]: NS(status="completed", message=json.dumps(authored)),
        payload["reviewer_thread_id"]: NS(status="completed", message=json.dumps(review)),
    }
    return NS(status="completed", final_response=json.dumps(payload),
              items=[NS(root=NS(type="collabAgentToolCall", agents_states=states))])


class FakeCodex:
    """Exercises the real adapter, filesystem, schemas and native-event QA gate."""
    def __init__(self, action="run", break_stage=None, mutate=None):
        self.action, self.break_stage, self.mutate = action, break_stage, mutate
        self.id = "main-thread"
        self.calls = []
        self.started = 0
        self.resumed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def thread_start(self, **kwargs):
        self.started += 1
        self.options = kwargs
        return self

    def thread_resume(self, thread_id, **kwargs):
        self.resumed.append(thread_id)
        return self

    def run(self, prompt, output_schema):
        if "action" in output_schema["properties"]:
            stage = "decision"
        else:
            keys = output_schema["properties"]
            stage = "hypotheses" if "hypotheses" in keys else "experiment_design" if "experiment" in keys else "analysis"
        self.calls.append(stage)
        if stage == self.break_stage:
            raise RuntimeError("interrupted SDK turn")
        if stage == "decision":
            payload = {"report": "Adopt the reviewed test; uncertainty remains.", "reason": "Discriminate H1",
                       "action": self.action, "next_params": PARAMS if self.action == "run" else None}
            if self.mutate:
                self.mutate(stage, payload)
            return NS(status="completed", final_response=json.dumps(payload), items=[])
        content = {"report": f"Accepted {stage} report. Evidence: inputs/llm.csv; QA: no blocking findings."}
        if stage == "hypotheses":
            content["hypotheses"] = [{"id": "H1", "statement": "Bath temperature changes modulus",
                                      "status": "proposed", "evidence": ["condition-A"]}]
        if stage == "experiment_design":
            content["experiment"] = {
                "hypothesis_id": "H1", "purpose": "explore", "prediction": "Modulus will increase",
                "comparator": "condition-A", "criteria": "Support if independent repeat contrast exceeds variation",
                "next_params": copy.deepcopy(PARAMS),
            }
        payload = {**content, "author_thread_id": stage + "-author",
                   "reviewer_thread_id": stage + "-reviewer"}
        if stage == "hypotheses":
            payload.update(selected_hypothesis_id="H1", selection_reason="Largest unresolved contrast")
        if self.mutate:
            self.mutate(stage, payload)
        return native_result(stage, payload)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.csv = self.root / "llm.csv"
        self.csv.write_text("name,Elastic Modulus Mean,Elastic Modulus SD,Changepoint Mean,final_report\n"
                            "condition-A,123.123456789,2,0.4,old prose\n")
        (self.root / "agg.csv").write_text("name,value\ncondition-A_postDiscard,123.123456789\n")
        (self.root / "reps.csv").write_text("name,Trial,value\ncondition-A,1,123.123456789\n")
        self.sdk = FakeCodex()

    def tearDown(self):
        self.tmp.cleanup()

    def generate(self, **kwargs):
        options = dict(material_context=MATERIALS, locked_additive_wt=0,
                       codex_factory=lambda: self.sdk)
        options.update(kwargs)
        return adapter.generate_reports_and_suggestion("condition-A", self.csv, AL, **options)

    def test_four_reports_csv_link_and_unchanged_measurements(self):
        measured = {name: (self.root / name).read_bytes() for name in ("reps.csv", "agg.csv")}
        decision = self.generate()
        self.assertEqual(decision["next_params"], {**PARAMS, **MATERIALS})
        self.assertEqual(self.sdk.calls, ["analysis", "hypotheses", "experiment_design", "decision"])
        self.assertEqual(self.sdk.started, 1)
        self.assertEqual(self.sdk.options["sandbox"].value, "read-only")
        report = Path(decision["report_path"])
        self.assertEqual({p.name for p in report.parent.glob("*.md")}, {"analysis.md", "hypotheses.md", "experiment_design.md", "decision.md"})
        self.assertFalse(list(report.parent.glob("result.json")))
        self.assertTrue((report.parent / "figures/trajectory.png").exists())
        self.assertTrue((report.parent / "figures/trajectory.csv").exists())
        with self.csv.open(newline="") as f:
            row = next(csv.DictReader(f))
        self.assertEqual(row["Elastic Modulus Mean"], "123.123456789")
        self.assertEqual(row["mas_report_path"], str(report))
        self.assertEqual(json.loads(row["LLM_suggestion"])["action"], "run")
        for name, data in measured.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_completed_round_reexports_without_sdk_or_duplicate_report_prose(self):
        first = self.generate()
        with patch.object(adapter, "_sdk", side_effect=AssertionError("no SDK allowed")):
            second = self.generate(codex_factory=Mock(side_effect=AssertionError("no SDK allowed")))
        self.assertEqual(first, second)
        analysis = Path(first["report_path"]).with_name("analysis.md").read_text()
        self.assertEqual(analysis.count("Accepted analysis report."), 1)

    def test_plain_markdown_roundtrip_and_checkpoint_contains_no_report_prose(self):
        prose = "# Observations\n\nA paragraph.\n\n<!-- mas-handoff is ordinary report text -->\n\n## Limits\n\nUnknown."
        def mutate(stage, payload):
            if stage == "analysis":
                payload["report"] = prose
        self.sdk.mutate = mutate
        result = self.generate()
        analysis_path = Path(result["report_path"]).with_name("analysis.md")
        self.assertTrue(analysis_path.read_text().startswith(prose))
        self.assertEqual(self.generate(codex_factory=Mock(side_effect=AssertionError("no SDK"))), result)
        state = json.loads((self.root / "mas/state.json").read_text())
        self.assertNotIn(prose, json.dumps(state))
        for record in state["rounds"].values():
            for stage in record["stages"].values():
                self.assertNotIn("report", stage["fields"])

    def test_changed_checkpoint_conditions_cannot_reuse_an_accepted_report(self):
        self.generate()
        path = self.root / "mas/state.json"
        state = json.loads(path.read_text())
        record = next(iter(state["rounds"].values()))
        record["stages"]["decision"]["fields"]["next_params"]["bath_temp"] = 10
        path.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, "changed after acceptance"):
            self.generate()

    def test_interruption_resumes_same_thread_and_only_missing_stages(self):
        self.sdk.break_stage = "experiment_design"
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            self.generate()
        self.sdk.break_stage = None
        self.sdk.calls.clear()
        self.generate()
        self.assertEqual(self.sdk.resumed, ["main-thread"])
        self.assertEqual(self.sdk.calls, ["experiment_design", "decision"])

    def test_hold_and_stop_survive_restart_without_execution_params(self):
        for action in ("hold", "stop"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "llm.csv"
                path.write_bytes(self.csv.read_bytes())
                sdk = FakeCodex(action)
                result = adapter.generate_reports_and_suggestion("condition-A", path, AL,
                    material_context=MATERIALS, locked_additive_wt=0, codex_factory=lambda: sdk)
                self.assertEqual((result["action"], result["next_params"]), (action, None))
                result2 = adapter.generate_reports_and_suggestion("condition-A", path, AL,
                    material_context=MATERIALS, locked_additive_wt=0,
                    codex_factory=Mock(side_effect=AssertionError("no SDK")))
                self.assertEqual(result, result2)

    def test_changed_observation_or_constraint_rejects_cached_decision(self):
        self.generate()
        with self.assertRaisesRegex(ValueError, "inputs or constraints changed"):
            self.generate(locked_additive_wt=1)
        self.csv.write_text(self.csv.read_text().replace("123.123456789", "999"))
        with self.assertRaisesRegex(ValueError, "inputs or constraints changed"):
            self.generate()

    def test_tampered_accepted_report_rejected(self):
        result = self.generate()
        Path(result["report_path"]).with_name("analysis.md").write_text("altered")
        with self.assertRaisesRegex(ValueError, "changed after acceptance"):
            self.generate()

    def test_tampered_evidence_figure_rejected(self):
        result = self.generate()
        (Path(result["report_path"]).parent / "figures/trajectory.csv").write_text("altered")
        with self.assertRaisesRegex(ValueError, "evidence figure changed"):
            self.generate()

    def test_evidence_changed_during_turn_is_not_accepted(self):
        def mutate(stage, payload):
            if stage == "analysis":
                self.csv.write_text(self.csv.read_text().replace("123.123456789", "999"))
        self.sdk.mutate = mutate
        with self.assertRaisesRegex(ValueError, "evidence changed during"):
            self.generate()
        self.assertFalse(list(self.root.glob("mas/rounds/*/analysis.md")))

    def test_frozen_evidence_changed_during_turn_is_not_accepted(self):
        def mutate(stage, payload):
            if stage == "analysis":
                path = next(self.root.glob("mas/rounds/*/inputs/llm.csv"))
                path.write_text(path.read_text().replace("123.123456789", "999"))
        self.sdk.mutate = mutate
        with self.assertRaisesRegex(ValueError, "Frozen evidence changed during"):
            self.generate()
        self.assertFalse(list(self.root.glob("mas/rounds/*/analysis.md")))

    def test_null_selection_and_design_can_resume_to_hold_or_stop(self):
        def no_test(stage, payload):
            if stage == "hypotheses":
                payload["selected_hypothesis_id"] = None
                payload["selection_reason"] = "No justified test"
            if stage == "experiment_design":
                payload["experiment"] = None
        for action in ("hold", "stop"):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "llm.csv"
                path.write_bytes(self.csv.read_bytes())
                sdk = FakeCodex(action=action, break_stage="experiment_design", mutate=no_test)
                options = dict(material_context=MATERIALS, locked_additive_wt=0,
                               codex_factory=lambda: sdk)
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    adapter.generate_reports_and_suggestion("condition-A", path, AL, **options)
                sdk.break_stage = None
                sdk.calls.clear()
                decision = adapter.generate_reports_and_suggestion("condition-A", path, AL, **options)
                self.assertEqual(sdk.calls, ["experiment_design", "decision"])
                self.assertEqual((decision["action"], decision["next_params"]), (action, None))
                options["codex_factory"] = Mock(side_effect=AssertionError("no SDK after acceptance"))
                self.assertEqual(adapter.generate_reports_and_suggestion("condition-A", path, AL, **options), decision)

    def test_next_round_receives_previous_accepted_hypotheses(self):
        first = self.generate()
        fields, rows = read_csv(self.csv)
        row = dict(rows[0], name="condition-B")
        self.csv.write_text(csv_text(fields, [*rows, row]))
        prompts = []
        original = self.sdk.run
        def capture(prompt, output_schema):
            prompts.append(prompt)
            return original(prompt, output_schema)
        self.sdk.run = capture
        adapter.generate_reports_and_suggestion("condition-B", self.csv, AL,
            material_context=MATERIALS, locked_additive_wt=0, codex_factory=lambda: self.sdk)
        self.assertIn(str(Path(first["report_path"]).with_name("hypotheses.md")), prompts[0])

    def test_unknown_duplicate_and_old_condition_rejected_before_sdk(self):
        for text in ("name\nother\n", "name\ncondition-A\ncondition-A\n", "name\ncondition-A\nnewer\n"):
            self.csv.write_text(text)
            with self.assertRaises(ValueError):
                self.generate()
        self.assertEqual(self.sdk.calls, [])

    def test_final_main_cannot_change_reviewed_conditions(self):
        def mutate(stage, payload):
            if stage == "decision":
                payload["next_params"] = dict(PARAMS, bath_temp=10)
        self.sdk.mutate = mutate
        with self.assertRaisesRegex(ValueError, "differ from the QA-reviewed design"):
            self.generate()
        self.assertFalse(list(self.root.glob("mas/rounds/*/decision.md")))

    def test_design_must_test_selected_hypothesis(self):
        def mutate(stage, payload):
            if stage == "experiment_design":
                payload["experiment"]["hypothesis_id"] = "H2"
        self.sdk.mutate = mutate
        with self.assertRaisesRegex(ValueError, "selected hypothesis"):
            self.generate()

    def test_initial_without_history_creates_no_campaign_row(self):
        self.csv.unlink()
        result = adapter.generate_reports_and_suggestion(None, self.csv, AL, initial=True,
            material_context=MATERIALS, locked_additive_wt=0, codex_factory=lambda: self.sdk)
        self.assertEqual(result["action"], "run")
        self.assertFalse(self.csv.exists())

    def test_round_lock_rejects_concurrent_callback(self):
        adapter._LOCK.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "already running"):
                self.generate()
        finally:
            adapter._LOCK.release()


class ValidationTests(unittest.TestCase):
    def test_pydantic_roundtrip_and_required_nullable_sdk_fields(self):
        params = ExperimentParameters.model_validate(PARAMS)
        self.assertEqual(ExperimentParameters.model_validate_json(params.model_dump_json()), params)
        materials = MaterialContext.model_validate(MATERIALS)
        self.assertEqual(MaterialContext.model_validate_json(materials.model_dump_json()), materials)
        for model in (AnalysisReport, HypothesisUpdate, ExperimentDesign, ExperimentDecision):
            schema = model.model_json_schema()
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
            self.assertFalse(schema["additionalProperties"])
        self.assertIn("next_params", ExperimentDecision.model_json_schema()["required"])

    def test_decision_fields_have_consistent_execution_meaning(self):
        base = {"report": "Decision", "reason": "Missing evidence"}
        for action in ("hold", "stop"):
            accepted = ExperimentDecision.model_validate({**base, "action": action, "next_params": None})
            self.assertEqual(accepted.action, action)
            with self.assertRaises(ValueError):
                ExperimentDecision.model_validate({**base, "action": action, "next_params": PARAMS})
        with self.assertRaises(ValueError):
            ExperimentDecision.model_validate({**base, "action": "run", "next_params": None})

    def test_hypothesis_selection_is_an_existing_nonrefuted_unique_id(self):
        base = {"report": "Updated list", "selection_reason": "Discriminate mechanisms",
                "author_thread_id": "author", "reviewer_thread_id": "qa",
                "selected_hypothesis_id": "H1"}
        hypothesis = {"id": "H1", "statement": "A testable claim", "status": "proposed", "evidence": []}
        accepted = HypothesisUpdate.model_validate({**base, "hypotheses": [hypothesis]})
        self.assertEqual(accepted.hypotheses[0].id, "H1")
        for hypotheses in ([], [dict(hypothesis, status="refuted")], [hypothesis, hypothesis]):
            with self.assertRaises(ValueError):
                HypothesisUpdate.model_validate({**base, "hypotheses": hypotheses})

    def test_invalid_conditions_are_rejected_without_clamping(self):
        cases = [dict(PARAMS, additive_wt=1), dict(PARAMS, polymer_wt=99),
                 dict(PARAMS, mixing_temp=80), dict(PARAMS, bath_temp=26),
                 dict(PARAMS, bath_temp=True), dict(PARAMS, bath_temp=float("nan")),
                 dict(PARAMS, nitrogen="true"), dict(PARAMS, extra=1)]
        for params in cases:
            with self.subTest(params=params), self.assertRaises(ValueError):
                validate_conditions(params, bounds, MATERIALS, locked_additive_wt=0)
        self.assertEqual(validate_conditions(PARAMS, bounds, MATERIALS, 0), {**PARAMS, **MATERIALS})

    def test_operator_materials_cannot_change(self):
        with self.assertRaisesRegex(ValueError, "material setting changed"):
            validate_conditions({**PARAMS, **MATERIALS, "polymer_type": "different"}, bounds, MATERIALS, 0)

    def test_native_qa_required_and_exact_content_checked(self):
        payload = {"report": "measured report", "author_thread_id": "author",
                   "reviewer_thread_id": "reviewer"}
        result = native_result("analysis", payload)
        validate_review(result, AnalysisReport.model_validate(payload), "main")
        for mutation in (lambda r: r.update(verdict="fail"),
                         lambda r: r["reviewed_content"].update(report="different")):
            with self.assertRaises(ValueError):
                validate_review(native_result("analysis", payload, mutation), AnalysisReport.model_validate(payload), "main")
        with self.assertRaisesRegex(ValueError, "SDK-observed"):
            validate_review(NS(items=[]), AnalysisReport.model_validate(payload), "main")
        with self.assertRaisesRegex(ValueError, "separate threads"):
            validate_review(result, AnalysisReport.model_validate(dict(payload, reviewer_thread_id="author")), "main")

    def test_nonfinite_missing_extra_keys_and_bool_numeric_rejected(self):
        for params in (dict(PARAMS, polymer_wt=float("inf")), dict(PARAMS, polymer_wt=True),
                       {k: v for k, v in PARAMS.items() if k != "nitrogen"}):
            with self.assertRaises(ValueError):
                ExperimentParameters.model_validate(params)

    def test_native_qa_with_actual_sdk_event_models(self):
        from openai_codex.generated.v2_all import ThreadItem
        payload = {"report": "observed values", "author_thread_id": "author",
                   "reviewer_thread_id": "reviewer"}
        event = ThreadItem.model_validate({
            "type": "collabAgentToolCall", "id": "call-1", "tool": "wait", "status": "completed",
            "senderThreadId": "main", "receiverThreadIds": ["author", "reviewer"],
            "agentsStates": {
                "author": {"status": "completed", "message": json.dumps({"report": payload["report"]})},
                "reviewer": {"status": "completed", "message": json.dumps({
                    "verdict": "pass", "reviewed_content": {"report": payload["report"]}, "findings": []})},
            },
        })
        validate_review(NS(items=[event]), AnalysisReport.model_validate(payload), "main")

    def test_reviewer_boolean_cannot_masquerade_as_reviewed_numeric_value(self):
        payload = {
            "report": "Test H1", "author_thread_id": "author", "reviewer_thread_id": "qa",
            "experiment": {"hypothesis_id": "H1", "purpose": "repeat", "prediction": "Repeat modulus",
                           "comparator": "condition-A", "criteria": "Compare independent syntheses",
                           "next_params": dict(PARAMS, pullcast_speed=1)},
        }
        def change_type(review):
            review["reviewed_content"]["experiment"]["next_params"]["pullcast_speed"] = True
        result = native_result("experiment_design", payload, change_type)
        with self.assertRaises(ValueError):
            validate_review(result, ExperimentDesign.model_validate(payload), "main")


if __name__ == "__main__":
    unittest.main()
