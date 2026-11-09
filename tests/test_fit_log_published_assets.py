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
