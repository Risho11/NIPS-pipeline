"""Backfill confirmed historical bath context without recomputing measurements.

Run from the repository root: python EVALUATE/backfill_historical_bath_context.py
Only explicit manifest conditions are eligible; nonzero records are preserved.
"""
import csv
import json
import os
import re
from historical_bath_context import ROOT, SOURCE, condition_name, confirmed_conditions, known_nonzero

FIELDS = {'nips_bath_solvent': 'none', 'nips_bath_solvent_wt_percent': '0.0'}
TEXT_FIELDS = ('formatted_parameters', 'formatted_parameters_withProp', 'final_report')


def correct_text(text):
    if not text:
        return text
    for field, value in FIELDS.items():
        pattern = rf'\b{field}=[^;\s,]+'
        if re.search(pattern, text):
            text = re.sub(pattern, f'{field}={value}', text)
        else:
            text += f'; {field}={value}'
    return text


def backfill(path, confirmed):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    changed = 0
    untouched = set(fields) - set(FIELDS) - set(TEXT_FIELDS) - {'bath_context_source'}
    for row in rows:
        name = row.get('condition') or row.get('name', '')
        if condition_name(name) not in confirmed or known_nonzero(row.get('nips_bath_solvent_wt_percent')):
            continue
        original = row.copy()
        row.update(FIELDS)
        row['bath_context_source'] = SOURCE
        for field in TEXT_FIELDS:
            if field in row:
                row[field] = correct_text(row[field])
        assert all(row[k] == original[k] for k in untouched), 'Non-context data changed'
        changed += row != original
    if changed:
        fields += [key for key in (*FIELDS, 'bath_context_source') if key not in fields]
        temporary = path.with_suffix('.csv.tmp')
        with temporary.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    return changed


def main():
    confirmed = confirmed_conditions()
    paths = sorted((ROOT / 'data/warm_start').glob('*.csv'))
    paths += sorted(p for p in (ROOT / 'data/results').glob('*/*.csv')
                    if p.parent.name != 'begins_1999')
    report = {str(p.relative_to(ROOT)): count for p in paths if (count := backfill(p, confirmed))}
    print(json.dumps({'files_changed': len(report), 'rows_changed': sum(report.values()),
                      'files': report}, indent=2))


if __name__ == '__main__':
    main()
