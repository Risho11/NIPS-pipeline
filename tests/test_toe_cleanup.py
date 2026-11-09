import json
from pathlib import Path
import tempfile
import unittest

from EVALUATE.cleanup_toe_artifacts import cleanup_generated


class ToeCleanupTests(unittest.TestCase):
    def test_original_and_latest_policy_prunes_only_intermediate_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / 'data/toe_reprocessing'
            for name in ('conditional/reps.csv', 'masked/reps.csv', 'corrected/reps.csv',
                         'originals/data.csv', 'snapshots/masked/data.csv'):
                p = task / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('data')
            (task / 'active.json').write_text(json.dumps({'origin': 'conditional', 'plot_prefix': 'test-toe-conditional'}))
            (task / 'conditional/validation.json').write_text(json.dumps({'batch_complete': True}))
            for name in ('test-toe-2026-11-06', 'test-toe-masked-2026-11-06',
                         'test-toe-conditional-2026-11-06', 'test-2026-06-01'):
                p = root / 'data/plots/pseudo-runs' / name
                p.mkdir(parents=True)
                (p / 'plot.png').write_text('plot')
            original = root / 'data/plots/run-2026-06-01/plot.png'
            original.parent.mkdir(parents=True)
            original.write_text('original plot')
            raw = root / 'data/raw/specimen.csv'
            raw.parent.mkdir(parents=True)
            raw.write_text('original measurements')
            plan = cleanup_generated(root, retain_original_and_latest=True)
            self.assertTrue((task / 'masked').exists())
            self.assertFalse(plan['applied'])
            cleanup_generated(root, apply=True, retain_original_and_latest=True)
            for name in ('masked', 'corrected', 'snapshots'):
                self.assertFalse((task / name).exists())
            for name in ('conditional/reps.csv', 'originals/data.csv'):
                self.assertTrue((task / name).exists())
            for name in ('test-toe-conditional-2026-11-06', 'test-2026-06-01'):
                self.assertTrue((root / 'data/plots/pseudo-runs' / name / 'plot.png').exists())
            self.assertTrue(original.exists())
            self.assertTrue(raw.exists())

    def test_removes_previews_but_preserves_raw_results_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / 'data/toe_reprocessing'
            for path in ('previews/example/image.png', 'review_high_modulus/index.html',
                         'masked/preview/image.png', 'masked/reps.csv', 'conditional/reps.csv',
                         'originals/data.csv', 'snapshots/masked/data.csv'):
                target = task / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('keep or remove as appropriate')
            raw = root / 'data/raw/specimen.csv'
            raw.parent.mkdir(parents=True)
            raw.write_text('immutable raw')
            task.joinpath('active.json').write_text(json.dumps({'origin': 'conditional'}))
            task.joinpath('conditional/validation.json').write_text(json.dumps({'batch_complete': True}))
            preview_plot = root / 'data/plots/pseudo-runs/test-toe-conditional-preview-0123456789abcdef-2026-11-06/image.png'
            preview_plot.parent.mkdir(parents=True)
            preview_plot.write_text('preview')
            retained_plot = root / 'data/plots/pseudo-runs/test-toe-masked-2026-11-06/image.png'
            retained_plot.parent.mkdir(parents=True)
            retained_plot.write_text('rollback plot')
            plan = cleanup_generated(root)
            self.assertFalse(plan['applied'])
            self.assertTrue((task / 'previews/example/image.png').exists())
            result = cleanup_generated(root, apply=True)
            self.assertTrue(result['applied'])
            self.assertFalse((task / 'previews').exists())
            self.assertFalse(preview_plot.exists())
            for path in ('masked/reps.csv', 'conditional/reps.csv', 'originals/data.csv', 'snapshots/masked/data.csv'):
                self.assertTrue((task / path).exists())
            self.assertTrue(raw.exists())
            self.assertTrue(retained_plot.exists())

    def test_incomplete_results_prevent_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = root / 'data/toe_reprocessing'
            (task / 'previews').mkdir(parents=True)
            (task / 'previews/plot.png').write_text('review')
            (task / 'conditional').mkdir()
            (task / 'active.json').write_text(json.dumps({'origin': 'conditional'}))
            (task / 'conditional/validation.json').write_text(json.dumps({'batch_complete': False}))
            with self.assertRaises(ValueError):
                cleanup_generated(root, apply=True)
            self.assertTrue((task / 'previews/plot.png').exists())


if __name__ == '__main__':
    unittest.main()
