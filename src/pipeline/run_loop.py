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

import json, re, threading, time, shutil, csv, os, sys, datetime
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

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # src/pipeline/run_loop.py -> repo root

# Log-file redirection and camera setup live in `if __name__ == "__main__":` below, not here --
# doing it at module level meant merely `import run_loop` (a test script, a REPL, a one-off
# helper check) silently created a new logs/run_*.log and hijacked stdout for the rest of that
# process, and opened the physical camera device, neither of which should happen outside an
# actual campaign run.

sys.path.insert(0, os.path.dirname(__file__))  # <<< IMPORT >>> adds script's own folder (src/pipeline) to path — siblings live here
import url_29 as url                           # <<< IMPORT >>> must be in same folder as run_loop.py
import activeLearning_29 as activeLearning     # <<< IMPORT >>> must be in same folder
import master_processing                       # <<< IMPORT >>> dispatches curve_segmentation + image_processing branches
import llm_context                             # <<< IMPORT >>> what branch results become CSV/report text for the LLM

# ── edit these before going to the lab ────────────────────────────────────────
INITIAL_PARAMS = {
    "mixing_temp": 25,
    "bath_temp": 5,
    "pullcast_speed": 10,
    "nitrogen": True,
    "coupon_to_bath_wait_time": 30,
    "nips_bath_wait_time": 125,
    "polymer_wt": 17,
    "additive_wt": 0
}

# TEMPORARY -- additive-free campaign phase. Hard clamp, not just a prompt suggestion: when
# LOCK_ADDITIVE_WT is True, the LLM's next_params always gets additive_wt forced to
# LOCK_ADDITIVE_WT_VALUE after parsing, regardless of what it actually suggested. Prompt wording
# alone isn't a guarantee the model won't drift (see
# system_prompt._ACTIVE_LEARNING_PROMPT_ORIGINAL_BUGGY_BACKUP for what that cost us once
# already). Flip LOCK_ADDITIVE_WT back to False once additive experiments are back in scope --
# don't leave this on by accident, it silently overrides every LLM suggestion until someone
# notices.
LOCK_ADDITIVE_WT = True
LOCK_ADDITIVE_WT_VALUE = 0

# When either is True, next_params advances through ADDITIVE_ITERATION_LIST and/or
# POLYMER_ITERATION_LIST instead of asking the LLM
# Sweeping is forced on regardless of these flags whenever no branches are enabled at all 
ITERATE_ADDITIVES = False
ITERATE_POLYMER = False
# LLM search policy:
#   "optimize" (default): objective-first active learning
#   "explore": maximize diversity/coverage to populate the dataset
LLM_AL_SEARCH_MODE = "optimize"
# Number of recent unique points provided as diversity context when LLM_AL_SEARCH_MODE="explore"
LLM_AL_EXPLORATION_HISTORY_POINTS = 40
#basically if None, it'll make a new thing but it'll be put automatically in old_csv... or. possibly
#in another csv thing so there'd be campaign csvs (like REAL campaigns) so yea
#otherwise put the date of the campaign in YYYY-MM-DD format in a string
CONTINUE_CAMPAIGN = "2026-8-19"


def _campaign_date_folder_tag(continue_campaign):
    """Return YYYY-MM-DD folder tag for campaign outputs."""
    if continue_campaign is None:
        return datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        parsed = datetime.datetime.strptime(str(continue_campaign), "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            "CONTINUE_CAMPAIGN must be None or a date string in YYYY-MM-DD format "
            f"(got {continue_campaign!r})"
        ) from e
    return parsed.strftime("%Y-%m-%d")


def _campaign_folder_tag(continue_campaign, search_mode):
    """Campaign folder tag with optional search-mode suffix."""
    base = _campaign_date_folder_tag(continue_campaign)
    mode = str(search_mode).strip().lower()
    if mode in {"explore", "exploration", "exploratory", "diversity"}:
        return f"{base}-exploration-mode"
    return base

