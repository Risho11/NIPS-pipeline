"""
test_master.py — run the full master_processing dispatcher (all enabled branches) locally
on Mac for one condition, no live robot/compression-tester campaign needed.

Sibling to test_processing.py (curve_segmentation only) and test_imaging.py (image_processing
only) — this one goes through the exact same shared functions run_loop.py calls in production
(llm_context.attach_all_branch_results, llm_context.generate_reports_and_suggestion), so there's
no separate/simplified reimplementation here that could drift from what actually runs live.

USE_REAL_LLM (below) controls whether that includes real API calls:
  - False (default): activeLearning_29's Generate_report/LLM_AL and llm_context's
    generate_quality_report_text are monkeypatched to stubs before the shared functions run --
    fast, free, and still exercises the identical code path with both observation channels
    (performance + quality) reaching one LLM_AL call.
  - True: real Generate_report + Generate_quality_report (vision LLM) + LLM_AL calls -- costs
    API calls, needs OPENROUTER_API_KEY, verifies the dual-LLM approach end-to-end for real.

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
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))  # <<< IMPORT >>> points to project root where master_processing.py lives
import master_processing as mp                  # <<< IMPORT >>> must be in same folder
import llm_context                              # <<< IMPORT >>> must be in same folder
import activeLearning_29 as activeLearning      # <<< IMPORT >>> must be in same folder

# ── edit these ──────────────────────────────────────────────────────────────
DATA_ROOT = Path(__file__).parent.parent   # real repo root — real compression-test-data/
CONDITION = '17-5deg-600s-N2-1800s'
USE_REAL_LLM = True  # True = real Generate_report + Generate_quality_report + LLM_AL calls
                      # (costs API calls) -- see module docstring above
# <<< PATH >>> output files land beside this script, isolated from test_processing.py's csv_tests/
CSV_DIR   = Path(__file__).parent / "csv_tests_master"
CSV_DIR.mkdir(exist_ok=True)
CSV_PATHS = (CSV_DIR / "test_reps.csv", CSV_DIR / "test_agg.csv", CSV_DIR / "test_agg_llm.csv")
REPS_CSV, AGG_CSV, AGG_LLM_CSV = CSV_PATHS
# ────────────────────────────────────────────────────────────────────────────

if not USE_REAL_LLM:
    activeLearning.Generate_report = lambda fmt_params, *a, **kw: "STUB initial report"
    activeLearning.LLM_AL = lambda perf, ranges, quality_observations=None, *a, **kw: (
        '[{"next_params": {"mixing_temp": 60, "bath_temp": 5, "weight_percent": 17, '
        '"volume": 1000, "pullcast_speed": 1, "nitrogen": true, '
        '"coupon_to_bath_wait_time": 600, "nips_bath_wait_time": 1800}}]'
    )
    llm_context.generate_quality_report_text = lambda result: "STUB quality report"


def _short(p):
    """Print paths starting after the repo root folder (Auto-Membranes/...) instead of
    the full absolute path — terminal display only, stored values stay untouched."""
    try:
        return str(Path(p).relative_to(DATA_ROOT))
    except ValueError:
        return str(p)


print(f"Data root : {_short(DATA_ROOT)}")
print(f"Condition : {CONDITION}")
print(f"Branches  : {[n for n, c in mp.BRANCH_CONFIG.items() if c['enabled']]}")
print()

branch_results = mp.run_branches(CONDITION, data_root=DATA_ROOT, csv_paths=CSV_PATHS)

llm_context.scrub_raw_result_columns(AGG_LLM_CSV)
condition_dir = mp.get_condition_dir(CONDITION, DATA_ROOT)
llm_context.ensure_condition_row(CONDITION, condition_dir, AGG_LLM_CSV)
llm_context.attach_all_branch_results(CONDITION, branch_results, mp.BRANCH_CONFIG, AGG_CSV, AGG_LLM_CSV)

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
    matches = llm_df[llm_df["name"] == CONDITION]
    if not matches.empty:
        row = matches.iloc[-1]
        print(f"\n{_short(AGG_LLM_CSV)} row for {CONDITION}:")
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
        print(f"\nWARNING: no row named {CONDITION!r} in {_short(AGG_LLM_CSV)}")

print("\nbuild_observations:")
for branch_type in {cfg["type"] for cfg in mp.BRANCH_CONFIG.values()}:
    if branch_type == "performance":
        continue
    obs = llm_context.build_observations(AGG_LLM_CSV, branch_type)
    print(f"  {branch_type}: {obs!r}")

# ── dual-LLM check: same shared function run_loop.py calls in production ────────────────────
if "curve_segmentation" in branch_results:
    suggestion = llm_context.generate_reports_and_suggestion(CONDITION, AGG_LLM_CSV, activeLearning)
    print(f"\nLLM_AL suggestion ({'real' if USE_REAL_LLM else 'stubbed'}, dual-channel):\n{suggestion}")
else:
    print("\n(curve_segmentation disabled — no formatted_parameters row to build a suggestion "
          "from; generate_reports_and_suggestion needs the performance branch's row)")
