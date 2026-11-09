"""Warm-start exports must preserve the notebooks' selections and measurements."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'EVALUATE'))
from export_warm_start import export_warm_start, PARAMETERS
from notebook_selection import load_notebook_selection, NOTEBOOK_OUTPUTS


class NotebookWarmStartTests(unittest.TestCase):
    def test_serializer_has_no_hidden_date_strain_dedup_or_bath_filters(self):
        rows = []
        for i, (campaign, strain, bath) in enumerate([
                ('2026-10-30', -.1, float('nan')), ('2026-09-25', .2, 10.)]):
            row = dict.fromkeys(PARAMETERS, 1.)
            row.update(name=f'same_{i}', condition='same', campaign=campaign,
                       sample_time=f'2026-10-{30-i} 12:00:00',
                       **{'Strain at 50 bar Mean': strain, 'Elastic Modulus Mean': 123.456789,
                          'Pore Fraction Mean': .567891234, 'nips_bath_solvent_wt_percent': bath})
            rows.append(row)
        frame = pd.DataFrame(rows)
        before = frame.copy(deep=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'warm.csv'
            summary = export_warm_start(frame, path)
            result = pd.read_csv(path, float_precision='round_trip')
        self.assertEqual(summary['rows'], 2)
        self.assertFalse(summary['additional_export_filters'])
        self.assertEqual(result['campaign'].tolist(), frame['campaign'].tolist())
        self.assertEqual(result['condition'].tolist(), ['same', 'same'])
        for col in ('Strain at 50 bar Mean', 'Elastic Modulus Mean', 'Pore Fraction Mean',
                    'nips_bath_solvent_wt_percent'):
            pd.testing.assert_series_equal(result[col], frame[col], check_names=False, check_exact=True)
        pd.testing.assert_frame_equal(frame, before)

    def test_both_notebook_export_cells_preserve_exact_selected_data(self):
        inputs = list((ROOT / 'data/results').glob('begins_*/*.csv'))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        for name, output in NOTEBOOK_OUTPUTS.items():
            with self.subTest(notebook=name), tempfile.TemporaryDirectory() as tmp:
                with patch('matplotlib.pyplot.subplots', side_effect=AssertionError('No plots should run')):
                    selected, settings = load_notebook_selection(name, quiet=True)
                notebook = json.loads((ROOT / 'EVALUATE' / name).read_text(encoding='utf-8'))
                marker = '# Keep AL warm-start history identical to the data selected for these plots.'
                source = next(''.join(c['source']) for c in notebook['cells']
                              if c['cell_type'] == 'code' and marker in ''.join(c['source']))
                namespace = dict(settings, campaign_detailed=selected, repo_root=Path(tmp))
                exec(source.split(marker, 1)[1], namespace)
                path = Path(tmp) / 'data/warm_start' / output
                exported = pd.read_csv(path, float_precision='round_trip')
                self.assertEqual(exported['condition'].tolist(), selected['condition'].tolist())
                self.assertEqual(exported['campaign'].tolist(), selected['campaign'].tolist())
                self.assertEqual(exported['source_name'].tolist(), selected['name'].tolist())
                # All-NaN report/provenance columns can be inferred as numeric in
                # source CSVs; these are intentionally enriched for AL exports.
                metadata = {'final_report', 'initial_report', 'formatted_parameters',
                            'formatted_parameters_withProp', 'pore_fraction_report',
                            'source_name', 'validation_status', 'pore_fraction_method'}
                numeric = [c for c in selected.select_dtypes(include='number').columns if c not in metadata]
                pd.testing.assert_frame_equal(exported[numeric], selected[numeric],
                                              check_dtype=False, check_exact=True)
                for col in ('sample_time', 'effective_sample_date', 'stock_solution_prepared'):
                    pd.testing.assert_series_equal(pd.to_datetime(exported[col]), selected[col],
                                                   check_names=False)
                summary = json.loads(path.with_suffix('.json').read_text())
                self.assertEqual(summary['notebook_selection']['notebook'], 'EVALUATE/' + name)
                self.assertEqual(summary['rows'], len(selected))
                if name == 'campaign_trends.ipynb':
                    self.assertNotIn('17-0add-12deg-cosolv-none-bathSolv-none-0wt-150s-N2-1800s_run2',
                                     exported['condition'].tolist())
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})


if __name__ == '__main__':
    unittest.main()
