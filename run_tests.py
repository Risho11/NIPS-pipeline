"""
run_tests.py — CI-ready test suite for the NIPS processing pipeline.

Tests clustering logic and full pipeline (processing → CSV → LLM → JSON) using
fake-data conditions in compression-test-data/fake-data/.

Usage:
    python run_tests.py                         # all tests, LLM mocked
    python run_tests.py --real-llm              # real API calls
    python run_tests.py --condition short-nips-30s  # single condition

Exit code: 0 if all pass, 1 if any fail.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # <<< IMPORT >>> project root where processing_29.py lives
import processing_29 as processing             # <<< IMPORT >>> must be in same folder

# <<< PATH >>> points INTO compression-test-data, differs from run_loop.py which points to project root
DATA_ROOT      = Path(__file__).parent / "compression-test-data"
FAKE_FOLDER    = "fake-data"  # <<< FOLDER NAME >>> subfolder inside compression-test-data

MOCK_INITIAL_REPORT = (
    "The membrane was synthesized using a polysulfone solution at 17 wt% in PolarClean. "
    "The solution was blade-cast and immersed in a NIPS bath at 13°C for the specified duration."
)
MOCK_LLM_AL_RESPONSE = (
    'I notice from the data that the weight percent significantly affects the data and blahblah blah '
    '{"mixing_temp": 30, "bath_temp": 10, "weight_percent": 15, "pullcast_speed": 8, '
    '"coupon_to_bath_wait_time": 120, "nips_bath_wait_time": 1500, "nitrogen": false}'
)

LLM_PROP_KEYS = ["Strain at 50 bar", "CV"]

REQUIRED_PARAM_KEYS = [
    "mixing_temp", "bath_temp", "weight_percent",
    "pullcast_speed", "coupon_to_bath_wait_time",
    "nips_bath_wait_time", "nitrogen",
]

PARAM_RANGES = {
    "mixing_temp":              (25, 80),
    "bath_temp":                (5, 25),
    "weight_percent":           (10, 17),
    "pullcast_speed":           (1, 20),
    "coupon_to_bath_wait_time": (0, 600),
    "nips_bath_wait_time":      (1200, 1800),
}

EXPECTED_PAIRS = {
    "short-nips-30s":             3,
    "nips-300s-gap-within-zeros": 3,
    "nips-600s-tight-boundary":   3,
    "nips-660s-just-over":        3,
    "nine-per-phase-1800s":       9,
    "double-run-4-clusters":      6,
    "multi-date-two-runs":        6,
    "pipeline-all-pass":          3,
    "pipeline-some-fail":         3,
}

CONDITION_TAGS = {
    "short-nips-30s":             {"clustering"},
    "nips-300s-gap-within-zeros": {"clustering"},
    "nips-600s-tight-boundary":   {"clustering"},
    "nips-660s-just-over":        {"clustering"},
    "nine-per-phase-1800s":       {"clustering"},
    "double-run-4-clusters":      {"clustering"},
    "multi-date-two-runs":        {"clustering"},
    "pipeline-all-pass":          {"pipeline"},
    "pipeline-some-fail":         {"pipeline"},
}

pass_count = 0
fail_count = 0


def report(label, passed, detail=""):
    global pass_count, fail_count
    status = "PASS" if passed else "FAIL"
    pad = max(0, 40 - len(label))
    print(f"  [{status}] {label}{' ' * pad}{detail}")
    if passed:
        pass_count += 1
    else:
        fail_count += 1


def test_clustering(condition, real_llm=False):
    label = f"{condition:35s} clustering"
    expected = EXPECTED_PAIRS[condition]
    try:
        result = processing.load_zero_sample_pairs_by_condition(
            folder_name=FAKE_FOLDER,
            data_root=str(DATA_ROOT),
            strict=True,
            load_dataframes=False,
        )
        if condition not in result:
            report(label, False, f"condition not found in output")
            return
        got = result[condition]["num_pairs"]
        report(label, got == expected, f"expected {expected} pairs, got {got}")
    except Exception as e:
        report(label, False, f"exception: {e}")


def test_full_pipeline(condition, real_llm=False):
    label = f"{condition:35s} full pipeline"
    tmp = tempfile.mkdtemp()
    try:
        tmp_csv         = Path(tmp) / "out.csv"
        tmp_agg_csv     = Path(tmp) / "out_agg.csv"
        tmp_agg_llm_csv = Path(tmp) / "out_agg_llm.csv"
        tmp_json        = Path(tmp) / f"llm_result_{condition}.json"

        # Step 1: process pipeline
        output = processing.process_zero_sample_pairs_pipeline(
            folder_name=FAKE_FOLDER,
            data_root=str(DATA_ROOT),
            strict=True,
            load_cutoff=1.0,
            thickness_info=False,
            thickness_map=None,
            creep_info=True,
            cutoff_load_thickness=1,
            cutoff_load_displacement=2,
            condition_filter=condition,
        )

        # Step 2: save agg CSV and promote one row to LLM CSV
        processing.save_to_csv(output, data_root=DATA_ROOT,
                               output_path=tmp_csv, aggregate_path=tmp_agg_csv)
        import pandas as pd
        _agg = pd.read_csv(tmp_agg_csv)
        _has_post = (_agg["name"] == f"{condition}_postDiscard").any()
        _src = "postDiscard" if _has_post else ""
        processing.promote_to_main(condition, _src, tmp_agg_csv, tmp_agg_llm_csv)

        # Step 3: read LLM CSV (one promoted row per condition)
        if not tmp_agg_llm_csv.exists() or tmp_agg_llm_csv.stat().st_size == 0:
            report(label, False, "Agg LLM CSV not written by promote_to_main")
            return
        llm_df = pd.read_csv(tmp_agg_llm_csv)
        if llm_df.empty:
            report(label, False, "Agg LLM CSV has no rows")
            return
        for col in ["initial_report", "final_report"]:
            if col in llm_df.columns:
                llm_df[col] = llm_df[col].astype(object)
        mask = llm_df["name"] == condition
        idx  = llm_df[mask].index[-1] if mask.any() else llm_df.index[-1]
        fmt_params = llm_df.at[idx, "formatted_parameters"]

        # Step 4: LLM calls (mocked or real)
        mech_subset = {f"{k} Mean": llm_df.at[idx, f"{k} Mean"]
                       for k in LLM_PROP_KEYS
                       if f"{k} Mean" in llm_df.columns and pd.notna(llm_df.at[idx, f"{k} Mean"])}
        fmt_params_with_prop = str(mech_subset)
        if real_llm:
            import activeLearning_29 as al  # <<< IMPORT >>> must be in same folder as run_tests.py
            initial_report    = al.Generate_report(fmt_params)
            final_report      = initial_report + "\n" + fmt_params_with_prop
            params_suggestion = al.LLM_AL(final_report, al.ranges)
        else:
            initial_report    = MOCK_INITIAL_REPORT
            final_report      = initial_report + "\n" + fmt_params_with_prop
            params_suggestion = MOCK_LLM_AL_RESPONSE

        # Step 5: write reports back to agg LLM CSV
        llm_df.at[idx, "initial_report"] = initial_report
        llm_df.at[idx, "formatted_parameters_withProp"] = fmt_params + fmt_params_with_prop
        llm_df.at[idx, "final_report"]   = final_report
        llm_df.at[idx, "LLM_suggestion"] = params_suggestion
        llm_df.to_csv(tmp_agg_llm_csv, index=False)

        # Step 6: parse and write JSON
        match = re.search(r'\{[^{}]*\}', params_suggestion)
        if not match:
            report(label, False, "LLM returned no JSON block")
            return
        new_params = json.loads(match.group(0))
        with open(tmp_json, "w") as f:
            json.dump(new_params, f, indent=2)

        # Validate
        failures = []

        # JSON output must be a flat params dict matching params.json's schema
        # (not wrapped in [{"condition":..., "next_params":...}])
        with open(tmp_json) as f:
            json_params = json.load(f)
        if not isinstance(json_params, dict):
            failures.append(f"llm_result JSON is not a flat params dict (got {type(json_params).__name__})")
            json_params = {}

        # Agg LLM CSV columns and content (one promoted row per condition)
        llm_df2 = pd.read_csv(tmp_agg_llm_csv)
        for col in ["name", "formatted_parameters", "initial_report", "final_report"]:
            if col not in llm_df2.columns:
                failures.append(f"CSV missing column '{col}'")
        row2 = llm_df2[llm_df2["name"] == condition]
        if not row2.empty:
            if not str(row2.iloc[-1]["initial_report"]).strip():
                failures.append("initial_report empty in CSV")
            if not str(row2.iloc[-1]["final_report"]).strip():
                failures.append("final_report empty in CSV")

        # JSON keys
        for key in REQUIRED_PARAM_KEYS:
            if key not in json_params:
                failures.append(f"JSON missing key '{key}'")

        # Range check (real LLM only)
        if real_llm:
            for key, (lo, hi) in PARAM_RANGES.items():
                if key in json_params:
                    val = json_params[key]
                    if not (lo <= val <= hi):
                        failures.append(f"{key}={val} out of range [{lo},{hi}]")

        if failures:
            report(label, False, "; ".join(failures))
        else:
            report(label, True, "CSV written, JSON valid")

    except Exception as e:
        report(label, False, f"exception: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-llm",  action="store_true",
                        help="Use real OpenRouter API instead of mocks")
    parser.add_argument("--condition", default=None,
                        help="Run tests for a single condition only")
    parser.add_argument("--skip", nargs="+", default=[],
                        help="Conditions to skip (e.g. --skip nine-per-phase-1800s)")
    parser.add_argument("--tags", nargs="+", default=None,
                        help="Only run conditions tagged with any of these tags (e.g. --tags clustering pipeline)")
    args = parser.parse_args()

    if args.real_llm:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            print("WARNING: --real-llm set but OPENROUTER_API_KEY not in environment")

    conditions = [args.condition] if args.condition else list(EXPECTED_PAIRS.keys())
    conditions = [c for c in conditions if c not in args.skip]
    if args.tags:
        tag_set = set(args.tags)
        conditions = [c for c in conditions if CONDITION_TAGS.get(c, set()) & tag_set]

    print(f"\nRunning tests ({'real LLM' if args.real_llm else 'mocked LLM'})\n")

    for condition in conditions:
        if condition not in EXPECTED_PAIRS:
            print(f"  [SKIP] {condition}: not in known conditions")
            continue
        test_clustering(condition, real_llm=args.real_llm)
        test_full_pipeline(condition, real_llm=args.real_llm)

    total = pass_count + fail_count
    print(f"\nSummary: {pass_count}/{total} passed")
    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
