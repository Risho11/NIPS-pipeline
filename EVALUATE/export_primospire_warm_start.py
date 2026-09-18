"""Export Primospire/NMP history using primospire_nmp_campaign_trends.ipynb filters.

Run from any directory: python EVALUATE/export_primospire_warm_start.py
Source aggregate and replicate CSVs are read-only.
"""
import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd

from campaign_trends import DEFAULT_PROPERTIES, load_campaign_data
from export_warm_start import export_warm_start

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = '2026-09-10-exploration-mode'
DEFAULT_OUTPUT = ROOT / 'data' / 'warm_start' / 'primospire_nmp.csv'


def select_primospire_campaign(root=ROOT):
    """Match the notebook's source selection, deduplication, and quality filters."""
    root = Path(root)
    source = root / 'data' / 'results' / ('begins_' + CAMPAIGN)
    # Restrict sources before deduplication, just as in the notebook.
    with tempfile.TemporaryDirectory() as selected_root:
        folder = Path(selected_root) / source.name
        folder.mkdir()
        shutil.copyfile(source / 'agg.csv', folder / 'agg.csv')
        data = load_campaign_data(selected_root, root / 'data' / 'raw')
    data['source_csv'] = str(source / 'agg.csv')
    chemistry = (data['polymer_type'].astype(str).str.strip().str.lower().eq('primospire')
                 & data['solvent_type'].astype(str).str.strip().str.lower().eq('nmp'))
    data = data.loc[
        chemistry
        & data[[p + ' Mean' for p in DEFAULT_PROPERTIES]].notna().any(axis=1)
        & (pd.to_numeric(data['Thickness Mean'], errors='coerce') >= 70)
    ].copy()
    reps = pd.read_csv(source / 'reps.csv')
    reps['condition'] = reps['name'].map(lambda name: str(name).split(' | rep ', 1)[0].strip())
    rep_strain = pd.to_numeric(reps['Strain at 50 bar'], errors='coerce')
    invalid_conditions = reps.loc[~rep_strain.between(0, 1), 'condition']
    strain = pd.to_numeric(data['Strain at 50 bar Mean'], errors='coerce')
    data = data.loc[strain.between(0, 1) & ~data['condition'].isin(invalid_conditions)].copy()
    data['chemistry'] = 'Primospire / NMP'
    return data


def main():
    selected = select_primospire_campaign()
    summary = export_warm_start(
        selected, DEFAULT_OUTPUT,
        selection_description=(
            'Primospire/NMP notebook defaults: campaign 2026-09-10-exploration-mode only; '
            'recorded polymer_type=Primospire and solvent_type=NMP; thickness >= 70 um; '
            'at least one selected property present; mean and every recorded replicate strain '
            'at 50 bar finite and within [0, 1]; missing/out-of-range strains exclude the '
            'whole condition; no polymer concentration filter. Prefer postDiscard aggregates '
            'and newest processing record per condition, ordered by sample time.'
        ),
        last_campaign=CAMPAIGN, chemistry_verified=True,
    )
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
