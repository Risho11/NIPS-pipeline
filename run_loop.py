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

import json, re, threading, time, shutil, csv, os, sys
import pandas as pd
import cv2
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))  # <<< IMPORT >>> adds script's own folder to path — breaks if moved to subfolder
import url_29 as url                           # <<< IMPORT >>> must be in same folder as run_loop.py
import processing_29 as processing             # <<< IMPORT >>> must be in same folder
import activeLearning_29 as activeLearning     # <<< IMPORT >>> must be in same folder

# ── edit these before going to the lab ────────────────────────────────────────
INITIAL_PARAMS = {
    "mixing_temp": 25,
    "bath_temp": 5,
    "weight_percent": 17,
    "volume": 1000,
    "pullcast_speed": 10,
    "nitrogen": True,
    "coupon_to_bath_wait_time": 5,
    "nips_bath_wait_time": 20,
}
PARAMS_SCHEMA = {
    "mixing_temp":              (int, float),
    "bath_temp":                (int, float),
    "weight_percent":           (int, float),
    "volume":                   (int, float),
    "pullcast_speed":           (int, float),
    "nitrogen":                 (bool,),
    "coupon_to_bath_wait_time": (int, float),
    "nips_bath_wait_time":      (int, float),
}
# <<< PATH >>> project root = folder containing this script
DATA_ROOT    = Path(__file__).parent
# <<< PATH >>> output CSVs land beside this script
CSV_REPS        = DATA_ROOT / "results_reps.csv"
CSV_AGG         = DATA_ROOT / "results_agg.csv"
CSV_AGG_LLM     = DATA_ROOT / "results_agg_llm.csv"
# <<< PATH >>> hardcoded Windows lab machine paths — change if machine changes
CSV_RAW_PATH = Path(r"C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed")
IMAGES_PATH  = Path(r"C:\Users\opentrons\Documents\auto-membranes\images")
SERVER_IP    = "169.254.230.148"
SERVER_PORT  = 8000
CAMERA_INDEX = 2  # change if wrong camera after restart or replug
# ──────────────────────────────────────────────────────────────────────────────

cam = cv2.VideoCapture(CAMERA_INDEX)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
# <<< PATH >>> "images" folder relative to cwd, not DATA_ROOT
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
    base = DATA_ROOT / "compression-test-data" / s  # <<< FOLDER NAME >>>
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

LLM_PROP_KEYS = ["Strain at 50 bar", "CV"]


def _extract_next_params(raw_text):
    """Extract the next_params dict from LLM output. Tries multiple formats."""
    def _navigate(parsed):
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if isinstance(parsed, dict):
            if "next_params" in parsed:
                return parsed["next_params"]
            if set(PARAMS_SCHEMA).issubset(parsed.keys()):
                return {k: parsed[k] for k in PARAMS_SCHEMA}
        return None

    # 1. parse full text directly
    try:
        result = _navigate(json.loads(raw_text.strip()))
        if result is not None:
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. extract from markdown code fence
    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
    if fence:
        try:
            result = _navigate(json.loads(fence.group(1).strip()))
            if result is not None:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. find outermost [...] or {...} then navigate
    for pattern in (r'\[[\s\S]*\]', r'\{[\s\S]*\}'):
        m = re.search(pattern, raw_text)
        if m:
            try:
                result = _navigate(json.loads(m.group(0)))
                if result is not None:
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

    # 4. innermost flat {} (original fallback)
    m = re.search(r'\{[^{}]*\}', raw_text)
    if m:
        try:
            candidate = json.loads(m.group(0))
            if isinstance(candidate, dict):
                return candidate
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"LLM returned no parseable params:\n{raw_text[:300]}")


