"""Descriptive consistency checks for samples made under similar conditions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform


DEFAULT_TOLERANCES = {
    'coupon_to_bath_wait_time': 10.0,  # seconds
    'bath_temp': 3.0,                 # degrees C
    'pullcast_speed': 3.0,            # mm/s
    'Humidity Mean': 5.0,             # percentage points
}
RESPONSES = ('Elastic Modulus', 'Pore Fraction', 'Yield Strength')


def nitrogen_state(value):
    text = str(value).strip().lower()
    if text in {'true', '1', '1.0', 'yes', 'on'}:
        return 1.0
    if text in {'false', '0', '0.0', 'no', 'off'}:
        return 0.0
    return np.nan


def match_conditions(data, tolerances=None):
    """Return annotated rows and all qualifying pairs, without using responses.

    Polymer concentration and nitrogen state must match exactly. Complete linkage
    limits the entire span of each other variable to its tolerance, preventing
    chains of near neighbors from producing groups with dissimilar endpoints.
    Groups form a deterministic, disjoint partition; qualifying pairs across
    different groups are retained in the pair table. Missing inputs never match.
    """
    tolerances = dict(DEFAULT_TOLERANCES if tolerances is None else tolerances)
    if set(tolerances) != set(DEFAULT_TOLERANCES):
        raise ValueError('Provide tolerances for all four matching variables.')
    if any(not np.isfinite(t) or t < 0 for t in tolerances.values()):
        raise ValueError('Tolerances must be finite and nonnegative.')
    rows = data.sort_values(['sample_time', 'condition']).reset_index(drop=True).copy()
    if 'iteration' not in rows:
        rows['iteration'] = np.arange(1, len(rows) + 1)
    inputs = rows[['polymer_wt'] + list(tolerances)].apply(pd.to_numeric, errors='coerce')
    inputs['nitrogen_state'] = rows['nitrogen'].map(nitrogen_state)
    valid = np.isfinite(inputs.to_numpy(dtype=float)).all(axis=1)
    rows['repeat_group'] = pd.Series(pd.NA, index=rows.index, dtype='object')
    rows['match_status'] = np.where(valid, 'No grouped repeat', 'Missing matching inputs')
    valid_indices = np.flatnonzero(valid)
    values = inputs.loc[valid].reset_index(drop=True)
    count = len(values)
    distances = np.zeros((count, count))
    for column in ['polymer_wt', 'nitrogen_state'] + list(tolerances):
        v = values[column].to_numpy(dtype=float)
        delta = np.abs(v[:, None] - v[None, :])
        tolerance = tolerances.get(column, 0)
        scaled = delta / tolerance if tolerance else np.where(delta == 0, 0., 1e12)
        distances = np.maximum(distances, scaled)
    pairs = []
    for left in range(count):
        for right in range(left + 1, count):
            if distances[left, right] <= 1:
                a, b = rows.iloc[valid_indices[left]], rows.iloc[valid_indices[right]]
                record = {'iteration_a': a['iteration'], 'iteration_b': b['iteration'],
                          'condition_a': a['condition'], 'condition_b': b['condition']}
                record.update({f'{c} difference': abs(values.loc[left, c] - values.loc[right, c])
                               for c in tolerances})
                pairs.append(record)
    if count >= 2:
        clusters = fcluster(linkage(squareform(distances, checks=False), method='complete'),
                            t=1.0, criterion='distance')
        groups = [valid_indices[clusters == label] for label in np.unique(clusters)]
        groups = sorted((g for g in groups if len(g) >= 2), key=lambda g: g[0])
        for number, indices in enumerate(groups, 1):
            rows.loc[indices, 'repeat_group'] = f'G{number}'
            rows.loc[indices, 'match_status'] = 'Grouped repeat'
    pair_columns = ['iteration_a', 'iteration_b', 'condition_a', 'condition_b'] + [
        f'{c} difference' for c in tolerances]
    return rows, pd.DataFrame(pairs, columns=pair_columns)


def summarize_repeats(rows, properties=RESPONSES):
    """Between-sample SD and CV use sample means, never specimen error bars."""
    records = []
    for group, members in rows.dropna(subset=['repeat_group']).groupby('repeat_group', sort=False):
        for prop in properties:
            values = pd.to_numeric(members[f'{prop} Mean'], errors='coerce')
            values = values[np.isfinite(values)]
            mean, sd = values.mean(), values.std(ddof=1)
            records.append({'group': group, 'property': prop, 'n': len(values),
                            'mean': mean, 'between_sample_SD': sd,
                            'CV_percent': 100 * sd / abs(mean) if pd.notna(mean) and mean != 0 else np.nan,
                            'min': values.min(), 'max': values.max()})
    return pd.DataFrame(records, columns=['group', 'property', 'n', 'mean',
                                         'between_sample_SD', 'CV_percent', 'min', 'max'])


def group_conditions(rows, tolerances=None):
    tolerances = DEFAULT_TOLERANCES if tolerances is None else tolerances
    records = []
    for group, members in rows.dropna(subset=['repeat_group']).groupby('repeat_group', sort=False):
        record = {'group': group, 'n': len(members),
                  'iterations': ', '.join(str(int(i)) for i in members['iteration']),
                  'polymer_wt': members['polymer_wt'].iloc[0],
                  'nitrogen': 'On' if nitrogen_state(members['nitrogen'].iloc[0]) else 'Off'}
        for col in tolerances:
            values = pd.to_numeric(members[col], errors='coerce')
            record[col + ' range'] = f'{values.min():g} to {values.max():g}'
        # Report additional process variables without silently imposing extra filters.
        for col in ['mixing_temp', 'nips_bath_wait_time', 'additive_wt']:
            if col in members and col not in tolerances:
                values = pd.to_numeric(members[col], errors='coerce')
                record[col + ' range (not matched)'] = (
                    f'{values.min():g} to {values.max():g}; {values.isna().sum()} missing')
        records.append(record)
    return pd.DataFrame(records)


def plot_repeatability(rows, properties=RESPONSES):
    groups = list(rows.dropna(subset=['repeat_group']).groupby('repeat_group', sort=False))
    if not groups:
        fig, ax = plt.subplots(figsize=(9, 3))
        ax.text(.5, .5, 'No repeat groups at these tolerances.', ha='center', va='center')
        ax.set_axis_off()
        return fig
    fig, axes = plt.subplots(len(groups), len(properties), squeeze=False,
                             figsize=(14, 3.3 * len(groups)), sharey='col')
    summary = summarize_repeats(rows, properties).set_index(['group', 'property'])
    for row_index, (group, members) in enumerate(groups):
        for col_index, prop in enumerate(properties):
            ax = axes[row_index, col_index]
            means = pd.to_numeric(members[f'{prop} Mean'], errors='coerce')
            sd = pd.to_numeric(members[f'{prop} SD'], errors='coerce')
            positions = np.arange(len(members))
            valid = np.isfinite(means)
            errors = valid & np.isfinite(sd) & (sd >= 0)
            ax.scatter(positions[valid], means[valid], color='#1f77b4', zorder=3)
            ax.errorbar(positions[errors], means[errors], yerr=sd[errors], fmt='none',
                        ecolor='#1f77b4', capsize=4, zorder=2)
            stats = summary.loc[(group, prop)]
            if stats['n']:
                ax.axhline(stats['mean'], color='0.35', ls='--', lw=1)
            cv = f"{stats['CV_percent']:.1f}%" if pd.notna(stats['CV_percent']) else 'NA'
            ax.set_title(f"{group} | {prop}\nn={int(stats['n'])}; between-sample CV={cv}")
            ax.set_xticks(positions)
            ax.set_xticklabels([f'I{int(i)}' for i in members['iteration']], rotation=45, ha='right')
            ax.set_ylabel('' if prop == 'Pore Fraction' else 'bar')
            ax.set_xlabel('Campaign iteration')
            ax.grid(axis='y', alpha=.2)
    fig.suptitle('Consistency within matched conditions', fontsize=16)
    fig.text(.5, .01, 'Points: sample means; bars: intra-sample SD when available; '
             'dashed line: group mean. CV measures variation between sample means.',
             ha='center', fontsize=10)
    fig.tight_layout(rect=(0, .045, 1, .96))
    return fig


def plot_repeatability_boxes(rows, properties=RESPONSES, seed=42):
    """All groups in one figure; boxes and jitter summarize sample means."""
    groups = list(rows.dropna(subset=['repeat_group']).groupby('repeat_group', sort=False))
    if not groups:
        fig, ax = plt.subplots(figsize=(9, 3))
        ax.text(.5, .5, 'No repeat groups at these tolerances.', ha='center', va='center')
        ax.set_axis_off()
        return fig

    def value_range(members, column):
        if column not in members:
            return 'NA'
        values = pd.to_numeric(members[column], errors='coerce')
        values = values[np.isfinite(values)]
        if values.empty:
            return 'NA'
        low, high = values.min(), values.max()
        fmt = lambda value: f'{value:.2f}'.rstrip('0').rstrip('.')
        result = fmt(low) if low == high else f'{fmt(low)}\u2013{fmt(high)}'
        return result + (' (missing)' if len(values) < len(members) else '')

    fig, grid = plt.subplots(1, len(properties), squeeze=False, sharey=True,
                             figsize=(20, 9))  # Short, wide layout for a slide.
    axes = grid[0]
    rng = np.random.default_rng(seed)
    labels = []
    max_rank = max(len(members) for _, members in groups)
    color_map = plt.get_cmap('viridis', max_rank)
    normalization = plt.matplotlib.colors.BoundaryNorm(
        np.arange(0.5, max_rank + 1.5), color_map.N)

    for position, (group, members) in enumerate(groups, 1):
        members = members.sort_values(['sample_time', 'iteration', 'condition'])
        span = lambda column: value_range(members, column)
        nitrogen = 'on' if nitrogen_state(members['nitrogen'].iloc[0]) else 'off'
        labels.append(
            f"{group} (n={len(members)}) | Polymer {span('polymer_wt')} wt%; N2 {nitrogen}\n"
            f"Exposure {span('coupon_to_bath_wait_time')} s; Bath {span('bath_temp')} \N{DEGREE SIGN}C\n"
            f"Casting {span('pullcast_speed')} mm/s; RH {span('Humidity Mean')}%"
        )
        # Use the same offsets in each response panel to help follow observations.
        offsets = rng.uniform(-.16, .16, len(members))
        color = '#888888'
        # Rank all group members before omitting missing responses, keeping colors
        # consistent for a sample across panels. Equal timestamps use iteration/ID.
        ranks = np.arange(1, len(members) + 1)
        for ax, prop in zip(axes, properties):
            values = pd.to_numeric(members[f'{prop} Mean'], errors='coerce').to_numpy()
            valid = np.isfinite(values)
            if valid.any():
                ax.boxplot([values[valid]], positions=[position], vert=False, widths=.5,
                           patch_artist=True, showfliers=False, manage_ticks=False,
                           boxprops={'facecolor': color, 'alpha': .22, 'edgecolor': color},
                           medianprops={'color': 'black', 'linewidth': 1.5},
                           whiskerprops={'color': color}, capprops={'color': color})
                ax.scatter(values[valid], position + offsets[valid], s=55, c=ranks[valid],
                           cmap=color_map, norm=normalization, edgecolor='#444444', linewidth=.6, zorder=3)
            else:
                ax.text(.5, position, 'No data', transform=ax.get_yaxis_transform(),
                        ha='center', va='center', color='0.5')
    axes[0].set_yticks(np.arange(1, len(groups) + 1))
    axes[0].set_yticklabels(labels, fontsize=12, linespacing=1.25)
    axes[0].set_ylim(len(groups) + .65, .35)
    for ax, prop in zip(axes, properties):
        ax.set_title(prop, fontsize=18, pad=14)
        ax.set_xlabel('' if prop == 'Pore Fraction' else 'bar', fontsize=15)
        ax.tick_params(axis='x', labelsize=13)
        ax.tick_params(axis='y', length=0)
        ax.grid(axis='x', alpha=.2)
        for boundary in np.arange(1.5, len(groups), 1):
            ax.axhline(boundary, color='0.92', lw=.8, zorder=0)
    fig.subplots_adjust(left=.31, right=.92, bottom=.09, top=.94, wspace=.20)
    colorbar_axis = fig.add_axes([.945, .17, .012, .68])
    colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=normalization, cmap=color_map),
                            cax=colorbar_axis, ticks=np.arange(1, max_rank + 1))
    colorbar.set_label('Chronological rank within group (1 = earliest)', fontsize=14, labelpad=12)
    colorbar.ax.tick_params(labelsize=12)
    return fig
