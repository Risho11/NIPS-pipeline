"""Report plots must belong to the named physical experiment."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fit_log', ROOT / 'EVALUATE/generate_fit_log.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class PlotIdentityTests(unittest.TestCase):
    def test_fit_modes_do_not_borrow_each_others_plots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for prefix in ('test-toe', 'test-toe-masked'):
                rep = root / 'plots/pseudo-runs' / (prefix + '-2026-11-06') / 'condition/rep-1'
                rep.mkdir(parents=True)
                (rep / 'Pre-Processing_rep-1.png').write_bytes(b'diagnostic')
                if prefix == 'test-toe':
                    (rep / 'Segmentation_rep-1.png').write_bytes(b'legacy fit')
            with patch.object(report, 'PLOTS_DIR', root / 'plots'), patch.object(report, 'ROOT', root):
                legacy = report.find_plots('condition', plot_prefix='test-toe')[0]
                masked = report.find_plots('condition', plot_prefix='test-toe-masked')[0]
                self.assertEqual(legacy[0].name, 'Segmentation_rep-1.png')
                self.assertEqual(masked[0].name, 'Pre-Processing_rep-1.png')
                self.assertIn('test-toe-masked-2026-11-06', str(masked[0]))

    def test_html_includes_optional_subtraction_diagnostics(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rep = root / 'plots/pseudo-runs/test-toe-masked-2026-11-06/condition/rep-1'
            rep.mkdir(parents=True)
            for name in ('Segmentation_rep-1.png', 'Unsubtracted_Segmentation_rep-1.png', 'Pre-Processing_rep-1.png'):
                (rep / name).write_bytes(b'plot')
            frame = pd.DataFrame([{'name': 'condition | rep 1', 'condition': 'condition',
                                   'Trial': 'sample 1', 'date': '2026-11-06 12:00:00',
                                   'Good Fit': True, 'Good Fit Score': 90, 'Toe Region': .1}])
            output = root / 'docs/log.html'
            with patch.object(report, 'PLOTS_DIR', root / 'plots'), patch.object(report, 'ROOT', root), \
                    patch.object(report, 'load_csvs', return_value=frame), \
                    patch.object(report, 'load_agg_cvs', return_value={}):
                report.generate(output_path=output, plot_prefix='test-toe-masked')
            html = output.read_text(encoding='utf-8')
            self.assertIn('id="toggle-preprocessing"', html)
            self.assertIn('class="preprocessing-plots"', html)
            self.assertIn('data-unsubtracted=', html)
            self.assertIn('<dialog id="plot-viewer"', html)
            self.assertIn('plotViewer.showModal()', html)
            self.assertIn('plotViewerImage.src = img.src', html)
            self.assertNotIn('window.open(', html)
            self.assertNotIn('document.write(', html)
            self.assertTrue((output.parent / 'assets/fit/condition/Pre-Processing_rep-1.png').exists())

    def test_separate_experiments_and_verified_reprocessing(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            base = parent / 'condition'
            repeat = parent / 'condition_run2'
            base.mkdir()
            repeat.mkdir()
            self.assertEqual(report._best_condition_dir(parent, 'condition'), base)
            self.assertEqual(report._best_condition_dir(parent, 'condition_run2'), repeat)
            (repeat / 'plot_source.json').write_text(json.dumps({'condition_name': 'condition'}))
            self.assertEqual(report._best_condition_dir(parent, 'condition'), repeat)
            self.assertIsNone(report._best_condition_dir(parent, 'condition_run2'))

    def test_missing_base_never_borrows_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'condition_run2').mkdir()
            self.assertIsNone(report._best_condition_dir(Path(tmp), 'condition'))

    def test_failed_base_does_not_borrow_average_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            day = root / 'plots/run-2026-10-23'
            rep = day / 'condition/rep-1'
            rep.mkdir(parents=True)
            (rep / 'Pre-Processing_rep-1.png').write_bytes(b'failed')
            avg = day / 'condition_run2/averageFits'
            avg.mkdir(parents=True)
            (avg / 'average_fit_average.png').write_bytes(b'valid repeat')
            with patch.object(report, 'PLOTS_DIR', root / 'plots'), patch.object(report, 'ROOT', root):
                seg, comps, averages, derivs, _ = report.find_plots('condition')
                self.assertEqual(seg, [rep / 'Pre-Processing_rep-1.png'])
                self.assertEqual(averages, [])
                self.assertEqual(len(report.find_plots('condition_run2')[2]), 1)

    def test_wrong_cached_asset_replaced_even_when_newer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'plot.png'
            source.write_bytes(b'correct curve')
            dest = root / 'assets/condition/plot.png'
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b'wrong curve')
            os.utime(source, (1, 1))
            report.copy_asset(source, root / 'assets', 'condition')
            self.assertEqual(dest.read_bytes(), source.read_bytes())


if __name__ == '__main__':
    unittest.main()