def _validate_params(params):
    """Raise ValueError if params don't exactly match PARAMS_SCHEMA keys and types."""
    expected = set(PARAMS_SCHEMA)
    got = set(params)
    missing = expected - got
    extra = got - expected
    if missing:
        raise ValueError(f"next_params missing keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"next_params has unexpected keys: {sorted(extra)}")
    for key, allowed_types in PARAMS_SCHEMA.items():
        val = params[key]
        if isinstance(val, bool) and bool not in allowed_types:
            raise ValueError(
                f"next_params['{key}'] wrong type: got bool, expected "
                f"{tuple(t.__name__ for t in allowed_types)}"
            )
        if not isinstance(val, allowed_types):
            raise ValueError(
                f"next_params['{key}'] wrong type: got {type(val).__name__}, expected "
                f"{tuple(t.__name__ for t in allowed_types)}"
            )


def _run_pipeline_and_trigger_next(params):
    try:
        print("\n[1/5] organising files...")
        condition_name = move_and_rename(params)

        print(f"[2/5] processing pipeline for: {condition_name}")
        output = processing.process_zero_sample_pairs_pipeline(
            folder_name="compression-test-data",  # <<< FOLDER NAME >>>
            data_root=str(DATA_ROOT),
            strict=False,
            load_cutoff=1.0,
            thickness_info=False,
            thickness_map=None,
            creep_info=True,
            cutoff_load_thickness=1,
            cutoff_load_displacement=2,
            condition_filter=condition_name,
        )
        processing.save_to_csv(output, data_root=DATA_ROOT,
                               output_path=CSV_REPS, aggregate_path=CSV_AGG)

        _agg_df = pd.read_csv(CSV_AGG)
        _has_post = (_agg_df["name"] == f"{condition_name}_postDiscard").any()
        _source = "postDiscard" if _has_post else ""
        processing.promote_to_main(condition_name, _source, CSV_AGG, CSV_AGG_LLM)

        print("[3/5] generating initial report...")
        if not CSV_AGG_LLM.exists() or CSV_AGG_LLM.stat().st_size == 0:
            raise ValueError(f"LLM CSV missing or empty after promote_to_main: {CSV_AGG_LLM}")
        llm_df = pd.read_csv(CSV_AGG_LLM)
        if llm_df.empty:
            raise ValueError(f"LLM CSV has no data rows: {CSV_AGG_LLM}")
        for col in ["initial_report", "final_report"]:
            if col in llm_df.columns:
                llm_df[col] = llm_df[col].astype(object)
        mask = llm_df["name"] == condition_name
        idx = llm_df[mask].index[-1] if mask.any() else llm_df.index[-1]
        fmt_params = llm_df.at[idx, "formatted_parameters"]
        initial_report = activeLearning.Generate_report(fmt_params)
        print(f"  initial_report: {initial_report[:120]}...")

        mech_subset = {f"{k} Mean": llm_df.at[idx, f"{k} Mean"]
                       for k in LLM_PROP_KEYS
                       if f"{k} Mean" in llm_df.columns and pd.notna(llm_df.at[idx, f"{k} Mean"])}
        fmt_params_with_prop = str(mech_subset)
        final_report = initial_report + "\n" + fmt_params_with_prop
        print(f"final_report: {final_report[120:]}...")

        # fill reports back into LLM CSV
        llm_df.at[idx, "initial_report"] = initial_report
        llm_df.at[idx, "formatted_parameters_withProp"] = fmt_params + fmt_params_with_prop
        llm_df.at[idx, "final_report"] = final_report
        llm_df.to_csv(CSV_AGG_LLM, index=False)
        print(f"  LLM CSV updated: {CSV_AGG_LLM}")

        print("[4/5] running active learning...")
        params_suggestion = activeLearning.LLM_AL(final_report, activeLearning.ranges)

        llm_df.at[idx, "LLM_suggestion"] = params_suggestion
        llm_df.to_csv(CSV_AGG_LLM, index=False)

        new_params = _extract_next_params(params_suggestion)
        _validate_params(new_params)

        json_out = DATA_ROOT / f"llm_result_{condition_name}.json"  # <<< PATH >>>
        with open(json_out, "w") as f:
            json.dump(new_params, f, indent=2)
        print(f"  JSON result: {json_out}")

        print(f"[5/5] next params: {new_params}")
        url.run_test(new_params)
        # response = urllib.request.urlopen("http://169.254.46.48:8000/run", json.dumps(new_params).encode())

    except json.JSONDecodeError:
        print("Active learning returned invalid JSON — loop stopped:", params_suggestion)
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
