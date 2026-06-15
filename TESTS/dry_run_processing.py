# dry_run_processing.py
#
# Dry run of the processing_29 + active-learning steps from run_loop.py's
# _run_pipeline_and_trigger_next(), run on a real condition folder under
# compression-test-data/.
#
# Only imports from processing_29 / activeLearning_29 - does not modify
# either module (other than toggling the documented
# `processing_29.SAVE_PLOTS` flag, see processing_29.py line 27).
#
# DRY_RUN_PROCESSING (bool):
#   True  (default) - don't save plots and don't write any CSVs
#                      (results_reps.csv / results_agg.csv / results_agg_llm.csv
#                      are untouched). formatted_parameters and mechanical
#                      property means are computed directly from the
#                      in-memory pipeline output.
#   False           - normal behaviour: plots are saved and
#                      save_to_csv()/promote_to_main() write to
#                      TESTS/csv_tests/dryrun_*.csv (like test_processing.py).
#
# Either way, Generate_report() and LLM_AL() are called for real, and the
# next suggested parameters are printed (and written to
# TESTS/csv_tests/dry_run_llm_params.json).
#
# Usage:
#   python TESTS/dry_run_processing.py

import sys, json, re
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # <<< IMPORT >>> points to project root where processing_29.py lives
import processing_29 as processing             # <<< IMPORT >>> must be in same folder
import activeLearning_29 as activeLearning     # <<< IMPORT >>> must be in same folder

# ── edit these ──────────────────────────────────────────────────────────────
DRY_RUN_PROCESSING = True

DATA_ROOT = Path(__file__).parent.parent
CONDITION = "17-13deg-10s-NoN2-40s"
FOLDER_NAME = "compression-test-data"

# only used when DRY_RUN_PROCESSING is False
OUTPUT_CSV  = Path(__file__).parent / "csv_tests" / "dryrun_reps.csv"
AGG_CSV     = Path(__file__).parent / "csv_tests" / "dryrun_agg.csv"
AGG_LLM_CSV = Path(__file__).parent / "csv_tests" / "dryrun_agg_llm.csv"

JSON_OUT = Path(__file__).parent / "csv_tests" / "dry_run_llm_params.json"

LLM_PROP_KEYS = ["Strain at 50 bar", "CV"]  # <<< must match run_loop.py's LLM_PROP_KEYS
# ────────────────────────────────────────────────────────────────────────────


def _fix_json_literals(s):
    """Normalize Python-style True/False/None to JSON true/false/null (same as run_loop.py)."""
    return re.sub(r'\b(True|False|None)\b',
                   lambda m: {'True': 'true', 'False': 'false', 'None': 'null'}[m.group(0)],
                   s)


if DRY_RUN_PROCESSING:
    processing.SAVE_PLOTS = False  # toggling the documented module flag, not editing processing_29.py

print(f"Data root : {DATA_ROOT}")
print(f"Condition : {CONDITION}")
print(f"Dry run processing : {DRY_RUN_PROCESSING}")
print()

output = processing.process_zero_sample_pairs_pipeline(
    folder_name=FOLDER_NAME,
    data_root=str(DATA_ROOT),
    strict=False,
    load_cutoff=1.0,
    thickness_info=False,
    thickness_map=None,
    creep_info=True,
    cutoff_load_thickness=1,
    cutoff_load_displacement=2,
    condition_filter=CONDITION,
)

if CONDITION not in output or not output[CONDITION]["mechanical_properties"]:
    raise ValueError(f"No processed data for condition {CONDITION!r} under {FOLDER_NAME!r}")

if DRY_RUN_PROCESSING:
    # build formatted_parameters + mechanical property means straight from
    # the in-memory pipeline output, without writing any CSVs
    params_path = DATA_ROOT / FOLDER_NAME / CONDITION / "params.json"
    with open(params_path) as f:
        params = json.load(f)

    fmt_params = processing.formatted_parameters(params)

    avg_props = next(p for p in output[CONDITION]["mechanical_properties"] if p.get("Trial") == "average")
    mech_subset = {
        f"{k} Mean": avg_props[k]
        for k in LLM_PROP_KEYS
        if k in avg_props and avg_props[k] is not None and not (isinstance(avg_props[k], float) and np.isnan(avg_props[k]))
    }
else:
    processing.save_to_csv(output, data_root=DATA_ROOT, output_path=OUTPUT_CSV, aggregate_path=AGG_CSV)

    _agg_df = pd.read_csv(AGG_CSV)
    _has_post = (_agg_df["name"] == f"{CONDITION}_postDiscard").any()
    _source = "postDiscard" if _has_post else ""
    processing.promote_to_main(CONDITION, _source, AGG_CSV, AGG_LLM_CSV)

    llm_df = pd.read_csv(AGG_LLM_CSV)
    idx = llm_df[llm_df["name"] == CONDITION].index[-1]
    fmt_params = llm_df.at[idx, "formatted_parameters"]
    mech_subset = {
        f"{k} Mean": llm_df.at[idx, f"{k} Mean"]
        for k in LLM_PROP_KEYS
        if f"{k} Mean" in llm_df.columns and pd.notna(llm_df.at[idx, f"{k} Mean"])
    }

    params_path = DATA_ROOT / FOLDER_NAME / CONDITION / "params.json"
    with open(params_path) as f:
        params = json.load(f)

print("\n" + "=" * 80)
print("RUNNING ACTIVE LEARNING")
print("=" * 80)

print("\ngenerating initial report...")
initial_report = activeLearning.Generate_report(fmt_params)
print(f"  initial_report: {initial_report[:120]}...")

fmt_params_with_prop = str(mech_subset)
final_report = initial_report + "\n" + fmt_params_with_prop

if not DRY_RUN_PROCESSING:
    llm_df.at[idx, "initial_report"] = initial_report
    llm_df.at[idx, "formatted_parameters_withProp"] = fmt_params + fmt_params_with_prop
    llm_df.at[idx, "final_report"] = final_report
    llm_df.to_csv(AGG_LLM_CSV, index=False)

print("\nrunning active learning...")
params_suggestion = activeLearning.LLM_AL(final_report, activeLearning.ranges)
print(f"  params_suggestion: {params_suggestion[:200]}...")

if not DRY_RUN_PROCESSING:
    llm_df.at[idx, "LLM_suggestion"] = params_suggestion
    llm_df.to_csv(AGG_LLM_CSV, index=False)

match = re.search(r'\{[^{}]*\}', params_suggestion)
if not match:
    raise ValueError(f"LLM returned no JSON object:\n{params_suggestion}")
new_params = json.loads(_fix_json_literals(match.group(0)))

# carry over + type-coerce against the current condition's params, same as run_loop.py
for key in params:
    new_params.setdefault(key, params[key])

for key, reference in params.items():
    if isinstance(reference, bool):
        new_params[key] = bool(new_params[key])
    elif isinstance(reference, int):
        new_params[key] = int(new_params[key])

JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
with open(JSON_OUT, "w") as f:
    json.dump(new_params, f, indent=2)

print(f"\nnext params: {json.dumps(new_params, indent=2)}")
print(f"\nJSON output: {JSON_OUT}")
