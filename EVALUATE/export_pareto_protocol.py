"""Freeze the reviewed selection and exact recorded settings for terminal replay."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ['mixing_temp', 'bath_temp', 'pullcast_speed', 'nitrogen',
          'coupon_to_bath_wait_time', 'nips_bath_wait_time', 'polymer_wt', 'additive_wt',
          'polymer_type', 'solvent_type', 'cosolvent_type', 'nips_bath_solvent',
          'nips_bath_solvent_wt_percent']
MATERIALS = FIELDS[8:]


def export():
    batches = {}
    for chemistry in ['psf', 'primospire']:
        source = ROOT / 'docs' / 'pareto_validation' / f'{chemistry}_selected_conditions.csv'
        with source.open(newline='', encoding='utf-8') as handle:
            selections = list(csv.DictReader(handle))
        if len(selections) != 5 or len({row['condition'] for row in selections}) != 5:
            raise ValueError(f'Expected five distinct reviewed conditions in {source}')
        for row in selections:
            original = ROOT / 'data' / 'raw' / row['condition'] / 'params.json'
            recorded = json.loads(original.read_text(encoding='utf-8'))
            # Require original metadata; never infer chemistry from concentrations.
            parameters = {key: recorded[key] for key in FIELDS}
            bath = parameters['nips_bath_solvent_wt_percent']
            batch_id = f'{chemistry}-water' if bath == 0 else f'{chemistry}-bath-{bath:g}wt'
            context = {key: parameters[key] for key in MATERIALS}
            batch = batches.setdefault(batch_id, dict(batch_id=batch_id, material_context=context, conditions=[]))
            if batch['material_context'] != context:
                raise ValueError('A batch cannot change material identities or bath composition')
            batch['conditions'].append(dict(
                validation_id=row['validation_id'], source_condition=row['condition'],
                source_campaign=row['campaign'], source_params=str(original.relative_to(ROOT)).replace('\\', '/'),
                source_params_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
                selection_reason=row['selection_reason'], parameters=parameters))
    plan = dict(schema_version=1, sample_repeats=3, membrane_tests_per_sample=2,
                zero_tests_per_sample=2, compression_test_locations=['coupon test 2', 'coupon test 4'],
                location_basis='Casting-start side; blade X=215 to 110, coupon yaw -90 to +91; fixed-probe coupon poses X=170.',
                batches=list(batches.values()))
    destination = ROOT / 'protocols' / 'pareto_validation_plan.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    setup = {batch_id: dict(material_context=batch['material_context'], stock_metadata=None)
             for batch_id, batch in batches.items()}
    destination.with_name('pareto_validation_setup.template.json').write_text(
        json.dumps(setup, indent=2) + '\n', encoding='utf-8')
    print(f'Frozen plan: {destination}; 10 conditions, 30 samples, 60 membrane + 60 zero curves.')


if __name__ == '__main__':
    export()
