"""
test_processing.py — run processing pipeline locally on Mac for one condition.

Edit DATA_ROOT and CONDITION below, then:
    python test_processing.py

Outputs:
  - pipeline_plots_YYYY-MM-DD/<condition>/  — PNG plots
  - test_output.csv                         — per-rep mechanical properties
  - test_llm_output.csv                     — LLM scaffold (averages, filled after API call)
  - test_llm_result.json                    — parsed next-experiment params from LLM
"""

import os, sys, json, re
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import processing_29 as processing
import activeLearning_29 as al

# ── edit these ──────────────────────────────────────────────────────────────
DATA_ROOT  = Path(__file__).parent.parent / "Auto-Membranes/"
CONDITION  = "17-13deg-10s-N2-30s"
OUTPUT_CSV = Path(__file__).parent / "test_output3.csv"
LLM_CSV    = Path(__file__).parent / "test_llm_output.csv"
JSON_OUT   = Path(__file__).parent / "test_llm_result.json"
# ────────────────────────────────────────────────────────────────────────────

print(f"Data root : {DATA_ROOT}")
print(f"Condition : {CONDITION}")
print()

output = processing.process_zero_sample_pairs_pipeline(
    folder_name="compression-test-data/fake-data",
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

processing.save_to_csv(output, data_root=DATA_ROOT, output_path=OUTPUT_CSV, aggregate_path=LLM_CSV)
print(f"\nReps CSV : {OUTPUT_CSV}")
print(f"LLM CSV  : {LLM_CSV}")

# ── LLM calls ───────────────────────────────────────────────────────────────
MECH_KEYS = ["Strain at 50 bar", "Strain at 80 bar", "Strain at 150 bar",
             "Strain at 500 bar", "CV"]

print("\n" + "=" * 80)
print("RUNNING LLM CALLS")
print("=" * 80)

if not LLM_CSV.exists() or LLM_CSV.stat().st_size == 0:
    raise FileNotFoundError(f"LLM CSV missing or empty after save_to_csv — check CONDITION matches a folder in old_data: {LLM_CSV}")
llm_df = pd.read_csv(LLM_CSV)
if llm_df.empty:
    raise ValueError(f"LLM CSV has no data rows: {LLM_CSV}")
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

mech_dict = {k: row[k] for k in MECH_KEYS if k in row and pd.notna(row[k])}
fmt_params_with_prop = str(mech_dict)
llm_df.at[idx, "formatted_parameters_withProp"] = fmt_params_with_prop

final_report = initial + "\n" + fmt_params_with_prop
llm_df.at[idx, "final_report"] = final_report
#params_suggestion = al.LLM_AL(final_report, al.ranges)
params_suggestion = 'Based on the observations, I recommend the following parameters: {"mixing_temp": 25, "bath_temp": 10, "weight_percent": 18, "pullcast_speed": 10, "coupon_to_bath_wait_time": 120, "nips_bath_wait_time": 1800, "nitrogen": true}'
print(f"  params_suggestion: {params_suggestion[:120]}...")

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

llm_df.to_csv(LLM_CSV, index=False)
print(f"\nLLM CSV updated: {LLM_CSV}")

with open(JSON_OUT, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nJSON output: {JSON_OUT}")
print(json.dumps(results, indent=2))
