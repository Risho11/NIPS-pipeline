"""Export notebook-compatible historical context without calling an LLM.

Run: python EVALUATE/export_warm_start.py
In the notebook: export_warm_start(campaign_detailed, output_path)
"""
from pathlib import Path
import json
import pandas as pd
from campaign_trends import DEFAULT_PROPERTIES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / 'data' / 'warm_start' / 'polysulfone_polarclean.csv'
PARAMETERS = ['mixing_temp', 'bath_temp', 'pullcast_speed', 'nitrogen',
              'coupon_to_bath_wait_time', 'nips_bath_wait_time', 'polymer_wt', 'additive_wt']
CONTEXT = ['cosolvent_type', 'nips_bath_solvent', 'nips_bath_solvent_wt_percent',
           'Air Temp Mean', 'Humidity Mean', 'Coupon Temp Mean', 'Coupon Humidity Mean']


def export_warm_start(frame, output_path=DEFAULT_OUTPUT, selection_description='Caller-selected dataframe',
                      *, last_campaign=None, chemistry_verified=False, selection_metadata=None):
    """Serialize exactly the caller's selected rows; never apply extra filters.

    Numeric columns retain full precision. Report fields are rebuilt for AL;
    original aggregate names remain in source_name. last_campaign is metadata.
    """
    data = frame.copy(deep=True)
    data['source_name'] = data['name']
    data['name'] = data['condition']
    data['chemistry'] = data.get('chemistry', 'Polysulfone / PolarClean (inferred)')
    data['validation_status'] = 'unknown; aggregate SD is intra-sample, not independent synthesis validation'
    data['pore_fraction_method'] = 'compression-curve changepoint estimate; dimensionless, not independent porosimetry'
    if 'Toe Subtracted' in data:
        corrected = data['Toe Subtracted'].astype(str).str.lower().eq('true')
        data.loc[corrected, 'pore_fraction_method'] += '; toe-end strain subtracted'
    if 'Toe Fit Mode' in data:
        masked = data['Toe Fit Mode'].eq('masked')
        data.loc[masked, 'pore_fraction_method'] += '; detected toe masked before fitting'
    if 'Toe Shift Policy' in data:
        conditional = data['Toe Shift Policy'].eq('masked_only')
        data.loc[conditional, 'pore_fraction_method'] += '; shift only for retained toe masks'
    for col in ['formatted_parameters', 'formatted_parameters_withProp', 'initial_report',
                'final_report', 'pore_fraction_report']:
        data[col] = ''
    for col in CONTEXT:
        if col not in data:
            data[col] = 'unknown'

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
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False)
    summary = {
        'historical_bath_context': {'policy': 'Preserve notebook-selected bath values; no export-only corrections.'},
        'rows': len(data),
        'last_campaign': last_campaign if last_campaign is not None else (data['campaign'].max() if len(data) else None),
        'excluded_negative_strain_rows': 0,
        'additional_export_filters': False,
        'complete_parameter_rows': int(data[PARAMETERS].notna().all(axis=1).sum()),
        'modulus_rows': int(data['Elastic Modulus Mean'].notna().sum()),
        'paired_objective_rows': int(data[['Elastic Modulus Mean', 'Pore Fraction Mean']].notna().all(axis=1).sum()),
        'campaigns': sorted(data['campaign'].unique().tolist()),
        'selection': selection_description,
        'notebook_selection': selection_metadata,
        'limitations': ([] if chemistry_verified else ['Chemistry is inferred, not verified.']) + ['Pore fraction is a compression-fit estimate.',
                       'Independent synthesis validation status is unknown.',
                       'Notebook filters exclude thin/failed samples: exploration coverage is incomplete.'],
    }
    output_path.with_suffix('.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


def export_notebook_warm_start(frame, notebook_name, *, root=ROOT, settings=None):
    from notebook_selection import NOTEBOOK_OUTPUTS, selection_settings
    if notebook_name not in NOTEBOOK_OUTPUTS:
        raise ValueError(f'Unsupported analysis notebook: {notebook_name}')
    output = Path(root) / 'data' / 'warm_start' / NOTEBOOK_OUTPUTS[notebook_name]
    metadata = {'notebook': 'EVALUATE/' + notebook_name,
                'settings': selection_settings(settings or {})}
    return export_warm_start(
        frame, output,
        selection_description=f'Exact selected rows from {notebook_name}; no additional export filters.',
        chemistry_verified=(notebook_name == 'primospire_nmp_campaign_trends.ipynb'
                            and frame['chemistry'].eq('Primospire / NMP').all()),
        selection_metadata=metadata)


def export_saved_notebook(notebook_name, *, root=ROOT):
    from notebook_selection import load_notebook_selection
    frame, settings = load_notebook_selection(notebook_name, root=root)
    return export_notebook_warm_start(frame, notebook_name, root=root, settings=settings)


if __name__ == '__main__':
    print(json.dumps(export_saved_notebook('campaign_trends.ipynb'), indent=2))
