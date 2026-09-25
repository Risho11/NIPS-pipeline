"""Offline checks for complete proposal context; no model or hardware calls."""
import ast
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

PIPELINE = Path(__file__).resolve().parents[1] / 'src' / 'pipeline'
sys.path.insert(0, str(PIPELINE))
from property_context import build_performance_observations, format_property_measurements


def load_context():
    # Isolate optional curve-fitting/vision dependencies, not the routing under test.
    curve = ModuleType('curve_segmentation')
    curve.FORMATTED_PARAMS_KEYS = []
    spec = importlib.util.spec_from_file_location('context_under_test', PIPELINE / 'llm_context.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'curve_segmentation': curve,
                                 'membrane_quality_llm': ModuleType('membrane_quality_llm')}):
        spec.loader.exec_module(module)
    return module


class PropertyContextTests(unittest.TestCase):
    def setUp(self):
        self.context = load_context()
        self.al = SimpleNamespace(Generate_report=Mock(return_value='New narrative'),
                                  LLM_AL=Mock(return_value='proposal'),
                                  LLM_AL_modulus_pore_fraction=Mock(return_value='proposal'))

    def test_all_properties_and_sd_including_future_columns(self):
        row = {'name': 'sample', 'Pore Fraction Mean': .55, 'Pore Fraction SD': .02,
               'Yield Strength Mean': 24, 'Yield Strength SD': 2,
               'New Property Mean': 12, 'New Property SD': 1,
               'Strain at 500 bar Mean': float('nan'), 'CV Mean': float('inf')}
        result = json.loads(format_property_measurements(row))
        self.assertEqual(result['Pore Fraction Mean'], .55)
        self.assertEqual(result['Pore Fraction SD'], .02)
        self.assertEqual(result['Yield Strength SD'], 2)
        self.assertEqual(result['New Property Mean'], 12)
        self.assertIsNone(result['Strain at 500 bar Mean'])
        self.assertIsNone(result['CV Mean'])
        self.assertNotIn('name', result)

    def test_missing_report_does_not_hide_numeric_data(self):
        history = pd.DataFrame([{'name': 'no-report', 'final_report': None,
                                 'formatted_parameters': 'polymer_wt=17',
                                 'Pore Fraction Mean': .6}])
        text = build_performance_observations(history)
        self.assertEqual(json.loads(text)['observations'][0]['identity']['condition'], 'no-report')
        self.assertEqual(json.loads(text)['observations'][0]['conditions']['polymer_wt'], 17)
        self.assertIn('"Pore Fraction Mean": 0.6', text)

    def test_narrative_not_duplicated_and_history_not_mutated(self):
        history = pd.DataFrame([{'name': 'legacy', 'final_report': 'Old fit-quality report',
                                 'Elastic Modulus Mean': 300, 'Elastic Modulus SD': 20}])
        before = history.copy(deep=True)
        text = build_performance_observations(history)
        self.assertNotIn('Old fit-quality report', text)
        self.assertIn('"Elastic Modulus SD": 20.0', text)
        self.assertIn('take precedence', text)
        pd.testing.assert_frame_equal(history, before)

    def test_all_modes_get_numeric_history_without_pore_report_column(self):
        history = pd.DataFrame([{'name': 'sample', 'final_report': 'modulus only',
                                 'Pore Fraction Mean': .57, 'Pore Fraction SD': .03,
                                 'Creep Strain Mean': .1, 'Creep Strain SD': .01}])
        for mode in ['single', 'double', 'explore']:
            self.context._suggest_from_history(history, self.al, 'quality', 0, mode, None, None)
            call = (self.al.LLM_AL_modulus_pore_fraction if mode == 'double' else self.al.LLM_AL).call_args
            self.assertIn('"Pore Fraction Mean": 0.57', call[0][0])
            self.assertIn('"Creep Strain SD": 0.01', call[0][0])
            self.assertEqual(call[1]['quality_observations'], 'quality')

    def test_new_campaign_warm_start_and_current_row_supersession(self):
        with tempfile.TemporaryDirectory() as tmp:
            warm = Path(tmp) / 'warm.csv'
            current = Path(tmp) / 'llm.csv'
            pd.DataFrame([{'name': 'same', 'formatted_parameters': 'polymer_wt=17',
                           'final_report': 'historical', 'Pore Fraction Mean': .1}]).to_csv(warm, index=False)
            self.context.generate_warm_start_suggestion(warm, self.al, al_search_mode='double')
            self.assertIn('"Pore Fraction Mean": 0.1', self.al.LLM_AL_modulus_pore_fraction.call_args[0][0])
            pd.DataFrame([{'name': 'same', 'formatted_parameters': 'polymer_wt=17',
                           'formatted_parameters_withProp': 'polymer_wt=17\nmodulus only',
                           'final_report': '', 'Pore Fraction Mean': .6, 'Pore Fraction SD': .02,
                           'Yield Strength Mean': 25, 'Yield Strength SD': 2}]).to_csv(current, index=False)
            self.context.generate_reports_and_suggestion('same', current, self.al,
                al_search_mode='double', warm_start_csv=warm)
            text = self.al.LLM_AL_modulus_pore_fraction.call_args[0][0]
            self.assertIn('"Pore Fraction Mean": 0.6', text)
            self.assertIn('"Yield Strength SD": 2.0', text)
            self.assertNotIn('"Pore Fraction Mean": 0.1', text)
            observation = json.loads(text)['observations'][0]
            self.assertEqual(observation['identity']['source'], 'current_campaign')
            saved = pd.read_csv(current)
            self.assertEqual(saved.loc[0, 'initial_report'], 'New narrative')
            self.assertIn('New narrative', saved.loc[0, 'final_report'])
            self.al.Generate_report.assert_called_once()

    def test_shared_schema_provenance_and_legacy_fallback(self):
        history = pd.DataFrame([
            {'name': 'warm', '_observation_source': 'warm_start',
             'chemistry': 'Polysulfone / PolarClean (inferred)',
             'final_report': 'duplicate narrative', 'Pore Fraction Mean': .5,
             'pore_fraction_report': 'duplicate pore report',
             'Discarded Fit Reasons': 'one poor fit'},
            {'name': 'live', '_observation_source': 'current_campaign',
             'polymer_type': 'Polysulfone', 'Pore Fraction Mean': .6},
            {'name': 'legacy', 'final_report': 'modulus 100',
             'pore_fraction_report': '0.7 dimensionless'},
        ])
        payload = json.loads(build_performance_observations(history))
        warm, live, legacy = payload['observations']
        self.assertEqual(set(warm), set(live))
        self.assertEqual(warm['identity']['source'], 'warm_start')
        self.assertIn('inferred', warm['identity']['chemistry'])
        self.assertIsNone(warm['conditions']['polymer_type'])
        self.assertEqual(live['conditions']['polymer_type'], 'Polysulfone')
        self.assertIsNone(warm['legacy_report'])
        self.assertIsNone(warm['legacy_pore_fraction_report'])
        self.assertEqual(warm['quality_notes']['discarded_fit_reasons'], 'one poor fit')
        self.assertEqual(legacy['legacy_report'], 'modulus 100')
        self.assertEqual(legacy['legacy_pore_fraction_report'], '0.7 dimensionless')

    def test_processing_schema_sends_every_property(self):
        tree = ast.parse((PIPELINE / 'curve_segmentation.py').read_text(encoding='utf-8'))
        schema = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'MECH_PROP_SCHEMA' for t in node.targets))
        self.assertTrue(all(spec['llm'] for spec in schema.values()))
        row = {f'{key} Mean': 1.0 for key in schema}
        row.update({f'{key} SD': .1 for key, spec in schema.items() if spec['sd']})
        self.assertEqual(json.loads(format_property_measurements(row, schema)), row)


if __name__ == '__main__':
    unittest.main()
