"""
test_csv.py — unit tests for save_to_csv edge cases.

Tests call save_to_csv directly with mock output dicts (no pipeline, no real CSV files).
Changing processing_29.py internals (curve fitting, goodFit_eval logic) does NOT
break these tests — only changes to the save_to_csv input/output contract would.

Run:
    python TESTS/test_csv.py
"""
import sys
import json
import tempfile
import numpy as np
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import processing_29 as processing

# ── Helpers ─────────────────────────────────────────────────────────────────

_PASS, _FAIL = 0, 0

def check(condition, label):
    global _PASS, _FAIL
    if condition:
        print(f"  PASS  {label}")
        _PASS += 1
    else:
        print(f"  FAIL  {label}")
        _FAIL += 1

def _rep(name, trial, good, breakdown=None):
    """Build a minimal mechanicalProperties dict for one rep."""
    return {
        "name": name,
        "Trial": trial,
        "Thickness": 100.0,
        "Elastic Modulus": 250.0,
        "Yield Strength": 30.0,
        "Changepoint": 0.35,
        "Slope Plateau": 15.0,
        "Slope Densification": 400.0,
        "Creep Strain": 0.05,
        "Strain at 50 bar": 0.28,
        "Strain at 80 bar": 0.44,
        "Strain at 150 bar": 0.62,
        "Strain at 500 bar": np.nan,
        "Good Fit": good,
        "Good Fit Breakdown": json.dumps(breakdown or {"elastic_r2": {"pts": 28, "max": 30, "note": "R²=0.94"}}),
        "Average Standard Deviation": 51.0,
        "CV": 0.12,
    }

def _avg(name):
    """Build a minimal average row."""
    r = _rep(name, "average", True)
    r["Trial"] = "average"
    return r

def _output(condition, reps, passing_props=None, has_failures=False, pre_cv=0.12, post_cv=0.10):
    """Build a minimal output dict for save_to_csv."""
    props = reps + [_avg(condition)]
    return {
        condition: {
            "condition": condition,
            "processed_curves": [],
            "mechanical_properties": props,
            "pre_cv": pre_cv,
            "post_cv": post_cv,
            "has_failures": has_failures,
            "passing_properties": passing_props if passing_props is not None else reps,
        }
    }

def _run(output_dict, tmp_dir):
    master = tmp_dir / "master.csv"
    llm = tmp_dir / "llm.csv"
    processing.save_to_csv(output_dict, data_root=tmp_dir, output_path=master, aggregate_path=llm)
    return master, llm

# ── Tests ────────────────────────────────────────────────────────────────────

