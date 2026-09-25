"""Offline regression checks; no robot submissions or paid LLM calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "pipeline"))
import llm_context
import run_loop


class WarmStartTests(unittest.TestCase):
    def test_history_only_all_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            pd.DataFrame([{
                "name": "prior", "formatted_parameters": "polymer_wt=17",
                "final_report": "measured modulus", "quality_report": "good film",
                "pore_fraction_report": "0.7 dimensionless", "polymer_wt": 17,
            }]).to_csv(path, index=False)
            original = path.read_bytes()
            for mode in ("single", "double", "explore"):
                with self.subTest(mode=mode):
                    al = SimpleNamespace(LLM_AL=Mock(return_value="suggestion"),
                        LLM_AL_modulus_pore_fraction=Mock(return_value="suggestion"))
                    result = llm_context.generate_warm_start_suggestion(
                        path, al, al_search_mode=mode, locked_additive_wt=0,
                        material_context={"polymer_type": "Primospire"})
                    self.assertEqual(result, "suggestion")
                    call = (al.LLM_AL_modulus_pore_fraction if mode == "double" else al.LLM_AL).call_args
                    self.assertIn("measured modulus", call.args[0])
                    self.assertIn("good film", call.kwargs["quality_observations"])
                    self.assertEqual(call.kwargs["locked_additive_wt"], 0)
                    if mode == "double":
                        self.assertIn("0.7 dimensionless", call.args[0])
                    if mode == "explore":
                        self.assertTrue(call.kwargs["diversity_context"])
                    self.assertEqual(path.read_bytes(), original)
            pd.DataFrame(columns=["name", "final_report", "formatted_parameters"]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "no data rows"):
                llm_context.generate_warm_start_suggestion(path, al)
            pd.DataFrame([{"name": "bad"}]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "missing columns"):
                llm_context.generate_warm_start_suggestion(path, al)

    def test_first_parameters_and_saved_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "campaign" / "llm.csv"
            candidate = dict(run_loop.INITIAL_PARAMS, polymer_wt=16, additive_wt=2)
            with patch.object(run_loop, "CSV_AGG_LLM", csv_path), \
                 patch.object(run_loop, "LLM_AL_WARM_START_CSV", "history.csv"), \
                 patch.object(run_loop, "LOCK_ADDITIVE_WT", True), \
                 patch.object(run_loop, "LOCK_ADDITIVE_WT_VALUE", 0), \
                 patch.object(llm_context, "generate_warm_start_suggestion", return_value=json.dumps(candidate)), \
                 patch.object(run_loop.activeLearning.bounds, "test_target", return_value=(15, 0)) as bounds:
                params = run_loop._new_campaign_params()
                bounds.assert_called_once_with(16, 0)
                self.assertEqual(params["polymer_wt"], 15)
                self.assertEqual(params["additive_wt"], 0)
                saved = json.loads((csv_path.parent / "initial_suggestion.json").read_text())
                self.assertEqual(saved["next_params"], params)
                self.assertFalse(csv_path.exists())

    def test_no_history_uses_defaults(self):
        with patch.object(run_loop, "LLM_AL_WARM_START_CSV", None):
            params = run_loop._new_campaign_params()
            self.assertEqual(params, run_loop.INITIAL_PARAMS)
            self.assertIsNot(params, run_loop.INITIAL_PARAMS)

    def test_stock_temperature_tracks_both_layouts_and_changing_concentrations(self):
        bounds = run_loop.activeLearning.bounds
        for concentration in (17, 21, 19.5):
            for stocks in (bounds.OldStockStruct(polymer_stock_wt_percent=concentration),
                           bounds.StockParameters(polymer_stock_pwt=concentration)):
                with self.subTest(stocks=stocks), patch.object(bounds, "DEFAULT_STOCKS", stocks):
                    for polymer, additive, expected in (
                        (concentration, 0, 25),
                        (concentration + 1e-10, 0, 25),
                        (concentration - 0.1, 0, 80),
                        (concentration, 2, 80),
                    ):
                        params = dict(run_loop.INITIAL_PARAMS, polymer_wt=polymer,
                                      additive_wt=additive, mixing_temp=80)
                        run_loop._enforce_stock_mixing_temperature(params)
                        self.assertEqual(params["mixing_temp"], expected)
                    self.assertIn(f"({concentration} wt%)", run_loop.activeLearning.current_ranges())

    def test_warm_start_clamp_precedes_temperature_and_save(self):
        bounds = run_loop.activeLearning.bounds
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "llm.csv"
            candidate = dict(run_loop.INITIAL_PARAMS, polymer_wt=25, additive_wt=0, mixing_temp=80)
            with patch.object(run_loop, "CSV_AGG_LLM", csv_path), \
                 patch.object(run_loop, "LLM_AL_WARM_START_CSV", "history.csv"), \
                 patch.object(bounds, "DEFAULT_STOCKS", bounds.OldStockStruct(polymer_stock_wt_percent=21)), \
                 patch.object(llm_context, "generate_warm_start_suggestion", return_value=json.dumps(candidate)):
                params = run_loop._new_campaign_params()
                self.assertEqual((params["polymer_wt"], params["mixing_temp"]), (21, 25))
                saved = json.loads((Path(tmp) / "initial_suggestion.json").read_text())
                self.assertEqual(saved["next_params"]["mixing_temp"], 25)

    def test_saved_resume_temperature_is_corrected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            campaign = root / "data/results/begins_test"
            campaign.mkdir(parents=True)
            (campaign / "llm.csv").write_text("name\nprevious\n")
            saved = dict(run_loop.INITIAL_PARAMS, polymer_wt=17, additive_wt=0, mixing_temp=80)
            (root / "llm_result_previous.json").write_text(json.dumps(saved))
            with patch.object(run_loop, "DATA_ROOT", root), \
                 patch.object(run_loop, "JSON_RESULTS_DIR", root), \
                 patch.object(run_loop.activeLearning.bounds, "DEFAULT_STOCKS",
                              run_loop.activeLearning.bounds.OldStockStruct(polymer_stock_wt_percent=17)):
                self.assertEqual(run_loop._load_resume_params_for_campaign("test")["mixing_temp"], 25)


if __name__ == "__main__":
    unittest.main()
