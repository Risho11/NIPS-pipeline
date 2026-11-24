"""A clean CI checkout must retain the published active segmentation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fit_log', ROOT / 'EVALUATE/generate_fit_log.py')
log = importlib.util.module_from_spec(spec)
spec.loader.exec_module(log)


class PublishedAssetsTest(unittest.TestCase):
    def test_new_batch_appears_with_recorded_replicates_on_next_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            results = root / 'data/results'
            original = results / 'begins_original'
            original.mkdir(parents=True)
            original_row = {'name': 'historical | rep 1', 'Trial': 'sample 1', 'date': '2026-11-10',
                            'Good Fit': True, 'Good Fit Score': 82}
            pd.DataFrame([original_row]).to_csv(original / 'reps.csv', index=False)
            plots = root / 'data/plots'
            page = root / 'docs/fit_evaluation_log.html'
            with patch.multiple(log, ROOT=root, RESULTS_DIR=results, PLOTS_DIR=plots, RAW_ROOT=root / 'data/raw'):
                log.generate(output_path=page)
                self.assertIn('1 condition(s)', page.read_text(encoding='utf8'))

                batch = results / 'begins_recasts' / 'psf-water'
                batch.mkdir(parents=True)
                pd.DataFrame([
                    {'name': 'film | rep 1', 'Trial': 'sample 9', 'date': '2026-11-16', 'Good Fit': False, 'Good Fit Score': 0},
                    {'name': 'film | rep 3', 'Trial': 'sample 10', 'date': '2026-11-16', 'Good Fit': True, 'Good Fit Score': 92},
                ]).to_csv(batch / 'reps.csv', index=False)
                pd.DataFrame([{'name': 'film', 'date': '2026-11-16', 'CV Mean': 0.12}]).to_csv(
                    batch / 'agg.csv', index=False)
                image = plots / 'run-recasts-psf-water/film/rep-3/Segmentation_rep-3.png'
                image.parent.mkdir(parents=True)
                image.write_bytes(b'recorded replicate 3 figure')
                log.generate(output_path=page)

            html = page.read_text(encoding='utf8')
            self.assertEqual(html.count('<div class="card"'), 2)
            self.assertLess(html.index('id="condition-film"'), html.index('id="condition-historical"'))
            self.assertIn('data-status="mixed" data-run="run-recasts-psf-water"', html)
            self.assertIn('Pre CV: 0.1200', html)
            card = html.split('id="condition-film"', 1)[1].split('id="condition-historical"', 1)[0]
            first, third = card.split('Replicate 3 · Original fit evaluation')
            self.assertIn('Replicate 1 · Original fit evaluation', first)
            self.assertIn('>0/100', first)
            self.assertIn('No plot found', first)
            self.assertIn('>92/100', third)
            asset = 'assets/fit/film/Segmentation_rep-3.png'
            self.assertIn(f'src="{asset}"', third)
            self.assertEqual((page.parent / asset).read_bytes(), image.read_bytes())

    def test_ci_reuses_active_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'fit_evaluation_log.html'
            assets = out.parent / 'assets/fit/sample'
            assets.mkdir(parents=True)
            image = assets / 'Segmentation_rep-1.png'
            image.write_bytes(b'current fit')
            index = {'sample': dict(prefix='test-toe-conditional', run='run-original',
                                   seg=[image.name], comp=[], preproc=[], deriv=[], avg=[])}
            out.with_name(out.stem + '_plots.json').write_text(json.dumps(index))
            frame = pd.DataFrame([dict(condition='sample', name='sample', date='2026-01-01')])
            with patch.object(log, 'load_csvs', return_value=frame), \
                 patch.object(log, 'load_agg_cvs', return_value={}), \
                 patch.object(log, 'find_plots', return_value=([], [], [], [], None)), \
                 patch.object(log, 'true_condition_date', return_value=None), \
                 patch.object(log, 'condition_card', return_value='card') as card:
                # The real renderer marks assets in use. Mirror that here.
                def render(*args, **kwargs):
                    self.assertEqual(args[2], [image])
                    args[8].add(image.resolve())
                    return 'card'
                card.side_effect = render
                log.generate(output_path=out, plot_prefix='test-toe-conditional')
            self.assertEqual(image.read_bytes(), b'current fit')
            self.assertEqual(json.loads(out.with_name(out.stem + '_plots.json').read_text()), index)
            image.unlink()
            with patch.object(log, 'load_csvs', return_value=frame), \
                 patch.object(log, 'load_agg_cvs', return_value={}), \
                 patch.object(log, 'find_plots', return_value=([], [], [], [], None)), \
                 patch.object(log, 'true_condition_date', return_value=None):
                with self.assertRaises(FileNotFoundError):
                    log.generate(output_path=out, plot_prefix='test-toe-conditional')


if __name__ == '__main__':
    unittest.main()
