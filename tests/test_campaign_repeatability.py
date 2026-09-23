import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'EVALUATE'))
from campaign_repeatability import match_conditions, summarize_repeats


def samples(exposures):
    n = len(exposures)
    return pd.DataFrame({
        'sample_time': pd.date_range('2026-09-21', periods=n, freq='h'),
        'condition': [f'sample_{i}' for i in range(n)],
        'polymer_wt': [17.] * n, 'nitrogen': [True] * n,
        'coupon_to_bath_wait_time': exposures, 'bath_temp': [22.] * n,
        'mixing_temp': [25.] * n, 'nips_bath_wait_time': [1200.] * n,
        'pullcast_speed': [19.] * n, 'Humidity Mean': [40.] * n,
        'Elastic Modulus Mean': np.arange(n) * 20. + 100.,
    })


class RepeatabilityTests(unittest.TestCase):
    def test_complete_linkage_prevents_chaining_and_keeps_all_pairs(self):
        rows, pairs = match_conditions(samples([0, 10, 20]))
        self.assertEqual(len(pairs), 2)
        grouped = rows.dropna(subset=['repeat_group'])
        self.assertEqual(len(grouped), 2)
        self.assertLessEqual(grouped['coupon_to_bath_wait_time'].max()
                             - grouped['coupon_to_bath_wait_time'].min(), 10)

    def test_exact_inputs_missing_inputs_and_tolerance_boundaries(self):
        data = samples([0, 10, 0, 0, 0, 0])
        data.loc[1, ['bath_temp', 'pullcast_speed', 'Humidity Mean']] = [25, 22, 45]
        data.loc[2, 'polymer_wt'] = 16.5
        data.loc[3, 'nitrogen'] = False
        data.loc[4, 'Humidity Mean'] = np.nan
        data.loc[5, 'nitrogen'] = 'unknown'
        rows, pairs = match_conditions(data)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(rows['repeat_group'].notna().sum(), 2)
        self.assertEqual((rows['match_status'] == 'Missing matching inputs').sum(), 2)

    def test_humidity_is_required_match(self):
        for column, mismatch in [('Humidity Mean', 45.1)]:
            data = samples([0, 0])
            data.loc[1, column] = mismatch
            rows, pairs = match_conditions(data)
            self.assertTrue(pairs.empty)
            self.assertTrue(rows['repeat_group'].isna().all())

    def test_mixing_and_residence_are_not_constrained(self):
        data = samples([0, 0])
        data.loc[1, 'mixing_temp'] = 80.
        data.loc[1, 'nips_bath_wait_time'] = 125.
        rows, pairs = match_conditions(data)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(rows['repeat_group'].notna().sum(), 2)

    def test_summary_uses_between_sample_sd(self):
        data = samples([0, 0])
        data['Elastic Modulus SD'] = 999
        rows, _ = match_conditions(data)
        summary = summarize_repeats(rows, ['Elastic Modulus']).iloc[0]
        self.assertAlmostEqual(summary['mean'], 110)
        self.assertAlmostEqual(summary['between_sample_SD'], np.sqrt(200))
        self.assertAlmostEqual(summary['CV_percent'], 100 * np.sqrt(200) / 110)

    def test_empty_singleton_and_no_matches(self):
        for data in [samples([]), samples([0]), samples([0, 100])]:
            rows, pairs = match_conditions(data)
            self.assertTrue(pairs.empty)
            self.assertTrue(rows['repeat_group'].isna().all())
            self.assertTrue(summarize_repeats(rows).empty)


if __name__ == '__main__':
    unittest.main()
