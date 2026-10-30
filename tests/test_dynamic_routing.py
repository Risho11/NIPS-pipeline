"""Actual run_loop routing/recovery with all robot and model calls mocked."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("OPENROUTER_API_KEY", "offline-test-placeholder")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/pipeline"))
import run_loop as loop
from test_mas import MATERIALS, PARAMS


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.csv = self.root / "data/results/begins_test/llm.csv"
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text("name\ncondition-A\n")
        self.checkpoint = self.root / "raw/condition-A/.pipeline_state.json"
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_text(json.dumps({
            "params": {**PARAMS, **MATERIALS},
            "completed_stages": ["files_saved", "branches_processed", "results_attached"],
            "branch_results": {},
        }))
        (self.checkpoint.parent / "params.json").write_text(json.dumps({**PARAMS, **MATERIALS}))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        settings = dict(LLM_AL_SEARCH_MODE="dynamic", ITERATE_ADDITIVES=False, ITERATE_POLYMER=False,
                        LOCK_ADDITIVE_WT=True, LOCK_ADDITIVE_WT_VALUE=0, LLM_AL_WARM_START_CSV=None,
                        CSV_AGG_LLM=self.csv, CSV_REPS=self.csv.parent / "reps.csv",
                        CSV_AGG=self.csv.parent / "agg.csv", JSON_RESULTS_DIR=self.root / "out",
                        DATA_ROOT=self.root)
        self.stack.enter_context(patch.multiple(loop, **settings))
        self.stack.enter_context(patch.object(loop, "_current_material_context", return_value=MATERIALS))
        self.stack.enter_context(patch.object(loop, "_checkpoint_path", return_value=self.checkpoint))
        self.stack.enter_context(patch.object(loop.master_processing, "BRANCH_CONFIG", {
            "curve_segmentation": {"enabled": True, "type": "performance"}}))
        self.stack.enter_context(patch.object(loop.llm_context, "attach_experiment_time"))
        self.legacy = self.stack.enter_context(patch.object(loop.llm_context, "generate_reports_and_suggestion",
                                                          side_effect=AssertionError("unexpected legacy call")))
        self.dynamic = self.stack.enter_context(patch.object(loop.codex_context, "generate_reports_and_suggestion"))
        self.robot = self.stack.enter_context(patch.object(loop.url, "run_test"))
        self.health = self.stack.enter_context(patch.object(loop.url, "check_health", return_value={"journal_id": "journal"}))

    def decide(self, action):
        self.dynamic.return_value = {
            "action": action, "reason": "bounded evidence decision",
            "next_params": {**PARAMS, **MATERIALS} if action == "run" else None,
            "report_path": str(self.root / "decision.md"),
        }

    def run_pipeline(self):
        loop._run_pipeline_and_trigger_next({**PARAMS, **MATERIALS}, resume_condition="condition-A")

    def test_run_uses_codex_exact_params_and_existing_submission_journal(self):
        self.decide("run")
        self.run_pipeline()
        self.dynamic.assert_called_once()
        self.legacy.assert_not_called()
        sent = self.robot.call_args.args[0]
        self.assertEqual({k: v for k, v in sent.items() if k != "stock_metadata"}, {**PARAMS, **MATERIALS})
        self.assertEqual(self.robot.call_args.kwargs["journal_id"], "journal")
        state = json.loads(self.checkpoint.read_text())
        self.assertIn("next_run_submitted", state["completed_stages"])
        self.assertEqual(self.robot.call_args.kwargs["request_id"], state["submission_request_id"])
        self.run_pipeline()
        self.robot.assert_called_once()
        self.dynamic.assert_called_once()

    def test_hold_and_stop_never_submit_or_regenerate_on_restart(self):
        for action in ("hold", "stop"):
            with self.subTest(action=action):
                state = json.loads(self.checkpoint.read_text())
                state.pop("mas_decision", None)
                self.checkpoint.write_text(json.dumps(state))
                self.decide(action)
                self.dynamic.reset_mock()
                self.run_pipeline()
                self.assertEqual(json.loads(self.checkpoint.read_text())["mas_decision"]["action"], action)
                self.run_pipeline()
                self.dynamic.assert_called_once()
                self.robot.assert_not_called()
                self.health.assert_not_called()
                self.assertFalse((self.root / "out/llm_result_condition-A.json").exists())

    def test_missing_resume_recommendation_uses_dynamic_and_persists_hold(self):
        self.decide("hold")
        self.assertIsNone(loop._load_resume_params_for_campaign("test"))
        self.dynamic.assert_called_once()
        self.legacy.assert_not_called()
        self.robot.assert_not_called()

    def test_new_campaign_also_uses_dynamic_without_warm_start(self):
        self.decide("run")
        self.assertEqual(loop._new_campaign_params(), {**PARAMS, **MATERIALS})
        self.assertTrue(self.dynamic.call_args.kwargs["initial"])
        saved = json.loads((self.csv.parent / "initial_suggestion.json").read_text())
        self.assertEqual(saved["next_params"], {**PARAMS, **MATERIALS})
        self.robot.assert_not_called()

    def test_invalid_dynamic_conditions_never_get_clamped_or_submitted(self):
        self.decide("run")
        self.dynamic.return_value["next_params"]["mixing_temp"] = 80
        with self.assertRaisesRegex(ValueError, "Undiluted"):
            self.run_pipeline()
        self.robot.assert_not_called()
        self.health.assert_not_called()

    def test_ambiguous_submission_reuses_same_request_id(self):
        self.decide("run")
        self.robot.side_effect = TimeoutError("lost acknowledgement")
        with self.assertRaises(TimeoutError):
            self.run_pipeline()
        request_id = self.robot.call_args.kwargs["request_id"]
        self.robot.side_effect = None
        self.run_pipeline()
        self.assertEqual(self.robot.call_args.kwargs["request_id"], request_id)

    def test_conflicting_saved_conditions_block_submission(self):
        self.decide("run")
        path = self.root / "out/llm_result_condition-A.json"
        path.parent.mkdir()
        path.write_text(json.dumps({**PARAMS, **MATERIALS, "bath_temp": 25}))
        with self.assertRaisesRegex(ValueError, "differ from the reviewed"):
            self.run_pipeline()
        self.robot.assert_not_called()

    def test_restart_does_not_submit_already_acknowledged_next_experiment(self):
        self.decide("run")
        self.run_pipeline()
        self.dynamic.reset_mock()
        self.robot.reset_mock()
        self.assertIsNone(loop._load_resume_params_for_campaign("test"))
        self.dynamic.assert_not_called()
        self.robot.assert_not_called()

    def test_initial_submission_reuses_identity_and_does_not_repeat_after_ack(self):
        self.decide("run")
        params = loop._new_campaign_params()
        self.robot.side_effect = TimeoutError("lost first acknowledgement")
        with self.assertRaises(TimeoutError):
            loop._submit_dynamic_initial(params)
        request_id = self.robot.call_args.kwargs["request_id"]
        self.robot.side_effect = None
        # Re-loading the accepted initial decision must preserve its journal.
        params = loop._new_campaign_params()
        loop._submit_dynamic_initial(params)
        self.assertEqual(self.robot.call_args.kwargs["request_id"], request_id)
        self.robot.reset_mock()
        loop._submit_dynamic_initial(params)
        self.robot.assert_not_called()

    def test_fixed_sweep_and_disabled_performance_rejected(self):
        with patch.object(loop, "ITERATE_ADDITIVES", True), self.assertRaisesRegex(ValueError, "fixed iteration"):
            self.run_pipeline()
        with patch.object(loop.master_processing, "BRANCH_CONFIG", {}), self.assertRaisesRegex(ValueError, "performance"):
            self.run_pipeline()
        self.dynamic.assert_not_called()
        self.robot.assert_not_called()

    def test_legacy_mode_still_uses_legacy_generator(self):
        self.legacy.side_effect = None
        self.legacy.return_value = json.dumps({"next_params": PARAMS})
        with patch.object(loop, "LLM_AL_SEARCH_MODE", "double_explore"):
            self.run_pipeline()
        self.legacy.assert_called_once()
        self.dynamic.assert_not_called()
        self.robot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
