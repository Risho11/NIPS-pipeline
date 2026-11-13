import sys
from pathlib import Path
import unittest

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'EVALUATE'))
from grouped_pareto import summarize_grouped_pareto, plot_grouped_pareto, prepare_recipe_pareto, plot_recipe_pareto


class GroupedParetoTests(unittest.TestCase):
    def test_recipe_medians_keep_singletons_and_have_ten_panels_without_sd_bars(self):
        parameters = {f'p{i}': f'Parameter {i}' for i in range(9)}
        parameters['nitrogen'] = 'Nitrogen'
        candidates = pd.DataFrame({'condition': ['a', 'b', 'c'], 'paired_samples': [1, 4, 2],
                                   'Pore Fraction median': [.4, .6, .3],
                                   'Elastic Modulus median': [300, 200, 100], 'nitrogen': [True, False, True],
                                   **{f'p{i}': [1, 2, 3] for i in range(9)}})
        original = candidates.copy(deep=True)
        table = prepare_recipe_pareto(candidates)
        self.assertEqual(len(table), 3)
        self.assertEqual(table.paired_samples.iloc[0], 1)
        self.assertEqual(table.pareto_optimal.tolist(), [True, True, False])
        figure, axes = plot_recipe_pareto(table, parameters, 'Test')
        self.assertEqual(axes.shape, (2, 5))
        self.assertTrue(all(len(axis.containers) == 0 for axis in axes.flat))
        self.assertIn('Median', axes[0, 0].get_xlabel())
        pd.testing.assert_frame_equal(candidates, original)
        plt.close(figure)

    def test_paired_sample_means_and_between_sample_sd(self):
        rows = pd.DataFrame({'repeat_group': ['G1'] * 3 + ['G2'] * 2 + ['G3', None],
                             'condition': list('abcdefg'),
                             'Pore Fraction Mean': [.4, .6, np.nan, .2, .2, .9, .9],
                             'Elastic Modulus Mean': [100, 300, 9000, 50, 50, 900, 900],
                             'Elastic Modulus SD': [9999] * 7, 'parameter': [10, 20, 999, 2, 2, 3, 4]})
        before = rows.copy(deep=True)
        table = summarize_grouped_pareto(rows, {'parameter': 'Parameter'})
        self.assertEqual(table.group.tolist(), ['G1', 'G2'])
        group = table.iloc[0]
        self.assertEqual(group.n_total, 3)
        self.assertEqual(group.n_paired, 2)
        self.assertEqual(group['Elastic Modulus Mean'], 200)
        self.assertAlmostEqual(group['Elastic Modulus Between SD'], np.sqrt(20000))
        self.assertAlmostEqual(group['Pore Fraction Between SD'], np.sqrt(.02))
        self.assertEqual(group.parameter, 15)
        self.assertEqual(group.conditions, 'a; b')
        self.assertEqual(table.pareto_optimal.tolist(), [True, False])
        pd.testing.assert_frame_equal(rows, before)

    def test_ten_panels_and_empty_groups(self):
        parameters = {f'p{i}': f'Parameter {i}' for i in range(10)}
        rows = pd.DataFrame(columns=['repeat_group', 'condition', 'Pore Fraction Mean', 'Elastic Modulus Mean'])
        table = summarize_grouped_pareto(rows, parameters)
        figure, axes = plot_grouped_pareto(table, parameters, 'Test chemistry')
        self.assertEqual(axes.shape, (2, 5))
        self.assertEqual(len(figure.axes), 10)
        plt.close(figure)


if __name__ == '__main__':
    unittest.main()
