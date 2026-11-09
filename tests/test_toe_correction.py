"""The toe correction is a translation and keeps an original plot available."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'pipeline'))
import curve_segmentation as processing
from EVALUATE import generate_fit_log as report
from EVALUATE.reprocess_toe import update_pore_columns, combine_condition_results


class ToeCorrectionTests(unittest.TestCase):
    def test_only_a_committed_mask_changes_pore_fraction(self):
        frame = pd.DataFrame({'Ch:Load (N)': np.linspace(3, 103, 101),
                              'Disp_corrected (um)': np.linspace(0, 100, 101),
                              'display_name': 'policy-test'})
        def regions(data, bp1, bp2, bp3, creep):
            plateau = data.loc[data['strain'].between(bp1, .7), ['strain']]
            densification = data.loc[data['strain'] >= .7, ['strain']]
            return plateau, densification, np.ones(len(plateau))*30, np.ones(len(densification))*80, .7, 50., 200., None
        for state in ('ordinary', 'masked', 'failed_retry'):
            first = (True, {'_score_final': (90, 100, 'pass')}) if state == 'ordinary' else (
                False, {'catastrophic_slope_vs_modulus': (0, 0, 'retry'), '_score_final': (30, 100, 'fail')})
            evaluations = [first, (True, {'_score_final': (90, 100, 'pass')})]
            count = [0]
            def fit(*args):
                count[0] += 1
                if state == 'failed_retry' and count[0] == 2:
                    raise ValueError('forced retry failure')
                return regions(*args)
            with patch.object(processing, 'MASK_TOE_BEFORE_FIT', False), \
                    patch.object(processing, 'SHIFT_ONLY_MASKED_TOE', True), \
                    patch.object(processing, 'SUBTRACT_TOE', True), \
                    patch.object(processing, 'SAVE_PLOTS', False), \
                    patch.object(processing, 'goodData_eval', return_value=.1), \
                    patch.object(processing, 'elastic_peak', side_effect=[.3, .4]), \
                    patch.object(processing, 'find_breakpoints', return_value=(.5, .8)), \
                    patch.object(processing, 'find_changepoint_fit', side_effect=fit), \
                    patch.object(processing, 'goodFit_eval', side_effect=evaluations):
                result = processing.interpretData([frame.copy()], thickness_info=True,
                                                  thickness_list=[100], creep_info=False)[0]
            self.assertEqual(result['Toe Masked'], state == 'masked')
            self.assertAlmostEqual(result['Toe Shift'], .3 if state == 'masked' else 0)
            self.assertAlmostEqual(result['Pore Fraction'], .4 if state == 'masked' else .7)

    def test_unmasked_plot_keeps_original_strain_even_when_toe_detected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(processing, 'SHIFT_ONLY_MASKED_TOE', True):
            fig, ax = processing.plt.subplots()
            line, = ax.plot([0, .5, 1], [0, 50, 100])
            ax.set_xlim(-.04, 1)
            processing.save_strain_views(fig, Path(tmp) / 'fit.png', .2, toe_masked=False)
            np.testing.assert_allclose(line.get_transform().transform([[.5, 50]]), ax.transData.transform([[.5, 50]]))
            self.assertAlmostEqual(ax.get_xlim()[1], 1)
            processing.plt.close(fig)

    def test_refitting_replaces_obsolete_aggregate_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame([{'name': 'sample', 'Pore Fraction Mean': .9},
                          {'name': 'untouched', 'Pore Fraction Mean': .6}]).to_csv(root / 'agg.csv', index=False)
            part = root / 'conditions/one'
            part.mkdir(parents=True)
            pd.DataFrame([{'name': 'sample_preDiscard', 'Pore Fraction Mean': .4},
                          {'name': 'sample_postDiscard', 'Pore Fraction Mean': .5}]).to_csv(part / 'agg.csv', index=False)
            result = combine_condition_results(root, 'agg.csv', ['name'])
            self.assertEqual(set(result['name']), {'untouched', 'sample_preDiscard', 'sample_postDiscard'})
            self.assertNotIn(.9, result['Pore Fraction Mean'].tolist())

    def test_masking_precedes_region_fits_including_average_curves(self):
        frame = pd.DataFrame({'strain': np.linspace(0, 1, 101),
                              'stress (bar)': np.linspace(0, 100, 101),
                              'display_name': 'average-test'})
        for mask in (True, False):
            with patch.object(processing, 'MASK_TOE_BEFORE_FIT', mask), \
                    patch.object(processing, 'goodData_eval', return_value=.2), \
                    patch.object(processing, 'elastic_peak', return_value=.4) as peak, \
                    patch.object(processing, 'find_breakpoints', return_value=(None, None)):
                processing.interpretData([frame], skip_preproc=True, creep_info=False)
                fitted = peak.call_args.args[0]
                self.assertAlmostEqual(fitted['strain'].min(), .2 if mask else 0)
        self.assertEqual(frame['strain'].iloc[0], 0)

    def test_full_fit_publication_restores_all_fit_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'reps.csv'
            pd.DataFrame([{'name': 'condition | rep 1', 'Trial': '1',
                           'Elastic Modulus': 100., 'Pore Fraction': .5, 'Good Fit': True,
                           'Toe Fit Mode': 'legacy'}]).to_csv(path, index=False)
            baseline = pd.read_csv(path)
            masked = baseline.assign(**{'Elastic Modulus': 250., 'Pore Fraction': .4,
                                        'Good Fit': False, 'Toe Fit Mode': 'masked'})
            # Numeric trial identifiers are preserved by the CSV reader.
            update_pore_columns(path, masked, replicate=True, full_fit=True)
            self.assertEqual(pd.read_csv(path).iloc[0]['Elastic Modulus'], 250.)
            self.assertFalse(pd.read_csv(path).iloc[0]['Good Fit'])
            update_pore_columns(path, baseline, replicate=True, full_fit=True)
            pd.testing.assert_frame_equal(pd.read_csv(path), baseline)

    def test_mask_preserves_the_original_strain_origin(self):
        frame = pd.DataFrame({'strain': np.linspace(0, 1, 101), 'stress (bar)': np.linspace(0, 100, 101)})
        masked = processing.mask_detected_toe(frame, .12)
        self.assertAlmostEqual(masked['strain'].iloc[0], .12)
        self.assertAlmostEqual(masked['stress (bar)'].iloc[0], 12)
        self.assertEqual(frame['strain'].iloc[0], 0)
        with self.assertRaises(ValueError):
            processing.mask_detected_toe(frame, .99)

    def test_aggregate_sd_uses_corrected_replicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            reps = [{'name': f'condition | rep {i}', 'Trial': str(i), 'Thickness': 100,
                     'Good Fit': True, 'Pore Fraction': raw - toe,
                     'Pore Fraction Unsubtracted': raw, 'Toe Region': toe, 'Toe Subtracted': True}
                    for i, (raw, toe) in enumerate([(.4, .15), (.6, .05)], 1)]
            output = {'condition': {'condition': 'condition', 'mechanical_properties': reps,
                                    'passing_properties': reps, 'has_failures': False}}
            processing.save_to_csv(output, data_root=Path(tmp),
                                   output_path=Path(tmp) / 'reps.csv', aggregate_path=Path(tmp) / 'agg.csv')
            agg = pd.read_csv(Path(tmp) / 'agg.csv').iloc[0]
            self.assertAlmostEqual(agg['Pore Fraction Mean'], .4)
            self.assertAlmostEqual(agg['Pore Fraction SD'], .15)
            self.assertAlmostEqual(agg['Pore Fraction Unsubtracted Mean'], .5)
            self.assertAlmostEqual(agg['Pore Fraction Unsubtracted SD'], .1)
            saved = pd.read_csv(Path(tmp) / 'reps.csv')
            np.testing.assert_allclose(saved['Pore Fraction'], saved['Pore Fraction Unsubtracted'] - saved['Toe Region'])

    def test_original_origin_can_be_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(processing, 'SUBTRACT_TOE', False):
            fig, ax = processing.plt.subplots()
            ax.plot([0, 1], [0, 10])
            ax.set_xlim(0, 1)
            processing.save_strain_views(fig, Path(tmp) / 'fit.png', .2)
            np.testing.assert_allclose(ax.get_xlim(), [-.04, 1])
            self.assertEqual((Path(tmp) / 'fit.png').read_bytes(), (Path(tmp) / 'Unsubtracted_fit.png').read_bytes())
            processing.plt.close(fig)

    def test_historical_update_is_idempotent_and_updates_promoted_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'agg_llm.csv'
            pd.DataFrame([{'name': 'condition', 'Pore Fraction Mean': .6,
                           'initial_report': 'keep this report'}]).to_csv(path, index=False)
            corrected = pd.DataFrame([{'name': 'condition_postDiscard', 'Pore Fraction Mean': .5,
                                       'Pore Fraction SD': .02, 'Toe Subtracted': True}])
            update_pore_columns(path, corrected)
            update_pore_columns(path, corrected)
            result = pd.read_csv(path).iloc[0]
            self.assertEqual(result['Pore Fraction Mean'], .5)
            self.assertEqual(result['initial_report'], 'keep this report')
            self.assertTrue(result['Toe Subtracted'])

    def test_translation_keeps_y_and_saves_both_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            fig, ax = processing.plt.subplots()
            line, = ax.plot([0, .4, .8], [0, 20, 100])
            scatter = ax.scatter([.4], [20])
            ax.set_xlim(0, 1)
            processing.save_strain_views(fig, Path(tmp) / 'fit.png', .1)
            np.testing.assert_allclose(ax.get_xlim(), [-.036, .9])
            self.assertEqual(ax.get_xlabel(), 'Strain')
            expected = ax.transData.transform([[.3, 20]])
            np.testing.assert_allclose(line.get_transform().transform([[.4, 20]]), expected)
            np.testing.assert_allclose(scatter.get_offset_transform().transform([[.4, 20]]), expected)
            np.testing.assert_allclose(line.get_ydata(), [0, 20, 100])
            self.assertTrue((Path(tmp) / 'Unsubtracted_fit.png').exists())
            used = set()
            html = report.strain_view_image(Path(tmp) / 'fit.png', Path(tmp) / 'assets', 'sample', used, 'fit')
            self.assertIn('data-unsubtracted=', html)
            self.assertEqual(len(used), 2)
            processing.plt.close(fig)

    def test_zero_margin_contains_no_negative_strain_or_stress_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            fig, ax = processing.plt.subplots()
            line, = ax.plot([-.1, 0, .3], [-10, 0, 20])
            points = ax.scatter([-.1, .3], [-5, 20])
            ax.set_ylabel('Stress (bar)')
            ax.set_xlim(-.2, .5)
            ax.set_ylim(-20, 30)
            processing.save_strain_views(fig, Path(tmp) / 'fit.png', .1)
            self.assertLess(ax.get_xlim()[0], 0)
            self.assertLess(ax.get_ylim()[0], 0)
            origin = ax.transData.transform([0, 0])
            for artist in (line, points):
                np.testing.assert_allclose(artist.get_clip_box().get_points()[0], origin)
                self.assertTrue(artist.get_clip_on())
            self.assertFalse(line.get_clip_box().contains(*line.get_transform().transform([.2, -1])))
            self.assertFalse(line.get_clip_box().contains(*line.get_transform().transform([0, 10])))
            self.assertTrue(line.get_clip_box().contains(*line.get_transform().transform([.3, 20])))
            processing.plt.close(fig)

    def test_negative_derivatives_remain_visible(self):
        fig, ax = processing.plt.subplots()
        line, = ax.plot([0, .5], [-5, 5])
        ax.set_ylabel('d(stress)/d(strain)')
        ax.set_xlim(-.1, 1)
        ax.set_ylim(-10, 10)
        processing.style_strain_axes(ax)
        self.assertTrue(line.get_clip_box().contains(*ax.transData.transform([.3, -5])))
        self.assertFalse(line.get_clip_box().contains(*ax.transData.transform([-.02, 5])))
        processing.plt.close(fig)

    def test_labeled_reference_guides_still_touch_axes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fig, ax = processing.plt.subplots()
            data, = ax.plot([0, .5, 1], [-5, 50, 100])
            horizontal, = ax.plot([-.1, .5], [50, 50], linestyle=':')
            vertical, = ax.plot([.5, .5], [-10, 50], linestyle=':')
            horizontal.set_gid('stress-reference-horizontal')
            vertical.set_gid('stress-reference-vertical')
            ax.set_ylabel('Stress (bar)')
            ax.set_xlim(-.1, 1)
            ax.set_ylim(-10, 110)
            processing.save_strain_views(fig, Path(tmp) / 'fit.png', .2)
            h_start = horizontal.get_transform().transform([horizontal.get_xdata()[0], 50])
            v_start = vertical.get_transform().transform([.5, vertical.get_ydata()[0]])
            self.assertAlmostEqual(h_start[0], ax.bbox.xmin)
            self.assertAlmostEqual(v_start[1], ax.bbox.ymin)
            np.testing.assert_allclose(data.get_clip_box().get_points()[0], ax.transData.transform([0, 0]))
            np.testing.assert_allclose(horizontal.get_clip_box().get_points(), ax.bbox.get_points())
            processing.plt.close(fig)

    def test_legend_is_opaque_and_above_every_curve(self):
        fig, ax = processing.plt.subplots()
        line, = ax.plot([0, 1], [0, 10], label='Plateau', zorder=2000)
        legend = ax.legend(framealpha=.2)
        processing.style_strain_axes(ax)
        self.assertGreater(legend.get_zorder(), line.get_zorder())
        self.assertEqual(legend.get_frame().get_alpha(), 1)
        processing.plt.close(fig)

    def test_toe_shading_and_legend_appear_only_in_unsubtracted_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            fig, ax = processing.plt.subplots()
            ax.plot([0, .5, 1], [0, 50, 100], label='Data')
            ax.axvspan(0, .2, color='grey', alpha=.3, label='Toe (masked)')
            ax.set_ylabel('Stress (bar)')
            ax.legend()
            original_save = fig.savefig
            saved = []
            def record(path, **kwargs):
                saved.append((Path(path).name,
                              any(p.get_label() == 'Toe (masked)' for p in ax.patches),
                              [t.get_text() for t in ax.get_legend().get_texts()]))
                original_save(path, **kwargs)
            with patch.object(fig, 'savefig', side_effect=record):
                processing.save_strain_views(fig, Path(tmp) / 'fit.png', .2)
            self.assertEqual(saved[0][0], 'Unsubtracted_fit.png')
            self.assertTrue(saved[0][1])
            self.assertIn('Toe (masked)', saved[0][2])
            self.assertFalse(saved[1][1])
            self.assertNotIn('Toe (masked)', saved[1][2])
            self.assertEqual(ax.get_legend().get_frame().get_alpha(), 1)
            processing.plt.close(fig)


if __name__ == '__main__':
    unittest.main()
