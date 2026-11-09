"""Remove disposable toe-processing previews after publishing validated results."""
import argparse
import json
from pathlib import Path
import re
import shutil


def cleanup_generated(root, *, apply=False, retain_original_and_latest=False):
    root = Path(root).resolve()
    task = root / 'data' / 'toe_reprocessing'
    pseudo = root / 'data' / 'plots' / 'pseudo-runs'
    targets = [(task / 'previews', task), (task / 'review_high_modulus', task)]
    profiles = ('corrected', 'unsubtracted', 'masked', 'masked_unsubtracted',
                'conditional', 'conditional_unsubtracted',
                'masked_conditional', 'masked_conditional_unsubtracted')
    prefixes = {'corrected': 'test-toe', 'unsubtracted': 'test-toe-unsubtracted',
                'masked': 'test-toe-masked', 'masked_unsubtracted': 'test-toe-masked-unsubtracted',
                'conditional': 'test-toe-conditional', 'conditional_unsubtracted': 'test-toe-conditional-unsubtracted',
                'masked_conditional': 'test-toe-masked-conditional',
                'masked_conditional_unsubtracted': 'test-toe-masked-conditional-unsubtracted'}
    state = None
    if retain_original_and_latest:
        state = json.loads((task / 'active.json').read_text())
        active = state.get('origin')
        if active not in profiles or state.get('plot_prefix', prefixes.get(active)) != prefixes[active]:
            raise ValueError('Cannot identify the latest result and plot version safely.')
        targets += [(task / profile, task) for profile in profiles if profile != active]
        targets.append((task / 'snapshots', task))
    targets += [(task / profile / 'preview', task / profile) for profile in profiles
                if not retain_original_and_latest or profile == state['origin']]
    if pseudo.exists():
        targets += [(p, pseudo) for p in pseudo.iterdir() if p.is_dir() and re.fullmatch(
            r'test-toe.*-preview-[0-9a-f]{16}-[0-9]{4}-[0-9]{2}-[0-9]{2}', p.name)]
        if retain_original_and_latest:
            for path in pseudo.iterdir():
                if path.is_dir() and any(re.fullmatch(re.escape(prefix) + r'-\d{4}-\d{2}-\d{2}', path.name)
                                        for origin, prefix in prefixes.items() if origin != state['origin']):
                    targets.append((path, pseudo))
    targets += [(task / name, task) for name in ('check_stock_dates.py', 'finalize.log')]
    records = []
    for target, allowed_parent in targets:
        if not target.exists():
            continue
        resolved = target.resolve()
        parent = allowed_parent.resolve()
        # Verify the final absolute target before any recursive removal on Windows.
        if not parent.is_relative_to(root) or resolved == parent or not resolved.is_relative_to(parent):
            raise ValueError(f'Cleanup target is outside its allowed directory: {target}')
        files = [f for f in resolved.rglob('*') if f.is_file()] if resolved.is_dir() else [resolved]
        records.append({'path': str(resolved.relative_to(root)), 'parent': str(parent.relative_to(root)), 'files': len(files),
                        'bytes': sum(f.stat().st_size for f in files)})
    result = {'applied': apply, 'retention': 'original_and_latest' if retain_original_and_latest else 'all_completed_modes',
              'targets': records,
              'files': sum(r['files'] for r in records),
              'bytes': sum(r['bytes'] for r in records)}
    if apply:
        state = json.loads((task / 'active.json').read_text())
        if state.get('origin') not in profiles:
            raise ValueError('No recognized active results; leave previews intact.')
        validation = json.loads((task / state['origin'] / 'validation.json').read_text())
        if not validation.get('batch_complete', False):
            raise ValueError('A validated full batch must be published before cleanup.')
        for record in records:
            target = (root / record['path']).resolve()
            parent = (root / record['parent']).resolve()
            # Recheck containment immediately before the filesystem mutation.
            if not parent.is_relative_to(root) or target == parent or not target.is_relative_to(parent):
                raise ValueError(f'Cleanup target escaped the workspace: {target}')
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        (task / 'cleanup_report.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--original-and-latest', action='store_true',
                        help='Also remove intermediate rerun versions; retain original measurements/backups and the active version.')
    args = parser.parse_args()
    print(json.dumps(cleanup_generated(Path(__file__).resolve().parents[1], apply=args.apply,
                                      retain_original_and_latest=args.original_and_latest), indent=2))
