"""
test_master.py — run the full master_processing dispatcher (all enabled branches) locally
on Mac for one condition, no live robot/compression-tester campaign needed.

Sibling to test_processing.py (curve_segmentation only) and test_imaging.py (image_processing
only) — this one goes through the exact same shared functions run_loop.py calls in production
(llm_context.attach_all_branch_results, llm_context.generate_reports_and_suggestion), so there's
no separate/simplified reimplementation here that could drift from what actually runs live.

Each of the three LLM calls can be stubbed or run for real independently (USE_REAL_GENERATE_REPORT /
USE_REAL_QUALITY_REPORT / USE_REAL_LLM_AL below) -- e.g. flip on only USE_REAL_QUALITY_REPORT to test
a system_prompt.py quality-checker change against a real photo without paying for the other two calls.
Stubbing a call monkeypatches it before the shared functions run -- fast, free, and still exercises
the identical code path either way. Running any of them for real needs OPENROUTER_API_KEY.

Edit DATA_ROOT and CONDITION below, then:
    python test_master.py

Outputs (isolated from test_processing.py's csv_tests/ — same repo root data, different folder
so the two test scripts can't clobber each other's output files):
  - csv_tests_master/test_reps.csv
  - csv_tests_master/test_agg.csv      — full raw "{type}_result" columns live here
  - csv_tests_master/test_agg_llm.csv  — only "{type}_report" summary text (what actually
                                          reaches the LLM via llm_context.build_observations),
                                          no raw column
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pipeline"))  # <<< IMPORT >>> points to src/pipeline where master_processing.py lives
import master_processing as mp                  # <<< IMPORT >>> must be in same folder
import llm_context                              # <<< IMPORT >>> must be in same folder
import activeLearning_29 as activeLearning      # <<< IMPORT >>> must be in same folder

# ── edit these ──────────────────────────────────────────────────────────────
DATA_ROOT = Path(__file__).parent.parent   # real repo root — real data/raw/
CONDITION = '21-0add-5deg-300s-N2-1800s'

# CONDITION names the real folder (data/raw/CONDITION) -- reused across every
# manual run of this script. RUN_NAME is what actually gets written as the "name" for every
# row in the isolated test csvs below, unique per invocation, so rerunning this script never
# overwrites a prior run's row (and its date) -- it just adds a new one, same way production
# never overwrites either (move_and_rename gives every real test its own _run2/_run3 folder
# before any of this runs). Only the two isolated csv_tests_master/ files are affected.
RUN_NAME = f"{CONDITION}__test-{datetime.now():%Y%m%d-%H%M%S}"

# Flip each independently -- True = real call (costs API, needs OPENROUTER_API_KEY), False = stub.
USE_REAL_GENERATE_REPORT = True   # activeLearning_29.Generate_report (experimental-report text)
USE_REAL_QUALITY_REPORT  = True   # membrane_quality_llm.Generate_quality_report (vision QC on photo)
USE_REAL_LLM_AL          = True   # activeLearning_29.LLM_AL (next-params suggestion)

# Which branches this test run exercises -- separate from master_processing.BRANCH_CONFIG's
# production defaults, overridden here for this script only (doesn't touch master_processing.py).
RUN_CURVE_SEGMENTATION = mp.BRANCH_CONFIG["curve_segmentation"]["enabled"]  # performance branch
RUN_IMAGE_PROCESSING   = mp.BRANCH_CONFIG["image_processing"]["enabled"]   # quality branch
# <<< PATH >>> output files land beside this script, isolated from test_processing.py's csv_tests/
CSV_DIR   = Path(__file__).parent / "csv_tests_master"
CSV_DIR.mkdir(exist_ok=True)
CSV_PATHS = (CSV_DIR / "test_reps.csv", CSV_DIR / "test_agg.csv", CSV_DIR / "test_agg_llm.csv")
REPS_CSV, AGG_CSV, AGG_LLM_CSV = CSV_PATHS
# ────────────────────────────────────────────────────────────────────────────

if not USE_REAL_GENERATE_REPORT:
    activeLearning.Generate_report = lambda fmt_params, *a, **kw: "STUB initial report"

if not USE_REAL_LLM_AL:
    # keys match the current PARAMS_SCHEMA (run_loop.py) -- polymer_wt/additive_wt, not the old
    # weight_percent/volume schema
    activeLearning.LLM_AL = lambda perf, ranges, quality_observations=None, *a, **kw: (
        '[{"next_params": {"mixing_temp": 60, "bath_temp": 5, "polymer_wt": 17, "additive_wt": 2, '
        '"pullcast_speed": 1, "nitrogen": true, '
        '"coupon_to_bath_wait_time": 600, "nips_bath_wait_time": 1800}}]'
    )

if not USE_REAL_QUALITY_REPORT:
    llm_context.generate_quality_report_text = lambda result: "STUB quality report"

mp.BRANCH_CONFIG["curve_segmentation"]["enabled"] = RUN_CURVE_SEGMENTATION
mp.BRANCH_CONFIG["image_processing"]["enabled"] = RUN_IMAGE_PROCESSING


def _short(p):
    """Print paths starting after the repo root folder (Auto-Membranes/...) instead of
    the full absolute path — terminal display only, stored values stay untouched."""
    try:
        return str(Path(p).relative_to(DATA_ROOT))
    except ValueError:
        return str(p)


print(f"Data root : {_short(DATA_ROOT)}")
print(f"Condition : {CONDITION}")
print(f"Run name  : {RUN_NAME}")
print(f"Branches  : {[n for n, c in mp.BRANCH_CONFIG.items() if c['enabled']]}")
print()

branch_results = mp.run_branches(CONDITION, data_root=DATA_ROOT, csv_paths=CSV_PATHS)

llm_context.scrub_raw_result_columns(AGG_LLM_CSV)

# curve_segmentation's promote_condition (inside run_branches, if that branch is enabled) writes
# its row into AGG_LLM_CSV under the real CONDITION name -- it has to, since it needs the actual
# data/raw/CONDITION folder to find params.json and the specimen CSVs; RUN_NAME isn't a real
# folder on disk. Rename that row to RUN_NAME now, before anything else touches AGG_LLM_CSV, so
# every call below agrees on one identity for this run. Otherwise the real
# formatted_parameters_withProp outcome (this row) and the quality report (attached below, under
# RUN_NAME) end up split across two separate rows, and generate_reports_and_suggestion -- which
# only ever writes final_report for whichever single row it's told to match -- never writes
# final_report for this one, so its outcome text silently never reaches the LLM.
if "curve_segmentation" in branch_results and AGG_LLM_CSV.exists() and AGG_LLM_CSV.stat().st_size > 0:
    llm_df = pd.read_csv(AGG_LLM_CSV)
    mask = llm_df["name"] == CONDITION
    if mask.any():
        llm_df.loc[mask, "name"] = RUN_NAME
        llm_df.to_csv(AGG_LLM_CSV, index=False)

condition_dir = mp.get_condition_dir(CONDITION, DATA_ROOT)
llm_context.ensure_condition_row(RUN_NAME, condition_dir, AGG_LLM_CSV)
# Note: this still passes RUN_NAME (not CONDITION) for AGG_CSV, so a non-performance branch's
# result won't merge onto an existing curve_segmentation row there even if one exists for
# CONDITION -- that merge needs the same name on both sides. Only matters if you flip
# RUN_CURVE_SEGMENTATION on; harmless no-op otherwise (today's default) and AGG_CSV isn't what
# reaches the LLM anyway (see AGG_LLM_CSV rename above, which is the side that matters).
llm_context.attach_all_branch_results(RUN_NAME, branch_results, mp.BRANCH_CONFIG, AGG_CSV, AGG_LLM_CSV)

print(f"branches ran: {list(branch_results.keys())}")

for branch_name, result in branch_results.items():
    branch_type = mp.BRANCH_CONFIG[branch_name]["type"]
    if branch_type == "performance":
        print(f"{branch_name} (performance) output keys: {list(result.keys())}")
        continue
    display_result = {k: v for k, v in result.items() if k != "uniform_map"}
    if "image_path" in display_result:
        display_result["image_path"] = _short(display_result["image_path"])
    print(f"{branch_name} ({branch_type}) result:")
    print(json.dumps(display_result, indent=2))

print(f"\nReps CSV    : {_short(REPS_CSV)}")
print(f"Agg CSV     : {_short(AGG_CSV)}")
print(f"Agg LLM CSV : {_short(AGG_LLM_CSV)}")

if AGG_CSV.exists():
    agg_df = pd.read_csv(AGG_CSV)
    agg_matches = agg_df[agg_df["name"].isin(
        [CONDITION, f"{CONDITION}_preDiscard", f"{CONDITION}_postDiscard"]
    )]
    if not agg_matches.empty:
        row = agg_matches.iloc[-1]
        print(f"\n{_short(AGG_CSV)} row for {CONDITION} ({row['name']}):")
        for branch_name in branch_results:
            branch_type = mp.BRANCH_CONFIG[branch_name]["type"]
            if branch_type == "performance":
                continue
            result_col = f"{branch_type}_result"
            raw = row.get(result_col)
            print(f"  {result_col}:")
            if isinstance(raw, str):
                parsed = json.loads(raw)
                if "image_path" in parsed:
                    parsed["image_path"] = _short(parsed["image_path"])
                for line in json.dumps(parsed, indent=2).splitlines():
                    print(f"    {line}")
            else:
                print(f"    {raw}")
    else:
        print(f"\nWARNING: no row for {CONDITION!r} in {_short(AGG_CSV)}")

if AGG_LLM_CSV.exists():
    llm_df = pd.read_csv(AGG_LLM_CSV)
    matches = llm_df[llm_df["name"] == RUN_NAME]
    if not matches.empty:
        row = matches.iloc[-1]
        print(f"\n{_short(AGG_LLM_CSV)} row for {RUN_NAME}:")
        for branch_name in branch_results:
            branch_type = mp.BRANCH_CONFIG[branch_name]["type"]
            if branch_type == "performance":
                continue
            assert f"{branch_type}_result" not in llm_df.columns, \
                f"raw {branch_type}_result column should not be in the LLM-facing CSV"
            print(f"  {branch_type}_report: {row.get(f'{branch_type}_report')}")
        tail = str(row['formatted_parameters_withProp'])[-200:]
        print(f"  formatted_parameters_withProp (tail): ...{tail}")
        print(f"  formatted_parameters: {row.get('formatted_parameters')}")
    else:
        print(f"\nWARNING: no row named {RUN_NAME!r} in {_short(AGG_LLM_CSV)}")

print("\nbuild_observations:")
for branch_type in {cfg["type"] for cfg in mp.BRANCH_CONFIG.values()}:
    if branch_type == "performance":
        continue
    obs = llm_context.build_observations(AGG_LLM_CSV, branch_type)
    print(f"  {branch_type}: {obs!r}")

# ── dual-LLM check: same shared function run_loop.py calls in production ────────────────────
# run_loop.py now calls this unconditionally regardless of branch config (ensure_condition_row
# builds the fallback row from params.json when curve_segmentation didn't) -- mirrored here.
suggestion = llm_context.generate_reports_and_suggestion(RUN_NAME, AGG_LLM_CSV, activeLearning)
print(f"\nLLM_AL suggestion ({'real' if USE_REAL_LLM_AL else 'stubbed'}, dual-channel):\n{suggestion}")
