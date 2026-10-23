"""Operator-confirmed zero-solvent history, scoped to explicit condition names."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/warm_start/historical_zero_bath_conditions.json'
SOURCE = 'operator-confirmed 2026-10-23: historical NIPS baths contained 0 wt% solvent'


def condition_name(value):
    name = str(value).split(' | rep ', 1)[0].strip()
    return re.sub(r'_(?:preDiscard|postDiscard)$', '', name)


def confirmed_conditions():
    return set(json.loads(MANIFEST.read_text(encoding='utf-8'))['conditions'])


def known_nonzero(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def apply_historical_bath_context(frame):
    """Return a copy; never infer bath composition for new/unlisted conditions."""
    data = frame.copy()
    names = data['condition'] if 'condition' in data else data['name']
    mask = names.map(condition_name).isin(confirmed_conditions())
    if 'nips_bath_solvent_wt_percent' in data:
        mask &= ~data['nips_bath_solvent_wt_percent'].map(known_nonzero)
    for field, value in [('nips_bath_solvent', 'none'),
                         ('nips_bath_solvent_wt_percent', 0.0),
                         ('bath_context_source', SOURCE)]:
        if field not in data:
            data[field] = None
        data[field] = data[field].astype(object)
        data.loc[mask, field] = value
    return data
