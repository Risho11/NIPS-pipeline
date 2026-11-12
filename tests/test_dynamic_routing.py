"""Offline routing tests using real prompt assembly and mocked model/device transports."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

os.environ.setdefault("OPENROUTER_API_KEY", "offline-test-placeholder")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/pipeline"))
import run_loop as loop


class DynamicRoutingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.campaign = self.root / "data/results/begins_test"
        self.campaign.mkdir(parents=True)
        self.csv = self.campaign / "llm.csv"
        self.prompt = self.campaign / "dynamic_prompt.jinja"
        self.warm = self.root / "warm.csv"
        self.out = self.root / "recommendations"
        self.condition = "condition-A"
        self.row = {
            "name": self.condition,
            "formatted_parameters": "polymer_wt=15; nips_bath_solvent_wt_percent=0",
            "formatted_parameters_withProp": "polymer_wt=15; nips_bath_solvent_wt_percent=0\nMeasured results",
            "final_report": "Measured results",
            "Elastic Modulus Mean": 123.4567,
            "Pore Fraction Mean": 0.45678,
            "nips_bath_solvent": "none",
            "nips_bath_solvent_wt_percent": 0,
        }
        pd.DataFrame([self.row]).to_csv(self.warm, index=False)
        self.response = {key: loop.INITIAL_PARAMS[key] for key in loop.LLM_PARAMS_KEYS}
        self.response.update(polymer_wt=15, additive_wt=0, bath_temp=15)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.multiple(
            loop, DATA_ROOT=self.root, CSV_AGG_LLM=self.csv,
            CSV_AGG=self.campaign / "agg.csv", CSV_REPS=self.campaign / "reps.csv",
            JSON_RESULTS_DIR=self.out, LLM_AL_SEARCH_MODE="dynamic",
            LLM_AL_WARM_START_CSV=self.warm, ITERATE_ADDITIVES=False, ITERATE_POLYMER=False,
            LOCK_ADDITIVE_WT=True, LOCK_ADDITIVE_WT_VALUE=0,
            COSOLVENT_TYPE="synthetic-cosolvent", NIPS_BATH_SOLVENT="synthetic-bath",
            NIPS_BATH_SOLVENT_WT_PERCENT=10.5,
        ))
        stack.enter_context(patch.object(loop.master_processing, "BRANCH_CONFIG", {
            "curve_segmentation": {"enabled": True, "type": "performance"},
        }))
        stack.enter_context(patch.object(loop.activeLearning, "Generate_report", return_value="Measured results"))
        self.provider = stack.enter_context(patch.object(
            loop.activeLearning, "create_chat_completion", return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.response)))]
            ),
        ))
        stack.enter_context(patch.object(loop.activeLearning.time, "sleep"))
        self.robot = stack.enter_context(patch.object(loop.url, "run_test"))
        self.health = stack.enter_context(patch.object(loop.url, "check_health", return_value={"journal_id": "journal"}))

    def recommendation_messages(self):
        self.assertEqual(self.provider.call_args.kwargs["stage"], "next-experiment-recommendation")
        return self.provider.call_args.kwargs["messages"]

    def prepare_measured_condition(self):
        pd.DataFrame([self.row]).to_csv(self.csv, index=False)
        params = dict(self.response, **loop._current_material_context())
        loop._save_checkpoint(self.condition, {
            "params": params,
            "completed_stages": ["files_saved", "branches_processed", "results_attached"],
        })
        return params

    def test_new_recommendation_reads_each_saved_template_with_same_observations(self):
        pd.DataFrame([self.row]).to_csv(self.csv, index=False)
        requests = []
        for guidance in ("가설 하나", "가설 둘"):
            self.prompt.write_text(guidance + " {{ ranges }}", encoding="utf-8")
            loop.llm_context.generate_reports_and_suggestion(
                self.condition, self.csv, loop.activeLearning, al_search_mode="dynamic",
                locked_additive_wt=0, material_context=loop._current_material_context(),
            )
            requests.append(self.recommendation_messages())
        self.assertEqual(self.provider.call_count, 2)
        first, second = requests
        self.assertIn('The "additive_wt" is locked at 0', first[0]["content"])
        self.assertIn(loop.activeLearning.system_prompt.RECOMMENDATION_OUTPUT_INSTRUCTIONS, first[0]["content"])
        self.assertEqual(first[0]["content"].replace("가설 하나", "가설 둘"), second[0]["content"])
        self.assertEqual(first[1], second[1])
        observations = second[1]["content"][0]["text"]
        self.assertIn('"Elastic Modulus Mean": 123.46', observations)
        self.assertIn('"Pore Fraction Mean": 0.46', observations)
        self.assertIn("Modulus, yield strength and compression slopes are in bar", observations)
        self.assertIn("pore fraction, strains and CV are dimensionless", observations)
        self.assertIn('"nips_bath_solvent_wt_percent": 10.5', observations)
        self.assertIn('"nips_bath_solvent_wt_percent": 0', observations)
        stored = pd.read_csv(self.csv).iloc[0]
        for key in ("Elastic Modulus Mean", "Pore Fraction Mean", "nips_bath_solvent_wt_percent"):
            self.assertEqual(stored[key], self.row[key])
        self.robot.assert_not_called()

    def test_warm_start_reads_campaign_template_and_reuses_saved_initial_conditions(self):
        self.prompt.write_text("Campaign template", encoding="utf-8")
        original = self.warm.read_bytes()
        params = loop._new_campaign_params()
        self.assertIn("Campaign template", self.recommendation_messages()[0]["content"])
        self.assertEqual(params["nips_bath_solvent_wt_percent"], 10.5)
        self.prompt.unlink()
        self.assertEqual(loop._new_campaign_params(), params)
        self.provider.assert_called_once()
        self.assertEqual(self.warm.read_bytes(), original)
        self.robot.assert_not_called()

    def test_fixed_modes_ignore_campaign_template(self):
        pd.DataFrame([self.row]).to_csv(self.csv, index=False)
        self.prompt.write_text("{{ invalid_variable }}", encoding="utf-8")
        for mode, objective, strategy in (
            ("single", "sole optimization objective", "optimize"),
            ("double", "equally important objectives", "optimize"),
            ("double_explore", "equally important objectives", "balanced"),
            ("explore", "sole optimization objective", "explore"),
        ):
            with self.subTest(mode=mode):
                loop.llm_context.generate_reports_and_suggestion(
                    self.condition, self.csv, loop.activeLearning, al_search_mode=mode,
                )
                system = self.recommendation_messages()[0]["content"]
                self.assertIn(objective, system)
                self.assertIn(f"Search mode: {strategy}.", system)

    def test_initial_submission_reuses_journal_and_refuses_operator_drift(self):
        self.prompt.write_text("First experiment guidance", encoding="utf-8")
        params = loop._new_campaign_params()
        params["stock_metadata"] = loop.activeLearning.bounds.send_metadata()
        self.robot.side_effect = TimeoutError("lost acknowledgement")
        with self.assertRaisesRegex(TimeoutError, "lost acknowledgement"):
            loop._submit_dynamic_initial(params)
        first = self.robot.call_args
        self.prompt.unlink()
        resumed = loop._new_campaign_params()
        resumed["stock_metadata"] = params["stock_metadata"]
        with patch.object(loop, "NIPS_BATH_SOLVENT_WT_PERCENT", 20.0):
            with self.assertRaisesRegex(ValueError, "operator settings changed"):
                loop._submit_dynamic_initial(resumed)
        self.robot.assert_called_once()
        self.robot.side_effect = None
        loop._submit_dynamic_initial(resumed)
        self.assertEqual(self.robot.call_args, first)
        self.assertEqual(self.health.call_args.kwargs["expected_journal"], first.kwargs["journal_id"])
        loop._submit_dynamic_initial(resumed)
        self.assertEqual(self.robot.call_count, 2)
        self.provider.assert_called_once()

    def test_missing_or_invalid_template_stops_recommendation(self):
        with self.assertRaisesRegex(FileNotFoundError, "dynamic_prompt.jinja"):
            loop._new_campaign_params()
        for template, message in (
            ("  ", "Dynamic prompt is empty"),
            ("{{ unknown }}", "Cannot render"),
            ("{% if %}", "Cannot render"),
        ):
            with self.subTest(template=template):
                self.prompt.write_text(template, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    loop._new_campaign_params()
        self.provider.assert_not_called()
        self.robot.assert_not_called()

    def test_retry_uses_saved_recommendation_and_same_submission_identity(self):
        params = self.prepare_measured_condition()
        self.prompt.write_text("Original guidance", encoding="utf-8")
        self.robot.side_effect = TimeoutError("lost acknowledgement")
        with self.assertRaisesRegex(TimeoutError, "lost acknowledgement"):
            loop._run_pipeline_and_trigger_next(params, resume_condition=self.condition)
        first = self.robot.call_args
        self.assertEqual(first.args[0]["cosolvent_type"], "synthetic-cosolvent")
        self.assertEqual(first.args[0]["nips_bath_solvent_wt_percent"], 10.5)

        self.prompt.write_text("New guidance", encoding="utf-8")
        recommendation = self.out / f"llm_result_{self.condition}.json"
        saved = recommendation.read_bytes()
        recommendation.unlink()
        with self.assertRaisesRegex(RuntimeError, "without its saved recommendation"):
            loop._run_pipeline_and_trigger_next(params, resume_condition=self.condition)
        self.provider.assert_called_once()
        self.robot.assert_called_once()

        recommendation.write_bytes(saved)
        self.robot.side_effect = None
        loop._run_pipeline_and_trigger_next(params, resume_condition=self.condition)
        self.assertEqual(self.robot.call_args, first)
        self.assertEqual(self.health.call_args.kwargs["expected_journal"], first.kwargs["journal_id"])
        self.assertIsNone(loop._load_resume_params_for_campaign("test"))
        loop._run_pipeline_and_trigger_next(params, resume_condition=self.condition)
        self.assertEqual(self.robot.call_count, 2)
        self.provider.assert_called_once()

    def test_campaign_resume_renders_template_if_recommendation_is_missing(self):
        self.prepare_measured_condition()
        self.prompt.write_text("Guidance for the resumed campaign", encoding="utf-8")
        params = loop._load_resume_params_for_campaign("test")
        self.assertIn("Guidance for the resumed campaign", self.recommendation_messages()[0]["content"])
        self.assertEqual(params["bath_temp"], 15)
        self.robot.assert_not_called()

    def test_retired_sdk_checkpoint_requires_review_without_overwriting(self):
        self.prepare_measured_condition()
        old = {"mas_request": {"id": "old"}, "mas_decision": {"action": "hold"}}
        loop._save_checkpoint(self.condition, old)
        checkpoint = loop._checkpoint_path(self.condition)
        original = checkpoint.read_bytes()
        with self.assertRaisesRegex(ValueError, "retired SDK MAS checkpoint"):
            loop._find_incomplete_condition()
        with self.assertRaisesRegex(ValueError, "retired SDK MAS checkpoint"):
            loop._load_resume_params_for_campaign("test")
        self.assertEqual(checkpoint.read_bytes(), original)
        initial = self.campaign / "initial_suggestion.json"
        initial.write_text(json.dumps(old), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "retired SDK MAS checkpoint"):
            loop._new_campaign_params()
        self.provider.assert_not_called()
        self.robot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
