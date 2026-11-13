"""Audit independent historical samples without filtering away failed repeats."""

import html
import json
import re

import numpy as np
import pandas as pd

from campaign_trends import load_campaign_data, DEFAULT_RAW_ROOT
from campaign_repeatability import nitrogen_state

FIELDS = ['polymer_type', 'solvent_type', 'polymer_wt', 'additive_wt',
          'mixing_temp', 'bath_temp', 'pullcast_speed', 'nitrogen',
          'coupon_to_bath_wait_time', 'nips_bath_wait_time', 'cosolvent_type',
          'nips_bath_solvent', 'nips_bath_solvent_wt_percent']
TEXT = {'polymer_type', 'solvent_type', 'cosolvent_type', 'nips_bath_solvent'}


def recipe(condition):
    return re.sub(r'_run\d+$', '', str(condition))


def canonical(key, value):
    if value is None or pd.isna(value) or str(value).strip() == '':
        return None
    if key == 'nitrogen':
        value = nitrogen_state(value)
    if key in TEXT:
        return str(value).strip().lower()
    value = pd.to_numeric(value, errors='coerce')
    return float(value) if np.isfinite(value) else None


def audit(selections, output_dir):
    history = load_campaign_data()
    settings = {}
    for _, row in history.iterrows():
        recorded = row.to_dict()
        path = DEFAULT_RAW_ROOT / row.condition / 'params.json'
        if path.exists():
            recorded.update(json.loads(path.read_text(encoding='utf-8')))
        settings[row.condition] = {key: canonical(key, recorded.get(key)) for key in FIELDS}
    records, summaries = [], []
    for selection in selections:
        condition = selection['condition']
        target = settings[condition]
        members = []
        for _, row in history.iterrows():
            candidate = settings[row.condition]
            missing = [key for key in FIELDS if target[key] is None or candidate[key] is None]
            different = [key for key in FIELDS if target[key] is not None
                         and candidate[key] is not None and target[key] != candidate[key]]
            exact = not missing and not different
            process_match = not different and not (set(missing) - {'polymer_type', 'solvent_type'})
            family = recipe(row.condition) == recipe(condition)
            process_match = process_match and (exact or family)
            if not process_match and not family:
                continue
            raw_files = list((DEFAULT_RAW_ROOT / row.condition).glob('Specimen_*.csv'))
            record = dict(chemistry=selection['chemistry'], validation_id=selection['validation_id'],
                          selected_condition=condition, condition=row.condition, campaign=row.campaign,
                          sample_time=row.sample_time, selected=row.condition == condition,
                          match='exact recorded settings' if exact else 'matching process; chemistry incomplete' if process_match else 'different settings' if different else 'incomplete settings',
                          mismatched_fields=', '.join(different), missing_fields=', '.join(missing),
                          raw_specimens=len(raw_files))
            for key in ['Elastic Modulus Mean', 'Pore Fraction Mean', 'CV PreDiscard Mean',
                        'Discarded Fit Reasons', 'Humidity Mean', 'Air Temp Mean']:
                record[key] = row.get(key)
            records.append(record)
            if process_match and raw_files:
                members.append(record)
        repeats = pd.DataFrame(members)
        summary = dict(chemistry=selection['chemistry'], validation_id=selection['validation_id'],
                       selected_condition=condition, matching_process_samples_with_raw_data=len(members),
                       chemistry_confirmed_samples=sum(r['match'] == 'exact recorded settings' for r in members),
                       additional_samples=sum(not r['selected'] for r in members))
        for prop in ['Elastic Modulus', 'Pore Fraction']:
            values = pd.to_numeric(repeats.get(prop + ' Mean', pd.Series(dtype=float)), errors='coerce')
            values = values[np.isfinite(values)]
            summary[prop + ' n'] = len(values)
            summary[prop + ' range'] = f'{values.min():.4g}–{values.max():.4g}' if len(values) else 'unavailable'
            summary[prop + ' CV %'] = 100 * values.std(ddof=1) / abs(values.mean()) if len(values) > 1 and values.mean() != 0 else np.nan
        summaries.append(summary)
    summary = pd.DataFrame(summaries)
    details = pd.DataFrame(records)
    summary.to_csv(output_dir / 'reproduction_summary.csv', index=False)
    details.to_csv(output_dir / 'reproduction_samples.csv', index=False)
    print(summary.to_string(index=False))
    description = ('Counts include the selected sample and other separately named samples with raw specimen files '
                   'and exactly matching recorded formulation, mixing, casting, exposure, and bath settings. '
                   'Chemistry-confirmed counts additionally require matching recorded polymer and solvent identities. '
                   'Missing historical chemistry labels are reported, not inferred as confirmed. '
                   'Raw params.json takes precedence over aggregate metadata. Missing settings cannot establish an exact repeat. '
                   'All historical aggregates are searched without the notebook quality filters so poor repeats are retained. '
                   'Repeated processing rows are deduplicated; compression curves within a sample do not count as synthesis repeats. '
                   'Stock age and ambient conditions may differ. Separate sample records support repeat attempts, '
                   'but do not independently prove fresh synthesis. Ranges and CVs describe between-sample means; '
                   'repeat counts alone do not establish reproducible performance. No acceptance tolerance has been imposed.')
    return ('<section id="reproduction-audit" style="padding:20px;overflow-x:auto">'
            '<h2>Historical reproduction audit</h2><p>' + html.escape(description) + '</p>'
            + summary.to_html(index=False, na_rep='—', float_format=lambda value: f'{value:.1f}')
            + '<details><summary>All candidate sample records, including settings mismatches</summary>'
            + details.to_html(index=False, na_rep='—') + '</details></section>')
