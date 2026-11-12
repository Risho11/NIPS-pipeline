"""Read-only selection of measured conditions for Pareto validation."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pareto_candidate_selection import assess_candidates, choose_candidates

OBJECTIVES = ['Pore Fraction Mean', 'Elastic Modulus Mean']


def select_validation_points(data, count=5):
    """Prioritize reproducibility, typical performance and tradeoff coverage."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ValueError('count must be an integer of at least two')
    points = data.copy()
    points[OBJECTIVES] = points[OBJECTIVES].apply(pd.to_numeric, errors='coerce')
    points = points[np.isfinite(points[OBJECTIVES]).all(axis=1)].copy()
    values = points[OBJECTIVES].to_numpy()
    points['pareto_optimal'] = [
        not (np.all(values >= point, axis=1) & np.any(values > point, axis=1)).any()
        for point in values
    ]
    front = (points[points.pareto_optimal]
             .sort_values(OBJECTIVES + ['campaign', 'condition'], kind='stable')
             .drop_duplicates(OBJECTIVES).copy())
    if front.empty:
        raise ValueError('No finite Pareto observations available for validation')
    chosen, candidates = choose_candidates(assess_candidates(points), count=count)
    chosen.attrs['candidate_assessment'] = candidates
    return points, front, chosen


def plot_validation_points(points, front, chosen, chemistry):
    figure, axes = plt.subplots(1, 2, figsize=(17, 7))
    axis = axes[0]
    x, y = OBJECTIVES

    def label_offset(frame, x_column, row, position):
        span = max(float(frame[x_column].max() - frame[x_column].min()), 1e-12)
        right = row[x_column] > frame[x_column].min() + .75 * span
        return (-10 if right else 10, 12 if position % 2 == 0 else -20), ('right' if right else 'left')
    axis.scatter(points[x], points[y], color='#bbbbbb', alpha=.6, label='Eligible measured samples')
    axis.plot(front[x], front[y], 'o--', color='#333333', label='Pareto frontier (maximize both)')
    axis.scatter(chosen[x], chosen[y], s=210, marker='*', color='#e53935',
                 edgecolors='black', zorder=4, label='Proposed validation conditions')
    for position, (_, row) in enumerate(chosen.iterrows()):
        offset, alignment = label_offset(chosen, x, row, position)
        axis.annotate(row.validation_id, (row[x], row[y]), xytext=offset, ha=alignment,
                      textcoords='offset points', fontweight='bold',
                      bbox=dict(facecolor='white', edgecolor='none', alpha=.7, pad=1))
    axis.set(xlabel='Pore fraction (compression-fit estimate)', ylabel='Elastic modulus (bar)',
             title='Actual selected source samples and single-sample frontier')
    axis.grid(alpha=.2)
    axis.legend()
    typical = axes[1]
    candidates = chosen.attrs['candidate_assessment']
    typical.scatter(candidates['Pore Fraction median'], candidates['Elastic Modulus median'],
                    color='#bbbbbb', alpha=.6, label='Eligible recipe medians')
    typical.scatter(chosen['Pore Fraction median'], chosen['Elastic Modulus median'], s=210,
                    marker='*', color='#e53935', edgecolors='black', zorder=4, label='Selected recipe medians')
    for position, (_, row) in enumerate(chosen.iterrows()):
        offset, alignment = label_offset(chosen, 'Pore Fraction median', row, position)
        typical.annotate(f"{row.validation_id} (n={int(row.paired_samples)})",
                         (row['Pore Fraction median'], row['Elastic Modulus median']),
                         xytext=offset, ha=alignment, textcoords='offset points', fontweight='bold',
                         bbox=dict(facecolor='white', edgecolor='none', alpha=.7, pad=1))
    typical.set(xlabel='Historical median pore fraction', ylabel='Historical median modulus (bar)',
                title='Typical measured performance across historical samples')
    typical.grid(alpha=.2)
    typical.legend()
    axis.margins(.1)
    typical.margins(.1)
    figure.suptitle(f'{chemistry}: reproducibility-aware validation selection')
    figure.tight_layout()
    return figure, axes
