"""
run_loop.py — continuous active learning loop.

1. Sends INITIAL_PARAMS to robot → robot runs synthesis + compression test
2. Robot POSTs back to /server/process
3. Pipeline processes new condition, saves to output2.csv
4. Claude suggests next params → url.run_test(next_params)
5. Repeat until Ctrl+C

Usage:
    python run_loop.py
"""

import json, threading, time, shutil, csv, os, sys
import pandas as pd
import cv2
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))
import url_29 as url
import processing_29 as processing
import activeLearning_29 as activeLearning

# ── edit these before going to the lab ────────────────────────────────────────
INITIAL_PARAMS = {
    "mixing_temp": 25,
    "bath_temp": 13,
    "weight_percent": 17,
    "volume": 1000,
    "pullcast_speed": 10,
    "nitrogen": False,
    "coupon_to_bath_wait_time": 10,
    "nips_bath_wait_time": 40,
}
DATA_ROOT    = Path(__file__).parent
CSV_OUT      = DATA_ROOT / "output2.csv"
CSV_RAW_PATH = Path(r"C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed")
IMAGES_PATH  = Path(r"C:\Users\opentrons\Documents\auto-membranes\images")
SERVER_IP    = "169.254.230.148"
SERVER_PORT  = 8000
CAMERA_INDEX = 2  # change if wrong camera after restart or replug
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

def get_last_set_csv():
    files = sorted(CSV_RAW_PATH.glob("**/*.csv"), key=os.path.getctime)
    return files[-6:]

def get_last_set_img():
    files = sorted(IMAGES_PATH.glob("*.jpg"), key=os.path.getctime)
    return files[-2:]

def move_and_rename(params):
    s = f"{params['weight_percent']}-"
    if params["weight_percent"] != 17:
        s += f"{params['mixing_temp']}degMix-"
    s += f"{params['bath_temp']}deg-"
    s += f"{params['coupon_to_bath_wait_time']}s-"
    if not params["nitrogen"]:
        s += "No"
    s += "N2-"
    s += f"{params['nips_bath_wait_time']}s"
    base = DATA_ROOT / "compression-test-data" / s
    directory = base
    if directory.exists():
        run = 2
        while (base.parent / f"{base.name}_run{run}").exists():
            run += 1
        directory = base.parent / f"{base.name}_run{run}"
        s = directory.name
        print(f"Condition already tested. New folder: {s}")
    directory.mkdir(parents=True, exist_ok=False)
    for f in get_last_set_img():
        shutil.copy(f, directory)
    for f in get_last_set_csv():
        shutil.copy(f, directory)
    (directory / "params.json").write_text(json.dumps(params))
    return s

def _run_pipeline_and_trigger_next(params):
    try:
        print("\n[1/4] organising files...")
        condition_name = move_and_rename(params)

        print(f"[2/4] processing pipeline for: {condition_name}")
        output = processing.process_zero_sample_pairs_pipeline(
            folder_name="compression-test-data",
            data_root=str(DATA_ROOT),
            strict=True,
            load_cutoff=1.0,
            thickness_info=False,
            thickness_map=None,
            creep_info=True,
            cutoff_load_thickness=1,
            cutoff_load_displacement=2,
            condition_filter=condition_name,
        )
        processing.save_to_csv(output)

        print("[3/4] running active learning...")
        df = pd.read_csv(CSV_OUT)
        new_params_json = activeLearning.LLM_AL(df.to_string(index=False), activeLearning.ranges)
        #Something is going on here
        print("Active Learning JSON:")
        print(repr(new_params_json))
        new_params = json.loads(new_params_json)
        print("Active Learning Parameters:")
        print(json.dumps(new_params, indent=2, sort_keys=True))
        print(f"[4/4] next params: {new_params}")
        url.run_test(new_params)

    except json.JSONDecodeError:
        print("Active learning returned invalid JSON — loop stopped:", new_params_json)
    except Exception as e:
        print(f"Pipeline error — loop stopped: {e}")
        raise

class LoopHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress per-request logs

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
            params = json.loads(self.rfile.read(length).decode())
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"true")
            # respond immediately, run pipeline + AL + next trigger in background
            threading.Thread(
                target=_run_pipeline_and_trigger_next,
                args=(params,),
                daemon=True,
            ).start()
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    server = HTTPServer((SERVER_IP, SERVER_PORT), LoopHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"server listening on {SERVER_IP}:{SERVER_PORT}")

    print(f"kicking off first experiment: {INITIAL_PARAMS}")
    url.run_test(INITIAL_PARAMS)
    print("robot started — loop running. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping server...")
        server.shutdown()
