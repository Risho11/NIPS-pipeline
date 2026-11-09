"""Rebuild historical fits and both plot views from immutable raw curves.

Run: .venv-analysis/Scripts/python.exe EVALUATE/reprocess_toe.py
Use --fit-mode legacy --activate to restore cached previous fits, --resume to
skip completed conditions, or --condition NAME for an isolated preview. CSVs are
backed up once in data/toe_reprocessing/originals before any updates.
"""
import argparse
import contextlib
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sys

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'pipeline'))
sys.path.insert(0, str(ROOT))
import curve_segmentation as processing
from EVALUATE import generate_fit_log as report


def combine_condition_results(work, filename, keys):
    """Replace whole conditions, including obsolete pre/post-discard row names."""
    work = Path(work)
    parts = []
    replaced = set()
    def condition(name):
        return re.sub(r'_(pre|post)Discard$', '', str(name).split(' | ', 1)[0])
    for path in sorted((work / 'conditions').glob('*/' + filename)):
        part = pd.read_csv(path)
        replaced.update(part['name'].map(condition))
        for metadata in ('condition.json', 'skipped.json'):
            meta = path.parent / metadata
            if meta.exists():
                replaced.add(json.loads(meta.read_text())['condition'])
        parts.append(part)
    canonical = work / filename
    if canonical.exists():
        previous = pd.read_csv(canonical)
        previous = previous.loc[~previous['name'].map(condition).isin(replaced)]
        parts.insert(0, previous)
    if not parts:
        raise ValueError(f'No results found for {filename}')
    return pd.concat(parts, ignore_index=True).drop_duplicates(keys, keep='last')


def update_pore_columns(path, source, replicate=False, full_fit=False):
    """Preserve historical metadata/reports and replace numeric pore estimates."""
    try:
        old = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return
    if 'name' not in old:
        return
    keys = ['name', 'Trial'] if replicate else ['name']
    cols = ([c for c in ['Pore Fraction', 'Pore Fraction Unsubtracted', 'Toe Region', 'Toe Subtracted'] if c in source]
            if replicate else [c for c in source if c.startswith('Pore Fraction ') or c == 'Toe Subtracted'])
    if full_fit:
        if replicate:
            fields = set(processing.MECH_PROP_SCHEMA) | {
                'Toe Region', 'Toe Subtracted', 'Toe Fit Mode', 'Good Fit', 'Good Fit Score',
                'Toe Masked', 'Toe Mask Cutoff', 'Toe Shift', 'Toe Shift Policy',
                'Good Fit Breakdown', 'Average Standard Deviation'}
            cols = [c for c in source if c in fields]
        else:
            cols = [c for c in source if c.endswith((' Mean', ' SD')) or c in {
                'Toe Subtracted', 'Toe Fit Mode', 'Toe Shift Policy', 'Discarded Fit Reasons', 'formatted_parameters_withProp'}]
    if not replicate:
        # Promoted rows use the bare name even when the source has pre/post rows.
        source = source.copy()
        aliases = source[source['name'].str.endswith('_postDiscard')].copy()
        aliases['name'] = aliases['name'].str.removesuffix('_postDiscard')
        source = pd.concat([source, aliases], ignore_index=True)
    lookup = source.drop_duplicates(keys, keep='last').set_index(keys)
    matched = False
    for col in cols:
        if col not in old:
            old[col] = pd.Series([None] * len(old), dtype=object) if col in {
                'Toe Subtracted', 'Toe Masked', 'Toe Fit Mode', 'Toe Shift Policy', 'Good Fit Breakdown', 'Discarded Fit Reasons',
                'formatted_parameters_withProp'} else np.nan
    for idx, row in old.iterrows():
        key = tuple(row[k] for k in keys) if replicate else row['name']
        if not replicate and key not in lookup.index:
            base = re.sub(r'_(pre|post)Discard$', '', key)
            if base in lookup.index:
                key = base
        if key in lookup.index:
            matched = True
            for col in cols:
                old.at[idx, col] = lookup.loc[key, col]
            if not replicate:
                for col in ('formatted_parameters_withProp', 'final_report', 'pore_fraction_report'):
                    if col not in old or not isinstance(row.get(col), str):
                        continue
                    text = old.at[idx, col]
                    for stat in ('Mean', 'SD'):
                        value = lookup.loc[key].get('Pore Fraction ' + stat, np.nan)
                        text = re.sub(r'([\"\']?Pore Fraction ' + stat + r'[\"\']?\s*:\s*[\"\']?)(?:[-+\deE.]+|NaN|nan|null)',
                                      lambda m: m[1] + (str(value) if pd.notna(value) else 'null'), text)
                    old.at[idx, col] = text
    if matched:
        old.to_csv(path, index=False)


