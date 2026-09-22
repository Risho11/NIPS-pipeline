"""Standalone robot camera diagnostic; works with the existing lib/url.py.

Run beside robot.json and lib/ on the robot:
    python camera_box_test.py
    python camera_box_test.py --http-only
    python camera_box_test.py --http-only --timeout 60

The default preserves url.py's timeout behavior. A snapshot saves a real image
on the PC. Keep the PC camera server running, but stop the robot campaign before
using this script. This script does not start synthesis or move a coupon.
"""
import argparse
from contextlib import contextmanager
import datetime
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
import traceback
import urllib.request
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent


def log(message):
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


@contextmanager
def trace_http(timeout=None):
    """Trace the actual url.py requests without editing that module on disk."""
    original = urllib.request.urlopen

    class TracedResponse:
        def __init__(self, response):
            self.response = response

        def read(self, *args, **kwargs):
            started = time.monotonic()
            log("Reading HTTP response body...")
            try:
                body = self.response.read(*args, **kwargs)
            except Exception:
                log(f"Body read FAILED after {time.monotonic() - started:.2f}s")
                raise
            log(f"Body received after {time.monotonic() - started:.2f}s: {body[:1000]!r}")
            return body

        def __getattr__(self, name):
            return getattr(self.response, name)

    @contextmanager
    def traced_open(*args, **kwargs):
        if timeout is not None:
            kwargs['timeout'] = timeout
        started = time.monotonic()
        effective = kwargs.get('timeout', socket.getdefaulttimeout())
        log(f"HTTP request: {args[0]}; timeout={effective!r}")
        try:
            with original(*args, **kwargs) as response:
                log(f"Headers received after {time.monotonic() - started:.2f}s: "
                    f"status={response.status}, headers={dict(response.headers)}")
                yield TracedResponse(response)
        except Exception as exc:
            log(f"HTTP FAILED after {time.monotonic() - started:.2f}s: "
                f"{type(exc).__name__}: {exc}")
            raise

    with patch.object(urllib.request, 'urlopen', traced_open):
        yield


def load_robot_url():
    path = ROOT / 'lib' / 'url.py'
    spec = importlib.util.spec_from_file_location('camera_test_robot_url', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    log(f"Loaded robot HTTP helper: {path}")
    log(f"PC server: {module.BASE_URL}")
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--http-only', action='store_true', help='Take a photo without arm initialization or motion.')
    parser.add_argument('--timeout', type=float, help='Override HTTP timeout in seconds for this test only.')
    parser.add_argument('--settle', type=float, default=10, help='Seconds to wait after closing the box (default: 10).')
    args = parser.parse_args(argv)
    if args.timeout is not None and (not 0 < args.timeout < float('inf')):
        parser.error('--timeout must be finite and positive')
    if not 0 <= args.settle < float('inf'):
        parser.error('--settle must be finite and nonnegative')

    url = load_robot_url()
    log(f"Global socket timeout before arm initialization: {socket.getdefaulttimeout()!r}")
    arm = None
    stage = 'setup'

    def move_box(open_box):
        action = 'open' if open_box else 'close'
        log(f"Camera box: {action} requested")
        (arm.open_camera_box if open_box else arm.close_camera_box)()
        # Preserve other robot counters; only record the completed box action.
        state_path = ROOT / 'robot.json'
        state = json.loads(state_path.read_text())
        state['camera_box_open'] = arm.camera_box_open
        temporary = state_path.with_suffix('.camera-test.tmp')
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(state_path)
        log(f"Camera box command completed; tracked open={arm.camera_box_open}. Verify visually.")

    try:
        if not args.http_only:
            state = json.loads((ROOT / 'robot.json').read_text())
            print('Stop the robot campaign process before this test. Keep the PC camera server running.\n'
                  'Arm initialization will HOME the arm and OPEN its gripper.\n'
                  'The gripper must be empty and the homing/box motion paths clear.\n'
                  'The test opens the box, closes it, takes one photo, then opens it again.', flush=True)
            physical = input('Actual camera box position now (open/closed): ').strip().lower()
            if physical not in ('open', 'closed'):
                raise ValueError('Enter open or closed; no motion performed.')
            if input('Campaign stopped and ready for these arm movements? (Y/N): ').strip().lower() != 'y':
                log('Cancelled before arm initialization.')
                return 0
            sys.path.insert(0, str(ROOT / 'lib'))
            from arm import Arm
            stage = 'arm initialization / homing'
            arm = Arm(coupons=state['coupons'], rings=state['rings'],
                      discards=state['discard'], camera_box_open=(physical == 'open'))
            stage = 'opening camera box'
            move_box(True)
            stage = 'closing camera box'
            move_box(False)
            time.sleep(args.settle)

        log(f"Global socket timeout at snapshot call: {socket.getdefaulttimeout()!r}")
        stage = 'snapshot HTTP request'
        with trace_http(args.timeout):
            result = url.take_snapshot()
        if result is not True:
            raise RuntimeError(f'Unexpected snapshot response: {result!r}')
        log('PC returned true. Verify that a NEW image exists in the PC images folder; '
            'the old PC handler could return true even when capture failed.')
        if arm is not None:
            stage = 'reopening camera box'
            move_box(True)
        log('Camera diagnostic completed.')
        return 0
    except (Exception, KeyboardInterrupt):
        log(f'STOPPED during: {stage}. No automatic retry or recovery motion.')
        traceback.print_exc()
        if arm is not None:
            log(f'Last tracked camera_box_open={arm.camera_box_open}; verify physical state.')
        return 1
    finally:
        if arm is not None:
            arm.xArm.disconnect()


if __name__ == '__main__':
    sys.exit(main())