ADDITIVE_ITERATION_LIST = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4]
POLYMER_ITERATION_LIST = [10, 11, 12, 13, 14, 15, 16, 16.5, 17]
ITERATION_BASE_PARAMS = {
    "mixing_temp": 25,
    "bath_temp": 5,
    "pullcast_speed": 10,
    "nitrogen": True,
    "coupon_to_bath_wait_time": 60,
    "nips_bath_wait_time": 121,
    "polymer_wt": 10,
}
_iteration_count = 0

PARAMS_SCHEMA = {
    "mixing_temp":              (int, float),
    "bath_temp":                (int, float),
    "pullcast_speed":           (int, float),
    "nitrogen":                 (bool,),
    "coupon_to_bath_wait_time": (int, float),
    "nips_bath_wait_time":      (int, float),
    "polymer_wt":               (int, float),
    "additive_wt":              (int, float),
}
# <<< PATH >>> project root = three levels up from src/pipeline/run_loop.py
DATA_ROOT    = _REPO_ROOT


# <<< PATH >>> output CSVs live under data/results/
d = _campaign_folder_tag(CONTINUE_CAMPAIGN, LLM_AL_SEARCH_MODE)
CSV_REPS        = DATA_ROOT / "data" / "results" / f"begins_{d}" / f"reps.csv"
CSV_AGG         = DATA_ROOT / "data" / "results" / f"begins_{d}" / f"agg.csv"
CSV_AGG_LLM     = DATA_ROOT / "data" / "results" / f"begins_{d}" / f"llm.csv"

def startup(lock_add, locked_value, iterate_add, iterate_poly, continue_campaign, campaign_date):
    if continue_campaign is None:
        print(f"Campaign: starting new -- {campaign_date}")
    else:
        print(f"Campaign: continuing -- {campaign_date}")

    print("Stock solutions:")
    for k, v in activeLearning.bounds.send_metadata().items():
        print(f"  {k}: {v}")

    active = []
    if lock_add:
        active.append(f"LOCK_ADDITIVE_WT (forcing additive_wt={locked_value})")
    if iterate_add:
        active.append("ITERATE_ADDITIVES")
    if iterate_poly:
        active.append("ITERATE_POLYMER")
    if str(LLM_AL_SEARCH_MODE).strip().lower() != "optimize":
        active.append(f"LLM_AL_SEARCH_MODE={LLM_AL_SEARCH_MODE}")

    if not active:
        return

    print("WARNING: these configurations are active:")
    for a in active:
        print(f"  - {a}")
    okay = input("Is this correct? (Y/N) ").strip().lower()
    if okay != "y":
        print("Shutting down -- please change the config")
        sys.exit(1)


JSON_RESULTS_DIR = DATA_ROOT / "data" / "llm_results"
# <<< PATH >>> hardcoded Windows lab machine paths — change if machine changes
CSV_RAW_PATH = Path(r"C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed")
IMAGES_PATH  = Path(r"C:\Users\opentrons\Documents\auto-membranes\images")
SERVER_IP    = "169.254.230.148"
SERVER_PORT  = 8000
CAMERA_INDEX = 2  # change if wrong camera after restart or replug
# ──────────────────────────────────────────────────────────────────────────────

def take_snapshot():
    ret, img = cam.read()
    if ret:
        # IMAGES_PATH, not a relative "images" -- must match get_last_set_img()'s read path
        # exactly, or snapshots silently land wherever the script's CWD happens to be instead
        # of where move_and_rename() looks for them.
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cv2.imwrite(str(IMAGES_PATH / f"{ts}.jpg"), img)
    else:
        print("Error: unable to take picture")

def get_last_set_csv():
    # Reps per condition varies by protocol -- 8 is today's number, not a hard rule. Since
    # CSV_RAW_PATH accumulates every specimen ever tested with no per-run boundary, any condition
    # that runs more than this constant loses its earliest specimens silently (they fall outside
    # the tail slice). Bump this if the protocol's rep count changes again.
    REPS_PER_CONDITION = 8
    files = sorted(CSV_RAW_PATH.glob("**/*.csv"), key=os.path.getctime)
    return files[-REPS_PER_CONDITION:]

def get_last_set_img():
    files = sorted(IMAGES_PATH.glob("*.jpg"), key=os.path.getctime)
    return files[-2:]

