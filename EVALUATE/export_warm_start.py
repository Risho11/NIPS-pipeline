"""Export notebook-compatible historical context without calling an LLM.

Run: python EVALUATE/export_warm_start.py
In the notebook: export_warm_start(campaign_detailed, output_path)
"""
from pathlib import Path
import json
import pandas as pd
from campaign_trends import load_campaign_data, DEFAULT_PROPERTIES, POLARCLEAN_LAST_CAMPAIGN

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'data' / 'warm_start' / 'polysulfone_polarclean.csv'
PARAMETERS = ['mixing_temp', 'bath_temp', 'pullcast_speed', 'nitrogen',
              'coupon_to_bath_wait_time', 'nips_bath_wait_time', 'polymer_wt', 'additive_wt']
CONTEXT = ['cosolvent_type', 'nips_bath_solvent', 'nips_bath_solvent_wt_percent',
           'Air Temp Mean', 'Humidity Mean', 'Coupon Temp Mean', 'Coupon Humidity Mean']


def export_warm_start(frame, output_path=DEFAULT_OUTPUT, selection_description='Caller-selected dataframe'):
    """Export selected aggregate rows; retain failures as unknown-outcome history."""
    data = frame.copy()
    data = data[data['campaign'] <= POLARCLEAN_LAST_CAMPAIGN].copy()
    data = data.drop_duplicates('condition', keep='last').sort_values('sample_time')
    # Negative strain at 50 bar indicates an artifact; retain unknown outcomes.
    strain_50 = pd.to_numeric(data['Strain at 50 bar Mean'], errors='coerce')
    excluded_negative_strain_rows = int((strain_50 < 0).sum())
    data = data[~(strain_50 < 0)].copy()
    data['source_name'] = data['name']
    data['name'] = data['condition']
    data['chemistry'] = data.get('chemistry', 'Polysulfone / PolarClean (inferred)')
    data['validation_status'] = 'unknown; aggregate SD is intra-sample, not independent synthesis validation'
    data['pore_fraction_method'] = 'compression-curve changepoint estimate; dimensionless, not independent porosimetry'
    for col in ['formatted_parameters', 'formatted_parameters_withProp', 'initial_report',
                'final_report', 'pore_fraction_report']:
        data[col] = ''
    for col in CONTEXT:
        if col not in data:
            data[col] = 'unknown'
        data[col] = data[col].fillna('unknown')

    def value(row, key):
        v = row.get(key)
        return 'unknown' if pd.isna(v) else str(v)

    for idx, row in data.iterrows():
        params = '; '.join(f'{key}={value(row, key)}' for key in PARAMETERS + CONTEXT)
        properties = '; '.join(
            f'{prop}: mean={value(row, prop + " Mean")}, SD={value(row, prop + " SD")}'
            for prop in DEFAULT_PROPERTIES
        )
        report = (
            f'[{row["name"]}] Historical observation; chemistry={row["chemistry"]}; '
            f'campaign={row["campaign"]}; sample_time={row["sample_time"]}. {params}. '
            f'{properties}. Modulus and yield strength units: bar; thickness: micrometers; '
            'pore fraction and strains: dimensionless. '
            f'CV Mean={value(row, "CV Mean")}; '
            f'Discarded Fit Quality Mean={value(row, "Discarded Fit Quality Mean")}; '
            f'Discarded Fit Reasons={value(row, "Discarded Fit Reasons")}. '
            f'{row["validation_status"]}. Pore fraction method: {row["pore_fraction_method"]}. '
            'Historical parameters may be outside current bounds; use current bounds for suggestions.'
        )
        data.at[idx, 'formatted_parameters'] = params
        data.at[idx, 'formatted_parameters_withProp'] = params + '\n' + properties
        data.at[idx, 'initial_report'] = ''
        data.at[idx, 'final_report'] = report
        data.at[idx, 'pore_fraction_report'] = (
            f'Pore Fraction mean={value(row, "Pore Fraction Mean")}, '
            f'SD={value(row, "Pore Fraction SD")}; {row["pore_fraction_method"]}'
        )
    data = data.drop(columns=[c for c in data if c.endswith('_result') or c == 'LLM_suggestion'])
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False)
    summary = {
        'rows': len(data),
        'last_campaign': POLARCLEAN_LAST_CAMPAIGN,
        'excluded_negative_strain_rows': excluded_negative_strain_rows,
        'complete_parameter_rows': int(data[PARAMETERS].notna().all(axis=1).sum()),
        'modulus_rows': int(data['Elastic Modulus Mean'].notna().sum()),
        'paired_objective_rows': int(data[['Elastic Modulus Mean', 'Pore Fraction Mean']].notna().all(axis=1).sum()),
        'campaigns': sorted(data['campaign'].unique().tolist()),
        'selection': selection_description,
        'limitations': ['Chemistry is inferred, not verified.', 'Pore fraction is a compression-fit estimate.',
                       'Independent synthesis validation status is unknown.',
                       'Notebook filters exclude thin/failed samples: exploration coverage is incomplete.'],
    }
    output_path.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    data = load_campaign_data(last_campaign=POLARCLEAN_LAST_CAMPAIGN)
    polymer = pd.to_numeric(data['polymer_wt'], errors='coerce')
    # Match the current notebook's Polysulfone/PolarClean selection and quality filters.
    selected = data[
        polymer.between(13, 17)
        & ~data['condition'].astype(str).str.startswith('21-')
        & (pd.to_numeric(data['Thickness Mean'], errors='coerce') >= 70)
        & data[[p + ' Mean' for p in DEFAULT_PROPERTIES]].notna().any(axis=1)
    ].copy()
    print(json.dumps(export_warm_start(selected, selection_description=
        'Notebook defaults: through 2026-08-22-exploration-mode inclusive; inferred Polysulfone/PolarClean; thickness >= 70 um; polymer >= 13 wt%; at least one property present; negative strain at 50 bar excluded.'), indent=2))
