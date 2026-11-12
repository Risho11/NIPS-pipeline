"""Descriptive, repeat-aware prioritization; no predicted outcomes or hardware I/O."""

import json

import numpy as np
import pandas as pd

from campaign_trends import DEFAULT_RAW_ROOT, load_campaign_data
from pareto_reproduction import FIELDS, canonical, recipe

PROPERTIES = ['Elastic Modulus', 'Pore Fraction']
PROCESS = [key for key in FIELDS if key not in {'polymer_type', 'solvent_type'}]


def recorded_settings(history):
    settings = {}
    for _, row in history.iterrows():
        values = row.to_dict()
        path = DEFAULT_RAW_ROOT / row.condition / 'params.json'
        if path.exists():
            values.update(json.loads(path.read_text(encoding='utf-8')))
        settings[row.condition] = {key: canonical(key, values.get(key)) for key in FIELDS}
    return settings


def matching_settings(target, candidate, target_name, candidate_name):
    # Never merge across unknown chemistry just because a numeric recipe matches.
    for key in FIELDS:
        left, right = target[key], candidate[key]
        if key in PROCESS and (left is None or right is None):
            return False
        if left is not None and right is not None and left != right:
            return False
    chemistry_known = all(target[key] is not None and candidate[key] is not None
                          for key in ['polymer_type', 'solvent_type'])
    return chemistry_known or recipe(target_name) == recipe(candidate_name)


def assess_candidates(data, history=None):
    """Eligible representatives; repeat statistics include poor historical repeats."""
    history = load_campaign_data() if history is None else history.copy()
    settings = recorded_settings(history)
    candidates = []
    seen = set()
    ordered = data.sort_values(['campaign', 'condition'], kind='stable')
    for _, source in ordered.iterrows():
        if source.condition in seen:
            continue
        target = settings[source.condition]
        if any(target[key] is None for key in PROCESS):
            continue
        names = [name for name, values in settings.items()
                 if matching_settings(target, values, source.condition, name)]
        seen.update(names)
        raw_names = [name for name in names
                     if next((DEFAULT_RAW_ROOT / name).glob('Specimen_*.csv'), None) is not None]
        members = history[history.condition.isin(raw_names)].copy()
        values = members[[prop + ' Mean' for prop in PROPERTIES]].apply(pd.to_numeric, errors='coerce')
        paired = (np.isfinite(values).all(axis=1)
                  & (values['Elastic Modulus Mean'] > 0)
                  & values['Pore Fraction Mean'].between(0, 1))
        if not paired.any():
            continue
        paired_values = values.loc[paired]
        medians = paired_values.median()
        # Show an actual eligible sample nearest the recipe's typical observed response.
        eligible = ordered[ordered.condition.isin(names)].copy()
        observed = eligible[medians.index].apply(pd.to_numeric, errors='coerce')
        finite = np.isfinite(observed).all(axis=1)
        eligible, observed = eligible.loc[finite], observed.loc[finite]
        if eligible.empty:
            continue
        distance = ((observed - medians) / medians.abs().replace(0, 1)).pow(2).sum(axis=1)
        representative = eligible.loc[distance.idxmin()].copy()
        representative['historical_samples'] = len(members)
        representative['paired_samples'] = int(paired.sum())
        representative['paired_fraction'] = float(paired.mean())
        representative['repeat_conditions'] = '; '.join(members.condition)
        for prop in PROPERTIES:
            v = paired_values[prop + ' Mean']
            representative[prop + ' median'] = v.median()
            representative[prop + ' q25'] = v.quantile(.25)
            representative[prop + ' between CV %'] = 100 * v.std(ddof=1) / abs(v.mean()) if len(v) > 1 and v.mean() != 0 else np.nan
        cv = [representative[prop + ' between CV %'] for prop in PROPERTIES]
        representative['repeat_supported'] = bool(
            paired.sum() >= 3 and paired.mean() >= .75 and all(np.isfinite(c) and c <= 25 for c in cv))
        representative['chemistry_recorded'] = all(target[key] is not None for key in ['polymer_type', 'solvent_type'])
        candidates.append(representative)
    if not candidates:
        raise ValueError('No eligible conditions with recorded process settings and raw measurements')
    return pd.DataFrame(candidates).reset_index(drop=True)


