"""
test_processing.py — run processing pipeline locally on Mac for one condition.

Edit DATA_ROOT and CONDITION below, then:
    python test_processing.py

Outputs:
  - pipeline_plots_YYYY-MM-DD/<condition>/  — PNG plots
  - test_reps.csv                           — per-rep mechanical properties
  - test_agg.csv                            — full aggregated CSV (pre+post rows when failures)
  - test_agg_llm.csv                        — one promoted row per condition (sent to LLM)
  - test_llm_params.json                    — parsed next-experiment params from LLM
"""

import sys, json, re
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # <<< IMPORT >>> points to project root where processing_29.py lives
import processing_29 as processing             # <<< IMPORT >>> must be in same folder
#import activeLearning_29 as al                 # <<< IMPORT >>> must be in same folder

# ── edit these ──────────────────────────────────────────────────────────────
# <<< PATH >>> Chooses condition.
DATA_ROOT  = Path(__file__).parent.parent 
CONDITION  = "10-25degMix-25deg-0s-NoN2-1800s"
# <<< PATH >>> output files land beside this script
OUTPUT_CSV  = Path(__file__).parent / "csv_tests" / "test_reps.csv"
AGG_CSV     = Path(__file__).parent / "csv_tests" / "test_agg.csv"
AGG_LLM_CSV = Path(__file__).parent / "csv_tests" / "test_agg_llm.csv"
JSON_OUT    = Path(__file__).parent / "csv_tests" / "test_llm_params.json"
# ────────────────────────────────────────────────────────────────────────────

print(f"Data root : {DATA_ROOT}")
print(f"Condition : {CONDITION}")
print()

output = processing.process_zero_sample_pairs_pipeline(
    folder_name="compression-test-data",  # <<< FOLDER NAME >>>
    data_root=str(DATA_ROOT),
    strict=True,
    load_cutoff=1.0,
    thickness_info=False,
    thickness_map=None,
    creep_info=True,
    cutoff_load_thickness=1,
    cutoff_load_displacement=2,
    condition_filter=CONDITION,
)

processing.save_to_csv(output, data_root=DATA_ROOT, output_path=OUTPUT_CSV, aggregate_path=AGG_CSV)

_agg_df = pd.read_csv(AGG_CSV)
_has_post = (_agg_df["name"] == f"{CONDITION}_postDiscard").any()
_source = "postDiscard" if _has_post else ""
# Change _source to "preDiscard" to promote the pre-discard version instead
processing.promote_to_main(CONDITION, _source, AGG_CSV, AGG_LLM_CSV)

print(f"\nReps CSV    : {OUTPUT_CSV}")
print(f"Agg CSV     : {AGG_CSV}")
print(f"Agg LLM CSV : {AGG_LLM_CSV}")

# ── LLM calls ───────────────────────────────────────────────────────────────
LLM_PROP_KEYS = ["Strain at 50 bar", "Strain at 80 bar", "Strain at 150 bar", "Strain at 500 bar", "CV"]

print("\n" + "=" * 80)
print("RUNNING LLM CALLS")
print("=" * 80)

if not AGG_LLM_CSV.exists() or AGG_LLM_CSV.stat().st_size == 0:
    raise FileNotFoundError(f"Agg LLM CSV missing or empty after promote_to_main — check CONDITION matches a folder: {AGG_LLM_CSV}")
llm_df = pd.read_csv(AGG_LLM_CSV)
if llm_df.empty:
    raise ValueError(f"Agg LLM CSV has no data rows: {AGG_LLM_CSV}")
for col in ["formatted_parameters_withProp", "initial_report", "final_report"]:
    if col in llm_df.columns:
        llm_df[col] = llm_df[col].astype(object)
idx = llm_df.index[-1]
row = llm_df.iloc[-1]
print(f"\nCondition: {row['name']}")

#initial = al.Generate_report(row["formatted_parameters"])
initial = "this is the initial report thingy there is experiment and these are parameters and stuff"
llm_df.at[idx, "initial_report"] = initial
print(f"  initial_report: {initial[:120]}...")

mech_subset = {f"{k} Mean": row[f"{k} Mean"]
               for k in LLM_PROP_KEYS
               if f"{k} Mean" in llm_df.columns and pd.notna(row[f"{k} Mean"])}
fmt_params_with_prop = str(mech_subset) if mech_subset else "WARNING: all replicates had bad fits — all mechanical properties NaN"
final_report = initial + "\n" + fmt_params_with_prop
fmt_params = str(row["formatted_parameters"]) if pd.notna(row["formatted_parameters"]) else ""
llm_df.at[idx, "formatted_parameters_withProp"] = fmt_params + "\n\n" + fmt_params_with_prop
llm_df.at[idx, "final_report"] = final_report
#params_suggestion = al.LLM_AL(final_report, al.ranges)
params_suggestion = 'Based on the observations, I recommend the following parameters: {"mixing_temp": 25, "bath_temp": 10, "weight_percent": 18, "pullcast_speed": 10, "coupon_to_bath_wait_time": 120, "nips_bath_wait_time": 1800, "nitrogen": true}'
print(f"  params_suggestion: {params_suggestion[:120]}...")
llm_df.at[idx, "LLM_suggestion"] = params_suggestion
match = re.search(r'\{[^{}]*\}', params_suggestion)
if not match:
    print(f"  WARNING: no JSON found:\n{params_suggestion}")
    results = [{"condition": row["name"], "next_params": None, "raw": params_suggestion}]
else:
    try:
        parsed = json.loads(match.group(0))
        print(f"  next_params: {parsed}")
        results = [{"condition": row["name"], "next_params": parsed}]
    except json.JSONDecodeError as e:
        print(f"  WARNING: JSON parse failed ({e}):\n{match.group(0)}")
        results = [{"condition": row["name"], "next_params": None, "raw": params_suggestion}]

llm_df.to_csv(AGG_LLM_CSV, index=False)
print(f"\nAgg LLM CSV updated: {AGG_LLM_CSV}")

with open(JSON_OUT, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nJSON output: {JSON_OUT}")
print(json.dumps(results, indent=2))