def _next_iteration_params():
    """Next fixed-sweep params, clamped to the feasible triangle via bounds.test_target().
    Sweeps ADDITIVE_ITERATION_LIST and/or POLYMER_ITERATION_LIST in lockstep by index
    depending on which of ITERATE_ADDITIVES/ITERATE_POLYMER is on (see their comment above).
    If neither is on (pure-test forced fallback), defaults to sweeping additive alone -- the
    original single-axis behavior. Returns None once the active list(s) are exhausted."""
    global _iteration_count
    sweep_additive = ITERATE_ADDITIVES or not ITERATE_POLYMER
    active_lengths = []
    if sweep_additive:
        active_lengths.append(len(ADDITIVE_ITERATION_LIST))
    if ITERATE_POLYMER:
        active_lengths.append(len(POLYMER_ITERATION_LIST))
    total_steps = min(active_lengths)
    if _iteration_count >= total_steps:
        print(f"[ITERATE] all {total_steps} iteration step(s) exhausted — no more experiments to send")
        return None
    additive_wt = ADDITIVE_ITERATION_LIST[_iteration_count] if sweep_additive else 0
    target_polymer_wt = (
        POLYMER_ITERATION_LIST[_iteration_count] if ITERATE_POLYMER else ITERATION_BASE_PARAMS["polymer_wt"]
    )
    _iteration_count += 1
    p, a = activeLearning.bounds.test_target(target_polymer_wt, additive_wt)
    if p != target_polymer_wt or a != additive_wt:
        print(f"\nIteration params out of range -- ({target_polymer_wt}, {additive_wt})")
        print(f"CLOSEST POINT: | {p:.2f} pwt% | {a:.2f} awt% |\n-----------------------------------\n")
    return {**ITERATION_BASE_PARAMS, "polymer_wt": p, "additive_wt": a}

def _fmt_num(v):
    """Format a numeric param for use in a folder name -- no literal '.' (a dot like
    "21.0-0.0add" reads as a file extension to some tools and complicates path parsing), and no
    redundant trailing ".0" for whole numbers. Genuine fractions use 'p' in place of the dot
    (e.g. 0.5 -> "0p5")."""
    f = float(v)
    if f == int(f):
        return str(int(f))
    return str(f).replace(".", "p")


def move_and_rename(params):
    s = f"{_fmt_num(params['polymer_wt'])}-{_fmt_num(params['additive_wt'])}add-"
    if params["additive_wt"] != 0:
        s += f"{_fmt_num(params['mixing_temp'])}degMix-"
    s += f"{_fmt_num(params['bath_temp'])}deg-"
    s += f"{_fmt_num(params['coupon_to_bath_wait_time'])}s-"
    if not params["nitrogen"]:
        s += "No"
    s += "N2-"
    s += f"{_fmt_num(params['nips_bath_wait_time'])}s"
    base = DATA_ROOT / "data/raw" / s  # <<< FOLDER NAME >>>
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


def _load_resume_params_for_campaign(campaign_date):
    """Load the most recent saved next params for a given campaign date."""
    llm_csv = DATA_ROOT / "data" / "results" / f"begins_{campaign_date}" / "llm.csv"
    if not llm_csv.exists() or llm_csv.stat().st_size == 0:
        raise FileNotFoundError(
            f"Cannot continue campaign {campaign_date}: missing/empty {llm_csv}"
        )

    with llm_csv.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(
            f"Cannot continue campaign {campaign_date}: {llm_csv} has no data rows"
        )

    last_condition = None
    for row in reversed(rows):
        name = (row.get("name") or "").strip()
        if name:
            last_condition = name
            break
    if not last_condition:
        raise ValueError(
            f"Cannot continue campaign {campaign_date}: no condition name found in {llm_csv}"
        )

    llm_result = JSON_RESULTS_DIR / f"llm_result_{last_condition}.json"
    if not llm_result.exists() or llm_result.stat().st_size == 0:
        raise FileNotFoundError(
            f"Cannot continue campaign {campaign_date}: missing/empty {llm_result}"
        )

    with llm_result.open(encoding="utf-8") as f:
        params = json.load(f)
    if not isinstance(params, dict):
        raise ValueError(f"Resume params in {llm_result} must be a JSON object")

    params = {k: v for k, v in params.items() if k != "stock_metadata"}
    _validate_params(params)
    print(f"Resuming campaign {campaign_date} from {llm_result.name}")
    return params


