"""
run_loopHardcode.py — cycles through hardcoded additive amounts.

1. Sends INITIAL_PARAMS (additive = adtv_amts[0]) to robot
2. Robot POSTs back to /server/process
3. Server sends next params (additive = adtv_amts[count]) — no LLM, no processing
4. Repeat until all adtv_amts exhausted or Ctrl+C

Usage:
    python run_loopHardcode.py
"""

import json, threading, time, csv, os, sys, datetime
import cv2
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

class _TeeLogger:
    def __init__(self, filepath, stream):
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        self._file = open(filepath, "a", encoding="utf-8", buffering=1)
        self._stream = stream
    def write(self, msg):
        self._stream.write(msg)
        if msg.strip():
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._file.write(f"[{ts}] {msg}" if msg.endswith("\n") else f"[{ts}] {msg}\n")
        else:
            self._file.write(msg)
    def flush(self):
        self._stream.flush(); self._file.flush()
    def __getattr__(self, name):
        return getattr(self._stream, name)

_log_path = Path(__file__).parent / "logs" / f"run_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')}.log"
sys.stdout = _TeeLogger(_log_path, sys.__stdout__)
sys.stderr = _TeeLogger(_log_path, sys.__stderr__)

sys.path.insert(0, os.path.dirname(__file__))
import url_29 as url

# ── edit these before going to the lab ────────────────────────────────────────
adtv_amts = [1, 2, 3, 4, 5, 6, 7, 8, 9]
count = 0

BASE_PARAMS = {
    "mixing_temp": 6,
    "bath_temp": 5,
    "weight_percent": 17,
    "volume": 1000,
    "pullcast_speed": 1,
    "nitrogen": False,
    "coupon_to_bath_wait_time": 60,
    "nips_bath_wait_time": 100,
}

# <<< PATH >>> hardcoded Windows lab machine paths
CSV_RAW_PATH = Path(r"C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed")
IMAGES_PATH  = Path(r"C:\Users\opentrons\Documents\auto-membranes\images")
SERVER_IP    = "169.254.230.148"
SERVER_PORT  = 8000
CAMERA_INDEX = 2
# ──────────────────────────────────────────────────────────────────────────────

cam = cv2.VideoCapture(CAMERA_INDEX)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
if not os.path.isdir("images"):
    os.mkdir("images")

def take_snapshot():
    ret, img = cam.read()
    if ret:
        cv2.imwrite(os.path.join("images", str(time.time())) + ".jpg", img)
    else:
        print("Error: unable to take picture")


def _send_next(params):
    global count
    print(f"[DONE] received signal for additive={params.get('additive')}  count={count}")
    if count >= len(adtv_amts):
        print("[DONE] all adtv_amts exhausted — no more experiments to send")
        return
    next_params = {**BASE_PARAMS, "additive": adtv_amts[count]}
    count += 1
    print(f"[NEXT] sending additive={next_params['additive']}  (count now {count})")
    url.run_test(next_params)


class LoopHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/compressiontester/status":
            self.send_response(200)
            self.end_headers()
            files = list(CSV_RAW_PATH.glob("**/*.csv"))
            latest = max(files, key=os.path.getctime)
            with open(latest) as f:
                data = list(csv.reader(f))
            safe = float(data[-1][5]) < -6
            self.wfile.write(json.dumps({"safe": safe, "time": os.path.getmtime(latest)}).encode())
        elif path == "/camera/snapshot":
            self.send_response(200)
            self.end_headers()
            take_snapshot()
            self.wfile.write(json.dumps(True).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/server/process":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode())
            params = body.get("parameters", body)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"true")
            threading.Thread(target=_send_next, args=(params,), daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = HTTPServer((SERVER_IP, SERVER_PORT), LoopHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"server listening on {SERVER_IP}:{SERVER_PORT}")

    first_params = {**BASE_PARAMS, "additive": adtv_amts[count]}
    count += 1
    print(f"kicking off experiment {count + 1}: {first_params}")
    url.run_test(first_params)
    print("robot started — loop running. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping server...")
        server.shutdown()
