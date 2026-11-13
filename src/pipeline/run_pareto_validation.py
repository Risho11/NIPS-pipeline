"""Finite Mini PC validation campaign. Preview is the default; see docs/PARETO_VALIDATION.md.

No active learning, automatic material changes, or parameter projection. Hardware
and camera access occur only with --execute. Each batch has its own durable state.
"""

import argparse
from contextlib import contextmanager
import csv
import datetime
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.request
import uuid

import url_29 as robot

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'protocols' / 'pareto_validation_plan.json'
PROCESS_FIELDS = ['mixing_temp', 'bath_temp', 'pullcast_speed', 'nitrogen',
                  'coupon_to_bath_wait_time', 'nips_bath_wait_time', 'polymer_wt', 'additive_wt']


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@contextmanager
def campaign_lock(path):
    """OS lock releases on process exit, including a crash; never clear state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding='utf-8'))
    if (plan.get('schema_version'), plan.get('sample_repeats'),
        plan.get('membrane_tests_per_sample'), plan.get('zero_tests_per_sample')) != (1, 3, 2, 2):
        raise ValueError('Expected the reviewed three-repeat / two-location plan')
    if plan.get('compression_test_locations') != ['coupon test 2', 'coupon test 4']:
        raise ValueError('Expected the bottom pair at the casting-start side: tests 2 and 4')
    seen = set()
    for batch in plan['batches']:
        for condition in batch['conditions']:
            key = (batch['material_context']['polymer_type'], condition['validation_id'])
            if key in seen:
                raise ValueError('Duplicate condition in frozen plan')
            seen.add(key)
            params = condition['parameters']
            if any(params.get(k) != v for k, v in batch['material_context'].items()):
                raise ValueError('Material context changes within batch')
            if not isinstance(params['nitrogen'], bool):
                raise ValueError('Nitrogen must be boolean')
            for key in PROCESS_FIELDS:
                if key != 'nitrogen' and (isinstance(params[key], bool) or
                        not isinstance(params[key], (int, float)) or not math.isfinite(params[key]) or params[key] < 0):
                    raise ValueError(f'Invalid recorded setting: {key}')
    if len(seen) != 10:
        raise ValueError('Frozen plan must contain ten selected conditions')
    return plan


def jobs_for_batch(batch):
    # Finish all independent synthesis repeats of one condition before advancing.
    return [dict(condition=condition, repeat=repeat) for condition in batch['conditions']
            for repeat in range(1, 4)]


def validate_setup(batch, setup):
    if setup.get('material_context') != batch['material_context']:
        raise ValueError('Installed material/bath declaration differs from the frozen batch')
    metadata = setup.get('stock_metadata')
    if not isinstance(metadata, dict):
        raise ValueError('Fill stock_metadata with the actual installed bottle concentrations first')
    import polymer_additive_bounds as bounds
    mode = metadata.get('stock_mode')
    if mode == 'polymer_solvent':
        if set(metadata) != {'stock_mode', 'polymer_stock_wt_percent'}:
            raise ValueError('Polymer/solvent mode needs only stock_mode and polymer_stock_wt_percent')
        concentration = metadata['polymer_stock_wt_percent']
        if (isinstance(concentration, bool) or not isinstance(concentration, (int, float))
                or not math.isfinite(concentration) or not 0 < concentration <= 100):
            raise ValueError('Invalid polymer stock concentration')
        for condition in batch['conditions']:
            params = condition['parameters']
            if params['additive_wt'] != 0 or not 0 <= params['polymer_wt'] <= concentration:
                raise ValueError(f'{condition["validation_id"]}: infeasible with polymer stock and pure solvent only')
            if params['polymer_wt'] == concentration and params['mixing_temp'] > 25:
                raise ValueError(f'{condition["validation_id"]}: undiluted stock skips heated mixing')
        return metadata
    cls = {'two_bottle': bounds.OldStockStruct, 'four_bottle': bounds.StockParameters}.get(mode)
    if cls is None:
        raise ValueError('Explicit stock_mode must be two_bottle or four_bottle')
    fields = set(cls.__dataclass_fields__)
    if set(metadata) != fields | {'stock_mode'}:
        raise ValueError(f'Provide exactly these stock fields: {sorted(fields)} and stock_mode')
    for key in fields:
        value = metadata[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError(f'Invalid stock concentration: {key}')
    stocks = cls(**{key: metadata[key] for key in fields})
    sums = (['additive_stock_polymer_wt_percent', 'additive_stock_additive_wt_percent']
            if mode == 'two_bottle' else ['all_mix_pwt', 'all_mix_cswt'])
    if sum(metadata[key] for key in sums) > 100:
        raise ValueError('Combined stock mass fractions exceed 100%')
    for condition in batch['conditions']:
        params = condition['parameters']
        target = (params['polymer_wt'], params['additive_wt'])
        feasible = bounds.closest_feasible_target(*target, stocks=stocks)
        if any(abs(left - right) > 1e-8 for left, right in zip(target, feasible)):
            raise ValueError(f'{condition["validation_id"]} is infeasible with installed stocks; no recipe will be clamped')
        if bounds.is_undiluted_polymer_stock(*target, stocks=stocks) and params['mixing_temp'] > 25:
            raise ValueError(f'{condition["validation_id"]}: undiluted stock skips heated mixing. Use suitable stocks; the recorded temperature will not be rewritten')
    return metadata


def csv_snapshot(folder):
    return {str(path.resolve()): [path.stat().st_size, path.stat().st_mtime_ns]
            for path in Path(folder).rglob('*.csv')}


def new_csv_files(folder, baseline):
    current = csv_snapshot(folder)
    changed = [name for name in current if name in baseline and current[name] != baseline[name]]
    if changed:
        raise RuntimeError('Pre-existing Newton CSV changed; cannot establish an unambiguous run boundary')
    return sorted((Path(name) for name in current if name not in baseline), key=lambda p: p.name)


def specimen_order(path):
    match = re.fullmatch(r'Specimen_(\d+)_(\d{8})_(\d{6})', path.stem)
    if match is None:
        raise ValueError(f'Unexpected Newton specimen filename: {path.name}')
    return (datetime.datetime.strptime(match[2] + match[3], '%m%d%Y%H%M%S'), int(match[1]))


def process_sample(condition_name, data_root, results):
    # Mechanical processing only; no LLM, material rewrite, or next-experiment suggestion.
    import matplotlib
    matplotlib.use('Agg')
    import curve_segmentation as curves
    pairs = curves.load_zero_sample_pairs_by_condition('data/raw', str(data_root), strict=True,
                                                       condition_filter=condition_name)
    if pairs.get(condition_name, {}).get('num_pairs') != 2:
        raise RuntimeError('Expected exactly two chronological zero/membrane pairs')
    previous = curves._prefix, curves.SAVE_ROOT
    # The fitting module otherwise treats every caller except run_loop.py as a
    # disposable test. Preserve validation plots as real run artifacts instead.
    curves._prefix = 'run'
    curves.SAVE_ROOT = (Path(data_root) / 'data' / 'plots' /
                        f'run-{results.parent.name.removeprefix("begins_")}-{results.name}')
    try:
        output = curves.process_zero_sample_pairs_pipeline(
            'data/raw', str(data_root), strict=True, load_cutoff=1., thickness_info=False,
            creep_info=True, cutoff_load_thickness=3, cutoff_load_displacement=2,
            condition_filter=condition_name)
        curves.save_to_csv(output, data_root=data_root, output_path=results / 'reps.csv',
                           aggregate_path=results / 'agg.csv')
    finally:
        curves._prefix, curves.SAVE_ROOT = previous


class Campaign:
    def __init__(self, plan, batch, setup, args):
        self.plan, self.batch, self.setup, self.args = plan, batch, setup, args
        self.results = ROOT / 'data' / 'results' / f'begins_{args.campaign}' / batch['batch_id']
        self.state_path = self.results / 'validation_state.json'
        self.lock = threading.RLock()
        self.camera = None
        binding = dict(plan=plan, sample_order='condition_then_repeat', batch=batch['batch_id'], setup=setup,
                       locations=args.test_locations, csv_raw_path=str(Path(args.csv_raw_path).resolve()),
                       robot_url=args.robot_url, server_ip=args.server_ip, server_port=args.server_port,
                       camera_index=args.camera_index, collect_only=args.collect_only)
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding='utf-8'))
            if self.state['binding_sha256'] != digest(binding):
                raise ValueError('Saved campaign configuration changed; preserve and inspect its state')
        else:
            self.state = dict(binding_sha256=digest(binding), jobs=[], current=None)

    def save(self):
        save_json(self.state_path, self.state)

    def prepare_job(self, specification, index):
        if index < len(self.state['jobs']):
            job = self.state['jobs'][index]
            directory = ROOT / 'data' / 'raw' / job['name']
            directory.mkdir(parents=True, exist_ok=True)
            if not (directory / 'validation_source.json').exists():
                save_json(directory / 'validation_source.json', specification['condition'])
            return job
        condition = specification['condition']
        sample_name = f'{self.args.campaign}_{self.batch["batch_id"]}_{condition["validation_id"]}_rep{specification["repeat"]}'
        directory = ROOT / 'data' / 'raw' / sample_name
        if directory.exists():
            raise RuntimeError(f'Untracked sample folder exists: {directory}; refusing overwrite')
        request_id = str(uuid.uuid4())
        payload = dict(condition['parameters'], stock_metadata=self.setup['stock_metadata'],
                       compression_test_locations=[f'coupon test {n}' for n in self.args.test_locations],
                       validation_request_id=request_id, validation_id=condition['validation_id'],
                       validation_repeat=specification['repeat'], validation_source=condition['source_condition'])
        job = dict(request_id=request_id, payload=payload, name=sample_name,
                   baseline=csv_snapshot(self.args.csv_raw_path), snapshots=[], status='prepared')
        self.state['jobs'].append(job)
        self.state['current'] = index
        self.save()  # Bind the ID, immutable payload and file boundary before any POST.
        directory.mkdir(parents=True, exist_ok=False)
        save_json(directory / 'validation_source.json', condition)
        return job

    def current_job(self):
        current = self.state['current']
        if current is None:
            raise RuntimeError('No active validation sample')
        return self.state['jobs'][current]

    def receive_callback(self, body):
        with self.lock:
            job = self.current_job()
            parameters = body['parameters']
            if any(parameters.get(key) != value for key, value in job['payload'].items()):
                raise ValueError('Callback identity or parameters differ from active sample')
            if job.get('callback') and job['callback'] != body:
                raise ValueError('Conflicting duplicate completion callback')
            job['callback'] = body
            self.save()

    def snapshot(self):
        import cv2
        with self.lock:
            job = self.current_job()
            if len(job['snapshots']) >= 2:
                raise RuntimeError('Sample already has two snapshots; refusing extra capture')
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                ok, frame = self.camera.read()
                if not ok:
                    raise RuntimeError('Camera warm-up failed')
                time.sleep(.01)
            ok, frame = self.camera.read()
            path = ROOT / 'data' / 'raw' / job['name'] / f'{time.time_ns()}.jpg'
            if not ok or not cv2.imwrite(str(path), frame):
                raise RuntimeError('Camera snapshot failed')
            job['snapshots'].append(path.name)
            self.save()
        return True

    def tester_status(self):
        with self.lock:
            job = self.current_job()
            files = new_csv_files(self.args.csv_raw_path, job['baseline'])
        if not files:
            raise RuntimeError('No new compression CSV for the active sample')
        latest = max(files, key=lambda path: path.stat().st_mtime_ns)
        with latest.open(newline='', encoding='utf-8-sig') as handle:
            rows = list(csv.reader(handle))
        displacement = float(rows[-1][5])
        stamp, now = latest.stat().st_mtime, time.time()
        return {'safe': math.isfinite(displacement) and displacement < -6,
                'time': stamp, 'current time': now, 'age': now - stamp}

    def wait_for_completion(self, job):
        deadline = time.monotonic() + self.args.sample_timeout
        while time.monotonic() < deadline:
            with urllib.request.urlopen(f'{self.args.robot_url}/requests/{job["request_id"]}', timeout=30) as response:
                status = json.load(response)
            if status.get('journal_id') != self.state['journal_id'] or status.get('digest') != digest(job['payload']):
                raise RuntimeError('Robot journal or request payload identity changed')
            if status['status'] == 'failed':
                raise RuntimeError('Robot request failed; inspect hardware and preserve both journals')
            with self.lock:
                callback = job.get('callback')
            if status['status'] == 'completed':
                if not callback:
                    raise RuntimeError('Robot completed without a recorded callback; inspect before recovery')
                return
            time.sleep(2)
        raise TimeoutError('Sample timeout; restore connectivity and resume the same state/ID')

    def collect(self, job):
        files = new_csv_files(self.args.csv_raw_path, job['baseline'])
        if len(files) != 4 or len({p.name for p in files}) != 4:
            raise RuntimeError(f'Expected exactly four new CSVs (two zero + two membrane); found {len(files)}')
        if len(job['snapshots']) != 2:
            raise RuntimeError('Expected pre- and post-test snapshots')
        files.sort(key=specimen_order)
        directory = ROOT / 'data' / 'raw' / job['name']
        for source in files:
            content = source.read_bytes()
            target = directory / source.name
            if target.exists() and target.read_bytes() != content:
                raise RuntimeError('Existing collected measurement differs; refusing overwrite')
            if not target.exists():
                shutil.copy2(source, target)
            if source.read_bytes() != content or target.read_bytes() != content:
                raise RuntimeError('Measurement changed during collection')
        save_json(directory / 'params.json', job['callback']['parameters'])
        save_json(directory / 'protocol_log.json', job['callback'].get('protocol_log', []))
        save_json(directory / 'compression_locations.json', {
            'order': job['payload']['compression_test_locations'],
            'zero_files': [p.name for p in files[:2]],
            'membrane_files': [p.name for p in files[2:]], 'zero_count': 2, 'sample_count': 2})
        job['status'] = 'collected'
        self.save()

    def run(self):
        health = robot.check_health(expected_journal=self.state.get('journal_id'))
        locations = [f'coupon test {n}' for n in self.args.test_locations]
        if (health.get('compression_plan_version') != 1 or health.get('request_status_version') != 1
                or locations not in health.get('compression_row_pairs', [])):
            raise RuntimeError('Deploy updated robot protocol + compression_plan.py + request_server.py first')
        if (self.setup['stock_metadata']['stock_mode'] == 'polymer_solvent'
                and 'polymer_solvent' not in health.get('stock_modes', [])):
            raise RuntimeError('Deploy updated ot2.py and calculations.py for polymer/solvent-only stocks first')
        self.state['journal_id'] = health['journal_id']
        self.save()
        for index, specification in enumerate(jobs_for_batch(self.batch)):
            with self.lock:
                job = self.prepare_job(specification, index)
                if job['status'] == 'completed':
                    continue
                self.state['current'] = index
                self.save()
            print(f'{index + 1}/{len(jobs_for_batch(self.batch))}: {job["name"]}', flush=True)
            if job['status'] != 'collected':
                # A restart reuses the same durable ID and original file boundary.
                if not job.get('callback'):
                    robot.run_test(job['payload'], request_id=job['request_id'], journal_id=self.state['journal_id'])
                self.wait_for_completion(job)
                with self.lock:
                    self.collect(job)
            if not self.args.collect_only and not job.get('mechanical_processed'):
                process_sample(job['name'], ROOT, self.results)
                job['mechanical_processed'] = True
            with self.lock:
                job['status'] = 'completed'
                self.save()
        self.state['current'] = None
        self.state['completed'] = True
        self.save()
        print('Batch complete. No further experiments will be submitted.', flush=True)


def handler_for(campaign):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, result):
            payload = json.dumps(result, allow_nan=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            try:
                if self.path == '/compressiontester/status':
                    self.reply(200, campaign.tester_status())
                elif self.path == '/camera/snapshot':
                    self.reply(200, campaign.snapshot())
                else:
                    self.reply(404, {'error': 'Unknown endpoint'})
            except Exception as error:
                self.reply(500, {'error': str(error)})

        def do_POST(self):
            if self.path != '/server/process':
                self.reply(404, {'error': 'Unknown endpoint'})
                return
            try:
                self.connection.settimeout(30)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8 * 1024 * 1024:
                    raise ValueError('Invalid callback length')
                campaign.receive_callback(json.loads(self.rfile.read(length)))
                self.reply(200, True)
            except Exception as error:
                self.reply(409, {'error': str(error)})
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=PLAN)
    parser.add_argument('--batch')
    parser.add_argument('--campaign', help='New unique campaign key; reuse unchanged to resume')
    parser.add_argument('--setup', type=Path)
    parser.add_argument('--test-locations', nargs=2, type=int, default=[2, 4],
                        help='Casting-start bottom pair; fixed to 2 4 for this plan')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--process-only', action='store_true', help='Process saved batch samples without network or hardware')
    parser.add_argument('--collect-only', action='store_true', help='Keep raw data; defer mechanical processing')
    parser.add_argument('--csv-raw-path', type=Path, default=Path(r'C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed'))
    parser.add_argument('--server-ip', default='169.254.230.148')
    parser.add_argument('--server-port', type=int, default=8000)
    parser.add_argument('--robot-url', default=robot.BASE_URL)
    parser.add_argument('--camera-index', type=int, default=2)
    parser.add_argument('--sample-timeout', type=float, default=4 * 60 * 60)
    args = parser.parse_args(argv)
    plan = load_plan(args.plan)
    batches = [batch for batch in plan['batches'] if args.batch is None or batch['batch_id'] == args.batch]
    if not batches:
        parser.error('Unknown batch')
    if args.process_only:
        if args.execute or not args.batch or not args.campaign or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', args.campaign):
            parser.error('--process-only needs --batch and --campaign, without --execute')
        results = ROOT / 'data' / 'results' / f'begins_{args.campaign}' / args.batch
        path = results / 'validation_state.json'
        with campaign_lock(ROOT / 'data' / 'results' / '.pareto_validation.lock'):
            state = json.loads(path.read_text(encoding='utf-8'))
            for job in state['jobs']:
                if job['status'] not in {'collected', 'completed'} or job.get('mechanical_processed'):
                    continue
                process_sample(job['name'], ROOT, results)
                job['mechanical_processed'] = True
                save_json(path, state)
        return
    for batch in batches:
        print(f'{batch["batch_id"]}: {len(batch["conditions"])} conditions, '
              f'{3 * len(batch["conditions"])} independent samples; {batch["material_context"]}')
        for job in jobs_for_batch(batch):
            print(f'  {job["condition"]["validation_id"]} repeat {job["repeat"]}: {job["condition"]["parameters"]}')
    if not args.execute:
        print('Preview only: no device, network, camera, or experiment-state access.')
        return
    if (not args.batch or not args.setup or not args.campaign or
            not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', args.campaign)):
        parser.error('--execute requires --batch, --setup and a simple unique --campaign key')
    if args.test_locations != [2, 4]:
        parser.error('This reviewed plan uses the casting-start bottom pair: --test-locations 2 4')
    if not args.csv_raw_path.is_dir() or not math.isfinite(args.sample_timeout) or args.sample_timeout <= 0:
        parser.error('Newton CSV directory must exist and sample timeout must be positive')
    batch = batches[0]
    setup = json.loads(args.setup.read_text(encoding='utf-8'))[args.batch]
    validate_setup(batch, setup)  # No silent projection, material override, or heating rewrite.
    robot.BASE_URL = args.robot_url.rstrip('/')
    args.robot_url = robot.BASE_URL
    lock_path = ROOT / 'data' / 'results' / '.pareto_validation.lock'
    # Global local lock: a second chemistry/batch must not fight for this robot/server.
    with campaign_lock(lock_path):
        campaign = Campaign(plan, batch, setup, args)
        server = HTTPServer((args.server_ip, args.server_port), handler_for(campaign))
        import cv2
        campaign.camera = cv2.VideoCapture(args.camera_index)
        campaign.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        campaign.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        if not campaign.camera.isOpened():
            server.server_close()
            campaign.camera.release()
            raise RuntimeError('Unable to open snapshot camera')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            campaign.run()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            campaign.camera.release()


if __name__ == '__main__':
    main()
