import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'EVALUATE'))
import historical_bath_context as context
import backfill_historical_bath_context as migration


class HistoricalBathTests(unittest.TestCase):
    def test_export_preserves_nonzero_and_does_not_default_future_rows(self):
        frame = pd.DataFrame([
            {'condition': 'old', 'nips_bath_solvent_wt_percent': 'unknown'},
            {'condition': 'nonzero', 'nips_bath_solvent_wt_percent': 10},
            {'condition': 'future', 'nips_bath_solvent_wt_percent': None},
        ])
        original = frame.copy(deep=True)
        with patch.object(context, 'confirmed_conditions', return_value={'old', 'nonzero'}):
            result = context.apply_historical_bath_context(frame)
        self.assertEqual(result.iloc[0]['nips_bath_solvent_wt_percent'], 0)
        self.assertEqual(result.iloc[1]['nips_bath_solvent_wt_percent'], 10)
        self.assertTrue(pd.isna(result.iloc[2]['nips_bath_solvent_wt_percent']))
        pd.testing.assert_frame_equal(frame, original)

    def test_csv_backfill_preserves_measurements_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'history.csv'
            with path.open('w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'Elastic Modulus Mean', 'formatted_parameters'])
                writer.writeheader()
                writer.writerow({'name': 'old_preDiscard', 'Elastic Modulus Mean': '123.456789',
                                 'formatted_parameters': 'bath_temp=9; nips_bath_solvent=unknown; nips_bath_solvent_wt_percent=unknown'})
            self.assertEqual(migration.backfill(path, {'old'}), 1)
            with path.open(newline='', encoding='utf-8') as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row['Elastic Modulus Mean'], '123.456789')
            self.assertEqual(row['nips_bath_solvent_wt_percent'], '0.0')
            self.assertIn('nips_bath_solvent_wt_percent=0.0', row['formatted_parameters'])
            before = path.read_bytes()
            self.assertEqual(migration.backfill(path, {'old'}), 0)
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
