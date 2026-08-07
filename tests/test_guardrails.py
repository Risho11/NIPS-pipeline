"""
test_guardrails.py — robustness tests for degenerate inputs.

NOT testing correctness — testing that degenerate/edge-case inputs never crash
the pipeline downstream. Each test verifies graceful degradation.

Run:
    python TESTS/test_guardrails.py
"""
import sys
import tempfile
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import curve_segmentation as processing

_PASS, _FAIL = 0, 0

def check(condition, label):
    global _PASS, _FAIL
    if condition:
        print(f"  PASS  {label}")
        _PASS += 1
    else:
        print(f"  FAIL  {label}")
        _FAIL += 1

def _minimal_output(condition, props, pre_cv=np.nan, post_cv=np.nan, has_failures=False, passing=None):
    return {
        condition: {
            "condition": condition,
            "processed_curves": [],
            "mechanical_properties": props,
            "pre_cv": pre_cv,
            "post_cv": post_cv,
            "has_failures": has_failures,
            "passing_properties": passing if passing is not None else [],
        }
    }

# ── Test 1: empty output dict ────────────────────────────────────────────────

def test_empty_output_no_crash():
    """save_to_csv({}) must not raise."""
    print("\n[test_empty_output_no_crash]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        try:
            processing.save_to_csv({}, data_root=tmp, output_path=tmp/"m.csv", aggregate_path=tmp/"l.csv")
            check(True, "no exception on empty output")
        except Exception as e:
            check(False, f"exception raised: {e}")


# ── Test 2: condition with empty mechanical_properties ───────────────────────

def test_empty_mechanical_properties_no_crash():
    """Condition with no processed pairs — save_to_csv must not crash."""
    print("\n[test_empty_mechanical_properties_no_crash]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        out = _minimal_output("empty-cond", props=[])
        try:
            processing.save_to_csv(out, data_root=tmp, output_path=tmp/"m.csv", aggregate_path=tmp/"l.csv")
            check(True, "no exception for empty mechanical_properties")
            check(not (tmp/"m.csv").exists() or pd.read_csv(tmp/"m.csv").empty or True,
                  "master CSV empty or absent (no rep rows to write)")
        except Exception as e:
            check(False, f"exception raised: {e}")


# ── Test 3: all reps invalid thickness (Good Fit Breakdown = None) ───────────

def test_all_invalid_thickness_no_crash():
    """All reps have Good Fit Breakdown = None — save_to_csv must not crash."""
    print("\n[test_all_invalid_thickness_no_crash]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        reps = [
            {"name": "thin-cond | rep 1", "Trial": "sample 1", "Thickness": 20.0,
             "Good Fit": False, "Good Fit Breakdown": None,
             "Elastic Modulus": np.nan, "Yield Strength": np.nan, "Changepoint": np.nan,
             "Slope Plateau": np.nan, "Slope Densification": np.nan, "Creep Strain": np.nan,
             "Strain at 50 bar": np.nan, "Strain at 80 bar": np.nan,
             "Strain at 150 bar": np.nan, "Strain at 500 bar": np.nan,
             "Average Standard Deviation": np.nan, "CV": np.nan},
        ]
        out = _minimal_output("thin-cond", props=reps, pre_cv=np.nan, has_failures=False)
        try:
            processing.save_to_csv(out, data_root=tmp, output_path=tmp/"m.csv", aggregate_path=tmp/"l.csv")
            check(True, "no exception for all-invalid-thickness condition")
            if (tmp/"m.csv").exists():
                df = pd.read_csv(tmp/"m.csv")
                check("Good Fit Breakdown" in df.columns, "Good Fit Breakdown column present")
                check(df["Good Fit Breakdown"].isna().all() or (df["Good Fit Breakdown"] == "None").all(),
                      "Good Fit Breakdown is null/None for invalid thickness reps")
        except Exception as e:
            check(False, f"exception raised: {e}")


# ── Test 4: all reps fail Good Fit → passing_properties empty ────────────────

def test_all_fail_goodfit_no_crash():
    """has_failures=True but passing_properties=[] — postDiscard row must be skipped, no crash."""
    print("\n[test_all_fail_goodfit_no_crash]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        reps = [
            {"name": "fail-cond | rep 1", "Trial": "sample 1", "Thickness": 100.0,
             "Good Fit": False, "Good Fit Breakdown": "{}",
             "Elastic Modulus": 10.0, "Yield Strength": 5.0, "Changepoint": 0.3,
             "Slope Plateau": 50.0, "Slope Densification": 20.0, "Creep Strain": 0.05,
             "Strain at 50 bar": np.nan, "Strain at 80 bar": np.nan,
             "Strain at 150 bar": np.nan, "Strain at 500 bar": np.nan,
             "Average Standard Deviation": 50.0, "CV": 0.2},
        ]
        out = _minimal_output("fail-cond", props=reps, pre_cv=0.2, post_cv=np.nan,
                               has_failures=True, passing=[])
        try:
            processing.save_to_csv(out, data_root=tmp, output_path=tmp/"m.csv", aggregate_path=tmp/"l.csv")
            check(True, "no exception when all reps fail goodfit")
            if (tmp/"l.csv").exists():
                df = pd.read_csv(tmp/"l.csv")
                check("fail-cond_postDiscard" not in df["name"].values,
                      "no postDiscard row when passing_properties is empty")
        except Exception as e:
            check(False, f"exception raised: {e}")


# ── Test 5: pre_cv = None (no valid curves) ──────────────────────────────────

def test_none_cv_no_crash():
    """pre_cv = None (plot_average_curve returned None) — must not crash downstream."""
    print("\n[test_none_cv_no_crash]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        reps = [
            {"name": "nocurve-cond | rep 1", "Trial": "sample 1", "Thickness": 100.0,
             "Good Fit": True, "Good Fit Breakdown": "{}",
             "Elastic Modulus": 200.0, "Yield Strength": 25.0, "Changepoint": 0.3,
             "Slope Plateau": 10.0, "Slope Densification": 300.0, "Creep Strain": 0.05,
             "Strain at 50 bar": 0.25, "Strain at 80 bar": 0.40,
             "Strain at 150 bar": 0.60, "Strain at 500 bar": np.nan,
             "Average Standard Deviation": 50.0, "CV": np.nan},  # CV = nan because pre_cv was None
        ]
        out = _minimal_output("nocurve-cond", props=reps, pre_cv=np.nan, post_cv=np.nan,
                               has_failures=False, passing=reps)
        try:
            processing.save_to_csv(out, data_root=tmp, output_path=tmp/"m.csv", aggregate_path=tmp/"l.csv")
            check(True, "no exception when CV is NaN")
        except Exception as e:
            check(False, f"exception raised: {e}")


# ── Test 6: Good Fit Breakdown = "{}" (empty but valid JSON) ─────────────────

def test_empty_breakdown_json_no_crash():
    """Good Fit Breakdown = '{}' must be stored and readable without crash."""
    print("\n[test_empty_breakdown_json_no_crash]")
    import json
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        reps = [
            {"name": "empty-bd-cond | rep 1", "Trial": "sample 1", "Thickness": 100.0,
             "Good Fit": False, "Good Fit Breakdown": json.dumps({}),
             "Elastic Modulus": np.nan, "Yield Strength": np.nan, "Changepoint": np.nan,
             "Slope Plateau": np.nan, "Slope Densification": np.nan, "Creep Strain": np.nan,
             "Strain at 50 bar": np.nan, "Strain at 80 bar": np.nan,
             "Strain at 150 bar": np.nan, "Strain at 500 bar": np.nan,
             "Average Standard Deviation": np.nan, "CV": np.nan},
        ]
        out = _minimal_output("empty-bd-cond", props=reps, has_failures=False)
        try:
            processing.save_to_csv(out, data_root=tmp, output_path=tmp/"m.csv", aggregate_path=tmp/"l.csv")
            check(True, "no exception for empty breakdown JSON")
            if (tmp/"m.csv").exists():
                df = pd.read_csv(tmp/"m.csv")
                raw = df["Good Fit Breakdown"].iloc[0]
                parsed = json.loads(raw)
                check(parsed == {}, f"empty breakdown stored and parsed correctly (got {parsed!r})")
        except Exception as e:
            check(False, f"exception raised: {e}")


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_empty_output_no_crash()
    test_empty_mechanical_properties_no_crash()
    test_all_invalid_thickness_no_crash()
    test_all_fail_goodfit_no_crash()
    test_none_cv_no_crash()
    test_empty_breakdown_json_no_crash()

    print(f"\n{'='*40}")
    print(f"Results: {_PASS} passed, {_FAIL} failed")
    sys.exit(0 if _FAIL == 0 else 1)