def process_condition(condition, work, subtract, mask=True, plot_leaf=None, masked_only=True):
    processing.SUBTRACT_TOE = subtract
    processing.MASK_TOE_BEFORE_FIT = mask
    processing.SHIFT_ONLY_MASKED_TOE = masked_only
    leaf = plot_leaf or (('test-toe-masked' if mask else 'test-toe') + ('' if subtract else '-unsubtracted'))
    processing._prefix = 'pseudo-runs/' + leaf
    processing._SAVE_PREFIX_LEAF = leaf
    processing.SAVE_ROOT = ROOT / 'data' / 'plots' / 'pseudo-runs' / leaf
    seed = int(hashlib.sha256(condition.encode()).hexdigest()[:8], 16)
    np.random.seed(seed)
    dest = Path(work) / 'conditions' / hashlib.sha256(condition.encode()).hexdigest()[:16]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'condition.json').write_text(json.dumps({'condition': condition}))
    with (dest / 'processing.log').open('w', encoding='utf-8', buffering=1) as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        output = processing.process_zero_sample_pairs_pipeline(
            'data/raw', data_root=str(ROOT), strict=False,
            thickness_info=False, cutoff_load_thickness=3,
            cutoff_load_displacement=2, condition_filter=[condition])
        # Each worker writes isolated CSVs; the parent combines them after completion.
        for filename in ('reps.csv', 'agg.csv'):
            path = dest / filename
            if path.exists():
                path.unlink()
        processing.save_to_csv(output, data_root=ROOT,
                               output_path=dest / 'reps.csv', aggregate_path=dest / 'agg.csv')
    if not (dest / 'reps.csv').exists():
        (dest / 'skipped.json').write_text(json.dumps({
            'condition': condition, 'reason': 'No paired specimens passed raw preprocessing; no pore fraction is available.'
        }, indent=2))
        pd.DataFrame(columns=['name', 'Trial', 'Pore Fraction', 'Pore Fraction Unsubtracted', 'Toe Region', 'Good Fit',
                              'Toe Masked', 'Toe Mask Cutoff', 'Toe Shift']).to_csv(dest / 'reps.csv', index=False)
        pd.DataFrame(columns=['name', 'Pore Fraction Mean', 'Pore Fraction SD']).to_csv(dest / 'agg.csv', index=False)
    return condition


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unsubtracted', action='store_true')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--condition')
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--fit-mode', choices=['masked', 'legacy'],
                        default='masked' if processing.MASK_TOE_BEFORE_FIT else 'legacy',
                        help='Mask every detected toe before fitting, or restore the previous fitting method.')
    parser.add_argument('--activate', action='store_true',
                        help='Publish cached results and plots for this mode without refitting.')
    parser.add_argument('--toe-policy', choices=['masked-only', 'all-detected'],
                        help='Default: shift only committed masks for legacy fits; all detected toes for masked fits.')
    parser.add_argument('--cleanup', action='store_true',
                        help='Remove disposable previews and temporary files after successful publication.')
    args = parser.parse_args()
    if args.activate and args.condition:
        parser.error('--activate selects a completed mode; omit --condition.')
    if args.cleanup and args.condition:
        parser.error('--cleanup applies after a full published batch; omit --condition.')
    processing.SUBTRACT_TOE = not args.unsubtracted
    processing.MASK_TOE_BEFORE_FIT = args.fit_mode == 'masked'
    args.toe_policy = args.toe_policy or ('masked-only' if args.fit_mode == 'legacy' else 'all-detected')
    processing.SHIFT_ONLY_MASKED_TOE = args.toe_policy == 'masked-only'
    if args.fit_mode == 'masked':
        origin = 'masked_conditional' if processing.SHIFT_ONLY_MASKED_TOE else 'masked'
        plot_prefix = 'test-toe-masked-conditional' if processing.SHIFT_ONLY_MASKED_TOE else 'test-toe-masked'
    else:
        origin = 'conditional' if processing.SHIFT_ONLY_MASKED_TOE else 'corrected'
        plot_prefix = 'test-toe-conditional' if processing.SHIFT_ONLY_MASKED_TOE else 'test-toe'
    if args.unsubtracted:
        origin = 'unsubtracted' if origin == 'corrected' else origin + '_unsubtracted'
        plot_prefix += '-unsubtracted'
    task_root = ROOT / 'data' / 'toe_reprocessing'
    work = task_root / origin
    if args.condition and not args.activate:
        key = hashlib.sha256(args.condition.encode()).hexdigest()[:16]
        work = task_root / 'previews' / origin / key
        plot_prefix += '-preview-' + key
    work.mkdir(parents=True, exist_ok=True)
    if args.activate and not (work / 'validation.json').exists():
        parser.error('No validated cached results exist for this mode; reprocess it first.')
    if args.activate and json.loads((work / 'validation.json').read_text()).get('preview', False):
        parser.error('This mode only has a preview; finish the full batch before activating it.')
    if args.activate and args.fit_mode == 'masked' and not json.loads(
            (work / 'validation.json').read_text()).get('batch_complete', False):
        parser.error('The masked batch is not complete; resume it before activating it.')
    if args.activate and processing.SHIFT_ONLY_MASKED_TOE and json.loads(
            (work / 'validation.json').read_text()).get('toe_shift_policy') != 'masked_only':
        parser.error('This cache does not have verified actual-mask provenance; reprocess it first.')
    backup = task_root / 'originals'
    originals = list((ROOT / 'data' / 'results').glob('begins_*/*.csv'))
    originals += list((ROOT / 'tests' / 'csv_tests').glob('*.csv'))
    originals += list((ROOT / 'data' / 'warm_start').glob('*.csv'))
    manifest = task_root / 'active.json'
    if manifest.exists() and not args.condition:
        previous = json.loads(manifest.read_text()).get('origin')
        if previous in report.TOE_RESULT_ORIGINS and previous != origin:
            snapshot = task_root / 'snapshots' / previous
            for path in originals + [report.OUTPUT, manifest, task_root / 'settings.json']:
                if path.exists():
                    dest = snapshot / path.relative_to(ROOT)
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, dest)
    for path in originals:
        dest = backup / path.relative_to(ROOT)
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
    with (work / 'pairing.log').open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log):
        pairs = processing.load_zero_sample_pairs_by_condition(
            'data/raw', data_root=str(ROOT), strict=False, load_dataframes=False,
            condition_filter=[args.condition] if args.condition else None)
    done_path = work / 'completed.json'
    done = json.loads(done_path.read_text()) if (args.resume or args.activate) and done_path.exists() else []
    failures = {}
    def progress(phase):
        state = {'origin': origin, 'fit_mode': args.fit_mode, 'phase': phase,
                 'toe_shift_policy': 'masked_only' if processing.SHIFT_ONLY_MASKED_TOE else 'all_detected',
                 'completed': len(done), 'total': len(pairs), 'workers': args.workers,
                 'failures': failures}
        (work / 'progress.json').write_text(json.dumps(state, indent=2))
        if not args.condition:
            (task_root / 'running.json').write_text(json.dumps(state, indent=2))
    progress('fitting' if not args.activate else 'validating')
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        jobs = {executor.submit(process_condition, c, str(work), not args.unsubtracted,
                                args.fit_mode == 'masked', plot_prefix, processing.SHIFT_ONLY_MASKED_TOE): c
                for c in pairs if c not in done and c != 'fake-data' and not args.activate}
        for job in as_completed(jobs):
            condition = jobs[job]
            try:
                job.result()
                done.append(condition)
                done_path.write_text(json.dumps(done, indent=2))
                progress('fitting')
                print(f'[{len(done)}/{len(pairs)}] {condition}', flush=True)
            except Exception as exc:
                failures[condition] = str(exc)
                progress('fitting')
                print(f'  FAILED {condition}: {exc}', flush=True)
    (work / 'failures.json').write_text(json.dumps(failures, indent=2))
    (work / 'skipped.json').write_text(json.dumps([
        json.loads(p.read_text()) for p in (work / 'conditions').glob('*/skipped.json')
    ], indent=2))
    if failures:
        progress('failed')
        raise SystemExit('Some conditions failed; published results are unchanged. Resume to retry them.')
    progress('validating')
    for filename, keys in [('reps.csv', ['name', 'Trial']), ('agg.csv', ['name'])]:
        combined = combine_condition_results(work, filename, keys)
        combined.to_csv(work / filename, index=False)
    reps, agg = (pd.read_csv(work / name) for name in ('reps.csv', 'agg.csv'))
    policy = 'masked_only' if processing.SHIFT_ONLY_MASKED_TOE else 'all_detected'
    agg['Toe Shift Policy'] = policy
    agg['Toe Fit Mode'] = args.fit_mode
    reps['Toe Fit Mode'] = args.fit_mode
    reps['Toe Shift Policy'] = policy
    if processing.SHIFT_ONLY_MASKED_TOE:
        masked = reps['Toe Masked'].fillna(False).eq(True)
        reps['Toe Masked'] = masked
        reps['Toe Mask Cutoff'] = pd.to_numeric(reps['Toe Mask Cutoff'], errors='coerce').fillna(0).where(masked, 0)
        offsets = pd.to_numeric(reps['Toe Mask Cutoff'], errors='coerce').fillna(0).where(masked, 0)
    else:
        offsets = pd.to_numeric(reps['Toe Region'], errors='coerce').fillna(0).clip(lower=0)
    if args.unsubtracted:
        offsets[:] = 0
    offsets = offsets.where(reps['Pore Fraction Unsubtracted'].notna(), 0)
    if 'Toe Shift' not in reps:
        reps['Toe Shift'] = offsets
    reps['Toe Shift'] = pd.to_numeric(reps['Toe Shift'], errors='coerce').fillna(0)
    np.testing.assert_allclose(reps['Toe Shift'], offsets, atol=1e-12)
    reps['Toe Subtracted'] = reps['Toe Shift'] > 0
    reps.to_csv(work / 'reps.csv', index=False)
    expected = reps['Pore Fraction Unsubtracted'] - offsets
    np.testing.assert_allclose(reps['Pore Fraction'], expected, equal_nan=True, atol=1e-12)
    # Retain aggregate values in the original origin as well as per-rep values.
    reps['_condition'] = reps['name'].str.split(' | ', regex=False).str[0]
    for idx, row in agg.iterrows():
        name = row['name']
        condition = re.sub(r'_(pre|post)Discard$', '', name)
        selected = reps[reps['_condition'] == condition]
        if name.endswith('_postDiscard'):
            selected = selected[selected['Good Fit'].fillna(False).astype(bool)]
        agg.at[idx, 'Toe Subtracted'] = bool(selected['Toe Subtracted'].any())
        values = pd.to_numeric(selected.get('Pore Fraction Unsubtracted', pd.Series(dtype=float)), errors='coerce')
        agg.at[idx, 'Pore Fraction Unsubtracted Mean'] = values.mean()
        agg.at[idx, 'Pore Fraction Unsubtracted SD'] = values.std(ddof=0)
        corrected = pd.to_numeric(selected.get('Pore Fraction', pd.Series(dtype=float)), errors='coerce')
        np.testing.assert_allclose([row['Pore Fraction Mean'], row['Pore Fraction SD']],
                                   [corrected.mean(), corrected.std(ddof=0)], equal_nan=True, atol=1e-12)
    agg.to_csv(work / 'agg.csv', index=False)
    (work / 'validation.json').write_text(json.dumps({
        'fit_mode': args.fit_mode,
        'toe_shift_policy': policy,
        'shifted_replicates': int(reps['Toe Subtracted'].sum()),
        'preview': bool(args.condition and not args.activate),
        'batch_complete': not args.condition and not failures,
        'replicate_rows': len(reps),
        'finite_pore_fractions': int(reps['Pore Fraction'].notna().sum()),
        'nonzero_toe_rows': int((reps['Toe Region'].fillna(0) != 0).sum()),
        'aggregate_rows': len(agg),
        'replicate_subtraction_verified': True,
        'aggregate_mean_and_sd_verified': True,
    }, indent=2))
    if args.condition and not args.activate:
        report.generate(extra_csv_paths=[work / 'reps.csv'], agg_csv_paths=[work / 'agg.csv'],
                        output_path=work / 'preview' / 'fit_evaluation_log.html',
                        plot_prefix=plot_prefix, condition_filter=[args.condition])
        print(f'Preview ready: {work / "preview" / "fit_evaluation_log.html"}. Published data unchanged.')
        progress('preview_ready')
        if failures:
            raise SystemExit(1)
        return
    progress('publishing')
    for path in originals:
        if path.name in ('reps.csv', 'test_reps.csv'):
            update_pore_columns(path, reps, replicate=True, full_fit=True)
        elif 'agg' in path.name or path.name == 'llm.csv':
            update_pore_columns(path, agg, full_fit=True)
    # Regenerate derived warm-start reports from the now-corrected numeric sources.
    import runpy
    sys.path.insert(0, str(ROOT / 'EVALUATE'))
    runpy.run_path(str(ROOT / 'EVALUATE' / 'export_warm_start.py'), run_name='__main__')
    runpy.run_path(str(ROOT / 'EVALUATE' / 'export_primospire_warm_start.py'), run_name='__main__')
    (task_root / 'active.json').write_text(json.dumps({'origin': origin, 'plot_prefix': plot_prefix,
                                                       'fit_mode': args.fit_mode, 'toe_shift_policy': policy}, indent=2))
    (task_root / 'settings.json').write_text(json.dumps({
        'fit_mode': args.fit_mode, 'subtract_toe': not args.unsubtracted, 'toe_shift_policy': policy}, indent=2))
    report.generate(extra_csv_paths=[work / 'reps.csv'], agg_csv_paths=[work / 'agg.csv'], plot_prefix=plot_prefix)
    if args.cleanup:
        progress('cleaning')
        from EVALUATE.cleanup_toe_artifacts import cleanup_generated
        removed = cleanup_generated(ROOT, apply=True, retain_original_and_latest=True)
        print(f'Cleanup: removed {removed["files"]} disposable files ({removed["bytes"] / 1024**2:.1f} MiB).', flush=True)
    progress('complete')
    print(f'Completed {len(done)} conditions; {len(failures)} failures. Output: {work}', flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