def choose_candidates(candidates, count=5):
    """Balance observed performance, repeat evidence, and response-space coverage."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 2:
        raise ValueError('count must be an integer of at least two')
    table = candidates.copy().reset_index(drop=True)
    if len(table) < count:
        raise ValueError(f'Only {len(table)} assessed recipes; requested {count}')
    medians = table[[prop + ' median' for prop in PROPERTIES]].to_numpy(float)
    low, span = medians.min(axis=0), np.ptp(medians, axis=0)
    span = np.where(span > 0, span, 1)
    normalized = (medians - low) / span
    q25 = (table[[prop + ' q25' for prop in PROPERTIES]].to_numpy(float) - low) / span
    cvs = table[[prop + ' between CV %' for prop in PROPERTIES]].max(axis=1).fillna(50).to_numpy() / 100
    table['selection_eligible'] = ((table.paired_fraction >= .75)
                                   & ((table.paired_samples == 1) | (cvs <= .5)))
    if table.selection_eligible.sum() < count:
        raise ValueError('Not enough candidates with >=75% paired coverage and <=50% observed CV')
    # Utility is a transparent prioritization heuristic, never a material prediction.
    evidence = np.where(table.paired_samples >= 3, 1., np.where(table.paired_samples == 2, .85, .65))
    reliability = evidence * table.paired_fraction.to_numpy() / (1 + cvs)
    performance = .5 * normalized.sum(axis=1) + .5 * np.clip(q25, 0, 1).sum(axis=1)
    table['selection_utility'] = performance * reliability
    table['median_pareto'] = [not (np.all(medians >= p, axis=1) & np.any(medians > p, axis=1)).any() for p in medians]
    selected, roles = [], []

    def take(pool, scores, role):
        available = [i for i in pool if i not in selected]
        if available and len(selected) < count:
            index = max(available, key=lambda i: (scores[i], -i))
            selected.append(index)
            roles.append(role)

    supported = table.index[table.repeat_supported & table.selection_eligible].tolist()
    # Up to three reproducibility anchors: modulus, pore fraction, balanced response.
    take(supported, normalized[:, 0], 'Repeat-supported modulus anchor')
    take(supported, normalized[:, 1], 'Repeat-supported pore-fraction anchor')
    take(supported, table.selection_utility.to_numpy(), 'Repeat-supported balanced candidate')
    # One informative validation opportunity with encouraging but limited repeats.
    limited = table.index[(table.paired_samples <= 2) & table.selection_eligible].tolist()
    if selected:
        distance = np.min(np.linalg.norm(normalized[:, None] - normalized[selected][None, :], axis=2), axis=1)
    else:
        distance = np.zeros(len(table))
    take(limited, table.selection_utility.to_numpy() * (1 + distance),
         'Promising limited-repeat validation opportunity')
    # Remaining slots favor promising candidates that add response-space coverage.
    while len(selected) < min(count, len(table)):
        distance = (np.min(np.linalg.norm(normalized[:, None] - normalized[selected][None, :], axis=2), axis=1)
                    if selected else np.zeros(len(table)))
        scores = table.selection_utility.to_numpy() * (1 + distance)
        before = len(selected)
        take(table.index[table.selection_eligible], scores, 'Promising candidate adding tradeoff coverage')
        if len(selected) == before:
            break
    chosen = table.loc[selected].copy()
    chosen['selection_reason'] = roles
    contrast_fields = [key for key in PROCESS if key not in
                       {'nips_bath_solvent', 'nips_bath_solvent_wt_percent'}]
    for index, row in chosen.iterrows():
        for other_index, other in chosen.iterrows():
            if index == other_index:
                continue
            if (canonical('nips_bath_solvent_wt_percent', row.get('nips_bath_solvent_wt_percent')) !=
                    canonical('nips_bath_solvent_wt_percent', other.get('nips_bath_solvent_wt_percent'))
                    and all(canonical(key, row.get(key)) is not None and
                            canonical(key, row.get(key)) == canonical(key, other.get(key))
                            for key in contrast_fields)):
                chosen.loc[index, 'selection_reason'] += '; matched process contrast in bath-solvent content'
                break
    chosen = chosen.sort_values('Pore Fraction median', kind='stable')
    chosen.insert(0, 'validation_id', [f'V{i + 1}' for i in range(len(chosen))])
    chosen['sample_repeats'] = 3
    chosen['compression_tests_per_sample'] = 2
    return chosen, table
