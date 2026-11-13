"""Pareto comparison of all similar-condition repeat groups, using sample means."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from html import escape
from campaign_repeatability import nitrogen_state

X = 'Pore Fraction Mean'
Y = 'Elastic Modulus Mean'


def collapsed_table_html(table, title):
    return (f'<details><summary>{escape(title)} ({len(table)} rows)</summary>'
            '<div style="max-height:420px;overflow:auto;margin-top:8px">'
            + table.to_html(index=False) + '</div></details>')


def summarize_grouped_pareto(rows, parameters):
    records = []
    for group, members in rows.dropna(subset=['repeat_group']).groupby('repeat_group', sort=False):
        outcomes = members[[X, Y]].apply(pd.to_numeric, errors='coerce')
        valid = np.isfinite(outcomes).all(axis=1)
        paired = outcomes.loc[valid]
        if len(paired) < 2:
            continue
        record = dict(group=group, n_total=len(members), n_paired=len(paired),
                      conditions='; '.join(members.loc[valid, 'condition'].astype(str)))
        for column in (X, Y):
            record[column] = paired[column].mean()
            record[column.replace(' Mean', ' Between SD')] = paired[column].std(ddof=1)
        for parameter in parameters:
            values = members.loc[valid, parameter] if parameter in members else pd.Series(dtype=float)
            values = values.map(nitrogen_state) if parameter == 'nitrogen' else pd.to_numeric(values, errors='coerce')
            values = values[np.isfinite(values)]
            record[parameter] = values.mean()
            record[parameter + ' min'] = values.min()
            record[parameter + ' max'] = values.max()
            record[parameter + ' n'] = len(values)
        records.append(record)
    columns = ['group', 'n_total', 'n_paired', 'conditions', X, Y,
               'Pore Fraction Between SD', 'Elastic Modulus Between SD']
    table = pd.DataFrame(records) if records else pd.DataFrame(columns=columns + list(parameters))
    values = table[[X, Y]].to_numpy(dtype=float)
    table['pareto_optimal'] = [not (np.all(values >= point, axis=1) & np.any(values > point, axis=1)).any()
                               for point in values]
    return table


def prepare_recipe_pareto(candidates):
    """Same recipe medians as the typical-performance view; keep singletons."""
    table = candidates.copy()
    table.insert(0, 'recipe_id', [f'R{i + 1}' for i in range(len(table))])
    values = table[['Pore Fraction median', 'Elastic Modulus median']].to_numpy(dtype=float)
    table['pareto_optimal'] = [not (np.all(values >= p, axis=1) & np.any(values > p, axis=1)).any()
                               for p in values]
    return table


def plot_recipe_pareto(table, parameters, chemistry, property_label=None):
    return plot_grouped_pareto(table, parameters, chemistry, property_label, kind='recipes')


def plot_grouped_pareto(table, parameters, chemistry, property_label=None, *, kind='groups'):
    recipes = kind == 'recipes'
    X, Y = ('Pore Fraction median', 'Elastic Modulus median') if recipes else ('Pore Fraction Mean', 'Elastic Modulus Mean')
    if len(parameters) != 10:
        raise ValueError('Use the same ten parameters as the existing Pareto panels')
    label = property_label or (lambda name: name)
    figure, axes = plt.subplots(2, 5, figsize=(35, 12), squeeze=False)
    frontier = table.loc[table.pareto_optimal].sort_values(X)
    for axis, (parameter, title) in zip(axes.flat, parameters.items()):
        if table.empty:
            axis.text(.5, .5, 'No groups with two finite paired observations',
                      ha='center', va='center', transform=axis.transAxes)
        else:
            if not recipes:
                axis.errorbar(table[X], table[Y], xerr=table['Pore Fraction Between SD'],
                              yerr=table['Elastic Modulus Between SD'], fmt='none',
                              ecolor='#808080', elinewidth=1.2, capsize=4, alpha=.7,
                              label='±1 between-sample SD', zorder=1)
            colors = pd.to_numeric(table[parameter], errors='coerce')
            valid = np.isfinite(colors)
            axis.scatter(table.loc[~valid, X], table.loc[~valid, Y], color='#bdbdbd',
                         s=75, edgecolor='white', linewidth=.6, zorder=3)
            options = dict(cmap='viridis')
            if parameter == 'nitrogen':
                options = dict(cmap=plt.matplotlib.colors.ListedColormap(['#4C78A8', '#E45756']), vmin=-.5, vmax=1.5)
            scatter = axis.scatter(table.loc[valid, X], table.loc[valid, Y], c=colors[valid],
                                   s=75, edgecolor='white', linewidth=.6, zorder=3, **options)
            colorbar = figure.colorbar(scatter, ax=axis, pad=.02)
            if parameter == 'nitrogen':
                colorbar.set_ticks([0, 1], labels=['Off', 'On'])
            colorbar.set_label(title, fontsize=11)
            axis.plot(frontier[X], frontier[Y], 'k--', linewidth=2,
                      label='Pareto front of recipe medians' if recipes else 'Pareto front of group means', zorder=4)
            axis.scatter(frontier[X], frontier[Y], s=135, facecolor='none', edgecolor='black', linewidth=2, zorder=5)
            for _, row in table.iterrows():
                if recipes and not row.pareto_optimal:
                    continue  # Many recipe points; label frontier recipes to avoid clutter.
                text = (f'{row.recipe_id} (n={int(row.paired_samples)})' if recipes else
                        f'{row.group} (n={int(row.n_paired)})')
                if row.pareto_optimal:
                    value = row[parameter]
                    value_label = ('On' if value == 1 else 'Off') if parameter == 'nitrogen' and pd.notna(value) else f'{value:.3g}'
                    text += '\n' + value_label
                axis.annotate(text, (row[X], row[Y]), xytext=(7, 7), textcoords='offset points',
                              fontsize=8, fontweight='semibold' if row.pareto_optimal else 'normal',
                              bbox=dict(boxstyle='round,pad=.18', facecolor='white', edgecolor='none', alpha=.78),
                              arrowprops=dict(arrowstyle='-', color='#777777', linewidth=.5), zorder=6)
            axis.legend(loc='best', fontsize=9)
        axis.set_title(f'Colored by {title}', fontsize=15, fontweight='semibold')
        axis.set_xlabel(('Median ' if recipes else '') + label('Pore Fraction'), fontsize=13)
        axis.set_ylabel(('Median ' if recipes else '') + label('Elastic Modulus'), fontsize=13)
        axis.grid(alpha=.2)
        axis.set_box_aspect(1)
    subtitle = 'typical measured performance — historical recipe medians' if recipes else 'similar-condition groups — means ± between-sample SD'
    figure.suptitle(f'{chemistry}: {subtitle}', fontsize=21, y=1.01)
    figure.tight_layout()
    # Keep dense frontier labels readable without moving any measured points.
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    offsets = [(dx, dy) for dy in (7, -22, 28, -42, 48, -62, 68)
               for dx in (7, -7, 42, -42, 78, -78)]
    for axis in axes.flat:
        occupied = []
        for annotation in sorted(axis.texts, key=lambda item: '\n' not in item.get_text()):
            if not hasattr(annotation, 'xy'):
                continue
            best = None
            for dx, dy in offsets:
                annotation.set_position((dx, dy))
                annotation.set_ha('left' if dx > 0 else 'right')
                # Measure the text itself; annotation extents include its leader line.
                annotation.update_bbox_position_size(renderer)
                box = annotation.get_bbox_patch().get_window_extent(renderer).expanded(1.05, 1.1)
                overlaps = sum(box.overlaps(previous) for previous in occupied)
                outside = not (axis.bbox.contains(box.x0, box.y0) and axis.bbox.contains(box.x1, box.y1))
                penalty = overlaps + 100 * outside
                if best is None or penalty < best[0]:
                    best = (penalty, dx, dy, box)
                if penalty == 0:
                    break
            _, dx, dy, box = best
            annotation.set_position((dx, dy))
            annotation.set_ha('left' if dx > 0 else 'right')
            occupied.append(box)
    return figure, axes