def _run_pipeline_and_trigger_next(params, protocol_log=None):
    # robot echoes back whatever we posted, including stock_metadata — strip it here so
    # it never reaches params.json / move_and_rename / the CSV pipeline
    params = {k: v for k, v in params.items() if k != "stock_metadata"}
    _t0 = time.time()
    if protocol_log:
        print("── PROTOCOL LOG (Opentrons) " + "─" * 40)
        for line in protocol_log:
            print(line)
        print("── END PROTOCOL LOG " + "─" * 47)
    # "iterating" covers both explicit sweep modes and the no-branch pure-test case (a pure
    # test collects no data, so there's nothing for active learning to act on -- it has to
    # sweep a fixed list instead). Report generation and the LLM_AL call always run regardless
    # of this flag -- it only decides whose params (LLM's vs the sweep list's) actually get
    # sent to the next physical test, and whether an unparseable LLM suggestion is fatal.
    iterating = ITERATE_ADDITIVES or ITERATE_POLYMER or not master_processing.any_branch_enabled()

    try:
        condition_name = None
        line = "\n-----------------------------------\n"
        print("\n[1/5] organising files...")
        condition_name = move_and_rename(params)

        print(f"[START] condition={condition_name}")
        print(f"[2/5] processing pipeline for: {condition_name}")
        # csv_paths must be passed explicitly -- without it, _run_curve_segmentation falls back
        # to its own hardcoded flat data/results/results_agg_llm.csv (no CONTINUE_CAMPAIGN
        # begins_<d> folder), completely bypassing CSV_REPS/CSV_AGG/CSV_AGG_LLM below. That split
        # curve_segmentation's formatted_parameters_withProp off into a different file than
        # everything else in this function writes to.
        branch_results = master_processing.run_branches(
            condition_name, DATA_ROOT, csv_paths=(CSV_REPS, CSV_AGG, CSV_AGG_LLM)
        )

        llm_context.scrub_raw_result_columns(CSV_AGG_LLM)
        condition_dir = master_processing.get_condition_dir(condition_name, DATA_ROOT)
        llm_context.ensure_condition_row(condition_name, condition_dir, CSV_AGG_LLM)
        llm_context.attach_all_branch_results(condition_name, branch_results, master_processing.BRANCH_CONFIG,
                                               CSV_AGG, CSV_AGG_LLM)

        print("[3/5] generating initial report...")
        if not CSV_AGG_LLM.exists() or CSV_AGG_LLM.stat().st_size == 0:
            raise ValueError(f"LLM CSV missing or empty after promote_to_main: {CSV_AGG_LLM}")

        print("[4/5] running active learning...")
        params_suggestion = llm_context.generate_reports_and_suggestion(
            condition_name, CSV_AGG_LLM, activeLearning,
            locked_additive_wt=LOCK_ADDITIVE_WT_VALUE if LOCK_ADDITIVE_WT else None,
            al_search_mode=LLM_AL_SEARCH_MODE,
            exploration_history_points=LLM_AL_EXPLORATION_HISTORY_POINTS,
        )

        llm_new_params = None
        try:
            llm_new_params = _extract_next_params(params_suggestion)
        except ValueError as e:
            if not iterating:
                raise
            print(f"[WARN] {condition_name}  LLM suggestion unusable, ignoring "
                  f"(iteration mode drives next params): {e}")

        if iterating:
            new_params = _next_iteration_params()
            if new_params is None:
                return
        else:
            new_params = llm_new_params

            if LOCK_ADDITIVE_WT and new_params["additive_wt"] != LOCK_ADDITIVE_WT_VALUE:
                print(f"[LOCK_ADDITIVE_WT] LLM suggested additive_wt={new_params['additive_wt']}, "
                      f"forcing to {LOCK_ADDITIVE_WT_VALUE}")
                new_params["additive_wt"] = LOCK_ADDITIVE_WT_VALUE

            # snap to feasible triangle
            p, a = activeLearning.bounds.test_target(new_params["polymer_wt"], new_params["additive_wt"])
            if p != new_params["polymer_wt"] or a != new_params["additive_wt"]:
                print(f"\nLLM params out of range -- ({new_params['polymer_wt']}, {new_params['additive_wt']})")
                print(f"CLOSEST POINT: | {p:.2f} pwt% | {a:.2f} awt% |{line}")

            new_params["polymer_wt"] = p
            new_params["additive_wt"] = a

        _validate_params(new_params)

        # attach stock class metadata so the opentrons server has it alongside the params
        new_params["stock_metadata"] = activeLearning.bounds.send_metadata()

        JSON_RESULTS_DIR.mkdir(exist_ok=True)
        json_out = JSON_RESULTS_DIR / f"llm_result_{condition_name}.json"  # <<< PATH >>>
        with open(json_out, "w") as f:
            json.dump(new_params, f, indent=2)
        print(f"  JSON result: {json_out}")

        print(f"[5/5] next params: {new_params}")
        url.run_test(new_params)
        print(f"[DONE] {condition_name}  elapsed={time.time()-_t0:.1f}s")

    except json.JSONDecodeError:
        print(f"[ERROR] {condition_name}  JSONDecodeError: active learning returned invalid JSON")
        print("Active learning returned invalid JSON — loop stopped:", params_suggestion)
    except Exception as e:
        print(f"[ERROR] {condition_name}  {type(e).__name__}: {e}")
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
            mtime = os.path.getmtime(latest)
            now = time.time()  # PC's own clock, captured at the moment of the request
            self.wfile.write(json.dumps({
                "safe": safe,
                "time": mtime,          # kept for backward compatibility / debugging
                "current time": now,              # PC's clock at request time -- lets caller detect skew
                "age": now - mtime,      # computed entirely on the PC's clock -- no cross-machine math needed
            }).encode())

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
            params = body.get("parameters", body)  # new format: {"parameters": {...}, "protocol_log": [...]}
            protocol_log = body.get("protocol_log", [])
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"true")
            # respond immediately, run pipeline + AL + next trigger in background
            threading.Thread(
                target=_run_pipeline_and_trigger_next,
                args=(params, protocol_log),
                daemon=True,
            ).start()
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    startup(LOCK_ADDITIVE_WT, LOCK_ADDITIVE_WT_VALUE, ITERATE_ADDITIVES, ITERATE_POLYMER, CONTINUE_CAMPAIGN, d)
    _log_path = _REPO_ROOT / "logs" / f"run_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')}.log"
    sys.stdout = _TeeLogger(_log_path, sys.__stdout__)
    sys.stderr = _TeeLogger(_log_path, sys.__stderr__)

    cam = cv2.VideoCapture(CAMERA_INDEX)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    # IMAGES_PATH, not a cwd-relative "images" -- must match take_snapshot()'s write path and
    # get_last_set_img()'s read path, or snapshots land wherever the script happened to be
    # launched from instead of where the rest of the pipeline looks for them.
    IMAGES_PATH.mkdir(parents=True, exist_ok=True)

    master_processing.confirm_settings()

    server = HTTPServer((SERVER_IP, SERVER_PORT), LoopHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"server listening on {SERVER_IP}:{SERVER_PORT}")

    if ITERATE_ADDITIVES or ITERATE_POLYMER or not master_processing.any_branch_enabled():
        first_params = _next_iteration_params()
        if first_params is None:
            print("[ITERATE] iteration list(s) empty — nothing to run")
            sys.exit(1)
    elif CONTINUE_CAMPAIGN is not None:
        first_params = _load_resume_params_for_campaign(d)
    else:
        first_params = dict(INITIAL_PARAMS)

    first_params["stock_metadata"] = activeLearning.bounds.send_metadata()
    if LOCK_ADDITIVE_WT:
        first_params["additive_wt"] = 0
    print(f"kicking off first experiment: {first_params}")
    url.run_test(first_params)
    print("robot started — loop running. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping server...")
        server.shutdown()
