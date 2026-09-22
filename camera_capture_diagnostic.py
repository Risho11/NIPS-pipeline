import ast
import datetime
from pathlib import Path
import subprocess
import sys
import time

if len(sys.argv) == 1:
    try:
        result = subprocess.run([sys.executable, __file__, '--capture'], timeout=30)
        raise SystemExit(result.returncode)
    except subprocess.TimeoutExpired:
        print('FAIL: camera test exceeded 30 seconds; test process terminated.', flush=True)
        raise SystemExit(2)

import cv2
source = Path('src/pipeline/run_loop.py').read_text(encoding='utf-8-sig')
tree = ast.parse(source)
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'take_snapshot')
output = Path('data/camera_diagnostics')
output.mkdir(parents=True, exist_ok=True)
print('Opening camera index 2...', flush=True)
started = time.monotonic()
cam = cv2.VideoCapture(2)
try:
    print(f'Opened: {cam.isOpened()} ({time.monotonic()-started:.2f}s)', flush=True)
    if not cam.isOpened():
        raise SystemExit(1)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    namespace = dict(cam=cam, cv2=cv2, IMAGES_PATH=output, datetime=datetime, time=time)
    warmup = next(n for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'CAMERA_WARMUP_SECONDS' for t in n.targets))
    namespace['CAMERA_WARMUP_SECONDS'] = ast.literal_eval(warmup.value)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<current take_snapshot>', 'exec'), namespace)
    before = set(output.glob('*.jpg'))
    print('Calling current take_snapshot()...', flush=True)
    namespace['take_snapshot']()
    new = set(output.glob('*.jpg')) - before
    for path in new:
        img = cv2.imread(str(path))
        print(f'SAVED {path.resolve()} shape={None if img is None else img.shape} elapsed={time.monotonic()-started:.2f}s', flush=True)
    if not new:
        print('FAIL: no image saved', flush=True)
        raise SystemExit(1)
finally:
    cam.release()