def test_all_pass():
    """All reps pass → one LLM CSV row, no _preDiscard/_postDiscard suffix."""
    print("\n[test_all_pass]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        reps = [_rep("cond-A | rep 1", "sample 1", True), _rep("cond-A | rep 2", "sample 2", True)]
        out = _output("cond-A", reps, has_failures=False, pre_cv=0.11, post_cv=0.11)
        master, llm = _run(out, tmp)

        check(master.exists(), "master CSV written")
        check(llm.exists(), "LLM CSV written")

        llm_df = pd.read_csv(llm)
        check(len(llm_df) == 1, f"LLM CSV has exactly 1 row (got {len(llm_df)})")
        check("cond-A" in llm_df["name"].values, "LLM row name is plain condition (no suffix)")
        check("cond-A_preDiscard" not in llm_df["name"].values, "no _preDiscard suffix")
        check("cond-A_postDiscard" not in llm_df["name"].values, "no _postDiscard suffix")

        master_df = pd.read_csv(master)
        check("Good Fit Breakdown" in master_df.columns, "master CSV has Good Fit Breakdown column")
        check(master_df["Good Fit Breakdown"].notna().all(), "Good Fit Breakdown is non-null for passing reps")


def test_some_fail():
    """Some reps fail → two LLM CSV rows (_preDiscard and _postDiscard)."""
    print("\n[test_some_fail]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r1 = _rep("cond-B | rep 1", "sample 1", True)
        r2 = _rep("cond-B | rep 2", "sample 2", False)  # FAIL
        r3 = _rep("cond-B | rep 3", "sample 3", True)
        passing = [r1, r3]
        out = _output("cond-B", [r1, r2, r3], passing_props=passing, has_failures=True, pre_cv=0.15, post_cv=0.10)
        master, llm = _run(out, tmp)

        check(llm.exists(), "LLM CSV written")
        llm_df = pd.read_csv(llm)
        check(len(llm_df) == 2, f"LLM CSV has exactly 2 rows (got {len(llm_df)})")
        names = set(llm_df["name"].values)
        check("cond-B_preDiscard" in names, "preDiscard row present")
        check("cond-B_postDiscard" in names, "postDiscard row present")

        # postDiscard CV should differ from preDiscard CV
        pre_row = llm_df[llm_df["name"] == "cond-B_preDiscard"].iloc[0]
        post_row = llm_df[llm_df["name"] == "cond-B_postDiscard"].iloc[0]
        check(abs(pre_row["CV Mean"] - 0.15) < 0.001, f"preDiscard CV Mean = pre_cv (got {pre_row['CV Mean']})")
        check(abs(post_row["CV Mean"] - 0.10) < 0.001, f"postDiscard CV Mean = post_cv (got {post_row['CV Mean']})")

        master_df = pd.read_csv(master)
        check(len(master_df) == 3, f"master CSV has 3 rep rows (got {len(master_df)})")


def test_all_fail():
    """All reps fail → preDiscard row only (postDiscard skipped, no passing_properties)."""
    print("\n[test_all_fail]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r1 = _rep("cond-C | rep 1", "sample 1", False)
        r2 = _rep("cond-C | rep 2", "sample 2", False)
        out = _output("cond-C", [r1, r2], passing_props=[], has_failures=True, pre_cv=0.20, post_cv=np.nan)
        master, llm = _run(out, tmp)

        check(llm.exists(), "LLM CSV written")
        llm_df = pd.read_csv(llm)
        check(len(llm_df) == 2, f"LLM CSV has 2 rows (preDiscard + postDiscard NaN) (got {len(llm_df)})")
        check("cond-C_preDiscard" in llm_df["name"].values, "preDiscard row present")
        check("cond-C_postDiscard" in llm_df["name"].values, "postDiscard NaN row present")


def test_single_rep():
    """Single rep condition — no crash."""
    print("\n[test_single_rep]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r1 = _rep("cond-D | rep 1", "sample 1", True)
        out = _output("cond-D", [r1], has_failures=False, pre_cv=0.05)
        master, llm = _run(out, tmp)

        check(master.exists() and llm.exists(), "CSVs written for single-rep condition")
        llm_df = pd.read_csv(llm)
        check(len(llm_df) == 1, "LLM CSV has 1 row")


def test_good_fit_breakdown_json():
    """Good Fit Breakdown is valid JSON in master CSV."""
    print("\n[test_good_fit_breakdown_json]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bd = {"elastic_r2": {"pts": 28, "max": 30, "note": "R²=0.94"}, "yield_accuracy": {"pts": 20, "max": 25, "note": "err=5%"}}
        r1 = _rep("cond-E | rep 1", "sample 1", True, breakdown=bd)
        out = _output("cond-E", [r1], has_failures=False)
        master, _ = _run(out, tmp)

        master_df = pd.read_csv(master)
        check("Good Fit Breakdown" in master_df.columns, "column exists")
        raw = master_df["Good Fit Breakdown"].iloc[0]
        try:
            parsed = json.loads(raw)
            check(isinstance(parsed, dict), "Good Fit Breakdown is valid JSON dict")
            check("elastic_r2" in parsed, "breakdown contains elastic_r2 key")
        except (json.JSONDecodeError, TypeError) as e:
            check(False, f"JSON parse failed: {e}")


def test_good_fit_breakdown_invalid_thickness():
    """Good Fit Breakdown is null for invalid-thickness reps."""
    print("\n[test_good_fit_breakdown_invalid_thickness]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        r = _rep("cond-F | rep 1", "sample 1", False)
        r["Good Fit Breakdown"] = None  # invalid thickness path sets None
        out = _output("cond-F", [r], has_failures=True, passing_props=[])
        master, _ = _run(out, tmp)

        master_df = pd.read_csv(master)
        check("Good Fit Breakdown" in master_df.columns, "column exists")
        val = master_df["Good Fit Breakdown"].iloc[0]
        check(pd.isna(val), f"Good Fit Breakdown is null for invalid-thickness rep (got {val!r})")


def test_empty_output():
    """save_to_csv with empty output dict — no crash, no files written."""
    print("\n[test_empty_output]")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        master = tmp / "master.csv"
        llm = tmp / "llm.csv"
        processing.save_to_csv({}, data_root=tmp, output_path=master, aggregate_path=llm)
        check(not master.exists(), "master CSV not created for empty output")
        check(not llm.exists(), "LLM CSV not created for empty output")


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_all_pass()
    test_some_fail()
    test_all_fail()
    test_single_rep()
    test_good_fit_breakdown_json()
    test_good_fit_breakdown_invalid_thickness()
    test_empty_output()

    print(f"\n{'='*40}")
    print(f"Results: {_PASS} passed, {_FAIL} failed")
    sys.exit(0 if _FAIL == 0 else 1)
