"""Selection must retain repeat failures and distinguish chemistry/settings."""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'EVALUATE'))
import export_pareto_protocol
import generate_pareto_validation_log
from pareto_candidate_selection import assess_candidates, choose_candidates, matching_settings
from pareto_reproduction import FIELDS


class CandidateSelectionTests(unittest.TestCase):
    def test_downstream_log_and_protocol_use_the_original_points_without_notebooks(self):
        plan = json.loads((ROOT / 'protocols/pareto_validation_plan.json').read_text(encoding='utf-8'))
        expected = {}
        labels = {'psf': 'PSf / PolarClean', 'primospire': 'Primospire / NMP'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / 'docs/pareto_validation'
            archive.mkdir(parents=True)
            for chemistry in labels:
                name = f'{chemistry}_selected_conditions.csv'
                shutil.copyfile(ROOT / 'docs/pareto_validation' / name, archive / name)
            for batch in plan['batches']:
                chemistry = labels[batch['batch_id'].split('-')[0]]
                for row in batch['conditions']:
                    expected[chemistry, row['validation_id']] = (row['source_campaign'], row['source_condition'])
                    path = Path(row['source_params'])
                    (root / path).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / path, root / path)
                    # Replay hashes the exact local bytes, including the checkout's line endings.
                    row['source_params_sha256'] = hashlib.sha256((root / path).read_bytes()).hexdigest()
            with patch.object(generate_pareto_validation_log, 'ROOT', root):
                result = generate_pareto_validation_log.read_selections()
            self.assertEqual({(r['chemistry'], r['validation_id']): (r['campaign'], r['condition'])
                              for r in result}, expected)
            with patch.object(export_pareto_protocol, 'ROOT', root):
                export_pareto_protocol.export()
            self.assertEqual(json.loads((root / 'protocols/pareto_validation_plan.json').read_text(encoding='utf-8')), plan)
            template = Path('protocols/pareto_validation_setup.template.json')
            self.assertEqual(json.loads((root / template).read_text(encoding='utf-8')),
                             json.loads((ROOT / template).read_text(encoding='utf-8')))

    def test_matching_does_not_merge_different_or_unknown_chemistries(self):
        settings = {key: 1. for key in FIELDS}
        self.assertTrue(matching_settings(settings, settings, 'a', 'b'))
        other = dict(settings, polymer_type='different')
        self.assertFalse(matching_settings(settings, other, 'a', 'a_run2'))
        other = dict(settings, polymer_type=None)
        self.assertFalse(matching_settings(settings, other, 'a', 'b'))
        self.assertTrue(matching_settings(settings, other, 'a', 'a_run2'))
        self.assertFalse(matching_settings(settings, dict(settings, mixing_temp=2.), 'a', 'a_run2'))
        self.assertFalse(matching_settings(settings, dict(settings, mixing_temp=None), 'a', 'a_run2'))

    def test_bad_and_missing_repeats_are_not_filtered_away(self):
        names = ['a', 'a_run2', 'a_run3', 'a_run4']
        history = pd.DataFrame({'condition': names, 'campaign': ['test'] * 4,
                                'Elastic Modulus Mean': [100., 110., 500., np.nan],
                                'Pore Fraction Mean': [.4, .42, .8, np.nan]})
        settings = {name: {key: 1. for key in FIELDS} for name in names}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in names:
                (root / name).mkdir()
                (root / name / 'Specimen_test.csv').touch()
            with patch('pareto_candidate_selection.DEFAULT_RAW_ROOT', root), \
                 patch('pareto_candidate_selection.recorded_settings', return_value=settings):
                assessed = assess_candidates(history.iloc[:2], history)
                screened = history.iloc[:2].assign(screened_position_count=[2, 3])
                with patch('pareto_candidate_selection.load_campaign_data',
                           side_effect=AssertionError('Reviewed cohorts must not reload raw outcomes')):
                    reviewed = assess_candidates(screened).iloc[0]
        self.assertEqual(reviewed.historical_samples, 2)
        self.assertEqual(reviewed['Elastic Modulus median'], 105.)
        self.assertEqual(len(assessed), 1)
        row = assessed.iloc[0]
        self.assertEqual(row.historical_samples, 4)
        self.assertEqual(row.paired_samples, 3)
        self.assertEqual(row['Elastic Modulus median'], 110.)
        self.assertEqual(row.condition, 'a_run2')
        self.assertFalse(row.repeat_supported)
        self.assertGreater(row['Elastic Modulus between CV %'], 25.)

    def test_reproducible_anchors_and_limited_repeat_opportunity(self):
        records = []
        for name, modulus, pore, n, cv in [
            ('stiff', 800, .3, 4, 10), ('porous', 400, .6, 4, 10),
            ('balanced', 600, .45, 4, 10), ('opportunity', 650, .4, 2, 10),
            ('alternative', 500, .5, 4, 10), ('noisy_peak', 1000, .5, 4, 120),
        ]:
            row = dict(condition=name, historical_samples=n, paired_samples=n,
                       paired_fraction=1., repeat_supported=n >= 3 and cv <= 25)
            for prop, value in [('Elastic Modulus', modulus), ('Pore Fraction', pore)]:
                row[prop + ' median'] = value
                row[prop + ' q25'] = value * .9
                row[prop + ' between CV %'] = cv
            records.append(row)
        candidates = pd.DataFrame(records)
        chosen, _ = choose_candidates(candidates)
        self.assertEqual(len(chosen), 5)
        self.assertTrue(chosen.condition.is_unique)
        self.assertTrue({'stiff', 'porous', 'balanced', 'opportunity'}.issubset(chosen.condition))
        self.assertNotIn('noisy_peak', chosen.condition.tolist())
        self.assertEqual(chosen.condition.tolist(), choose_candidates(candidates)[0].condition.tolist())
        with self.assertRaises(ValueError):
            choose_candidates(candidates.iloc[:2], count=5)


if __name__ == '__main__':
    unittest.main()
