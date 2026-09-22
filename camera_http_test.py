"""Camera-only HTTP test; no robot imports or movements.

PC:   python camera_http_test.py serve
OT-2: python camera_http_test.py capture --url http://169.254.230.148:8001
PC local test: python camera_http_test.py capture --url http://127.0.0.1:8001
For the robot's unchanged lib/url.py and camera_box_test.py:
PC: python camera_http_test.py serve --port 8000 --robot-compatible

Copy this file to the OT-2 for client mode (standard library only).
Stop the PC server with Ctrl+C. Diagnostic pictures go to data/camera_diagnostics.
Port 8001 avoids the experiment server's port, but both must not use the camera
at the same time. This test does not test physical box opening or recovery.
"""

import argparse
import ast
import datetime
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent


def capture_worker(output):
    # Load only the current camera function/settings, not the experiment module.
    import cv2

    source = ROOT / 'src/pipeline/run_loop.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    function = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == 'take_snapshot')
    settings = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    'CAMERA_INDEX', 'CAMERA_WARMUP_SECONDS'
                }:
                    settings[target.id] = ast.literal_eval(node.value)
    cam = cv2.VideoCapture(settings['CAMERA_INDEX'])
    try:
        if not cam.isOpened():
            raise RuntimeError('Camera failed to open')
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        namespace = dict(cam=cam, cv2=cv2, IMAGES_PATH=output,
                         datetime=datetime, time=time, **settings)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        namespace['take_snapshot']()
        pictures = list(output.glob('*.jpg'))
        if len(pictures) != 1 or cv2.imread(str(pictures[0])) is None:
            raise RuntimeError('Capture did not save a readable JPEG')
        print(f'Saved: {pictures[0]}', flush=True)
    finally:
        cam.release()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/camera/snapshot':
            self.send_error(404)
            return
        started = time.monotonic()
        output = ROOT / 'data/camera_diagnostics' / datetime.datetime.now().strftime('http_%Y%m%d_%H%M%S_%f')
        output.mkdir(parents=True)
        # A separate process lets the test terminate a blocked native camera read.
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), '_worker', str(output)],
                capture_output=True, text=True, timeout=20,
            )
            success = result.returncode == 0
            payload = {'success': success, 'elapsed_seconds': round(time.monotonic() - started, 2),
                       'images': [str(p) for p in output.glob('*.jpg')],
                       'details': result.stdout + result.stderr}
            status = 200 if success else 500
        except subprocess.TimeoutExpired:
            status = 504
            payload = {'success': False, 'error': 'Camera capture exceeded 20 seconds; worker terminated.'}
        except Exception as exc:
            status = 500
            payload = {'success': False, 'error': str(exc)}
        # The production robot helper expects JSON true; retain full diagnostics
        # in the PC console and preserve the richer default test-client response.
        response_payload = True if status == 200 and self.server.robot_compatible else payload
        body = json.dumps(response_payload).encode()
        print(json.dumps(payload, indent=2), flush=True)
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            print('Client disconnected before the result was delivered.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modes = parser.add_subparsers(dest='mode', required=True)
    server = modes.add_parser('serve')
    server.add_argument('--host', default='0.0.0.0')
    server.add_argument('--port', type=int, default=8001)
    server.add_argument('--robot-compatible', action='store_true',
                        help='Return JSON true on success, matching the robot lib/url.py contract.')
    client = modes.add_parser('capture')
    client.add_argument('--url', default='http://169.254.230.148:8001')
    worker = modes.add_parser('_worker', help=argparse.SUPPRESS)
    worker.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.mode == '_worker':
        capture_worker(args.output)
    elif args.mode == 'serve':
        with HTTPServer((args.host, args.port), Handler) as httpd:
            httpd.robot_compatible = args.robot_compatible
            print(f'Camera-only server on {args.host}:{args.port}. Ctrl+C to stop.', flush=True)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
    else:
        started = time.monotonic()
        try:
            with urllib.request.urlopen(args.url.rstrip('/') + '/camera/snapshot', timeout=30) as response:
                result = json.loads(response.read())
            print(json.dumps(result, indent=2))
            print(f'HTTP round trip: {time.monotonic() - started:.2f}s')
            return 0 if result is True or (isinstance(result, dict) and result.get('success')) else 1
        except urllib.error.HTTPError as exc:
            print(f'HTTP {exc.code}: {exc.read().decode()}', file=sys.stderr)
            return 1
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f'Camera request failed: {exc}', file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
