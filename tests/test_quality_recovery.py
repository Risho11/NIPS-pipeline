"""
test_quality_recovery.py — one-off recovery run for the stranded-images bug.

take_snapshot() was writing photos to the wrong folder for a while (fixed in run_loop.py), so
every condition in data/raw/ from 2026-08-10 11:33 through 2026-08-11 09:21 ended up with the
same stale 2026-08-09 photo pair instead of its own. The real photos were sitting unused in
src/pipeline/images/ the whole time -- this script maps each of those 20 photos back to the
condition it actually belongs to (by timestamp: each pair falls cleanly between its condition's
start and the next condition's start, verified by hand before writing this) and runs the real
image_processing + quality-check flow on them.

Deliberately entirely test-isolated: does NOT touch data/raw/ or data/results/ -- copies (not
moves) the real params.json + correct photos into tests/quality_test/raw/<condition>/, and
writes the quality CSV rows to tests/quality_test/ too. Reuses the actual production functions
(membrane_imaging.run, llm_context.generate_quality_report_text/ensure_condition_row/
attach_branch_result_to_csv, EVALUATE.generate_quality_log.generate) so this exercises the same
code path a live campaign would, just pointed at an isolated copy.

Makes 10 real, paid vision-LLM calls (OPENROUTER_API_KEY required). Run once:
    python test_quality_recovery.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pipeline"))
sys.path.insert(0, str(Path(__file__).parent.parent))

import membrane_imaging
import llm_context
import EVALUATE.generate_quality_log as generate_quality_log

REPO_ROOT = Path(__file__).parent.parent
REAL_RAW = REPO_ROOT / "data" / "raw"
STRANDED_IMAGES = REPO_ROOT / "src" / "pipeline" / "images"

TEST_ROOT = Path(__file__).parent / "quality_test"
TEST_RAW = TEST_ROOT / "raw"
TEST_AGG = TEST_ROOT / "test_agg.csv"
TEST_AGG_LLM = TEST_ROOT / "test_agg_llm.csv"

# condition -> (pretest photo, posttest photo), hand-verified against each condition's earliest
# specimen timestamp and the next condition's start time -- every pair falls cleanly inside its
# own condition's window, no ambiguity.
CONDITION_PHOTOS = {
    "21-0add-5deg-300s-N2-1800s":              ("1786380082.4520621.jpg", "1786381287.166668.jpg"),
    "21-0add-5deg-300s-N2-1800s_run2":         ("1786390577.7242935.jpg", "1786391965.8173444.jpg"),
    "21-2add-60degMix-15deg-30s-NoN2-1800s":   ("1786399033.817619.jpg", "1786400314.2204707.jpg"),
    "21-2add-50degMix-15deg-60s-NoN2-1800s":   ("1786407166.2914371.jpg", "1786408026.707509.jpg"),
    "21-2add-70degMix-5deg-30s-NoN2-1800s":    ("1786415070.3832018.jpg", "1786415899.4205704.jpg"),
    "21-4add-75degMix-5deg-120s-N2-1800s":     ("1786419656.1187181.jpg", "1786420635.2068229.jpg"),
    "21-2add-60degMix-5deg-120s-N2-1800s":     ("1786427934.5364385.jpg", "1786428766.3924854.jpg"),
    "21-2add-60degMix-15deg-60s-N2-1800s":     ("1786435827.2820103.jpg", "1786436621.076103.jpg"),
    "21-2add-80degMix-5deg-60s-N2-1800s":      ("1786443844.0582082.jpg", "1786444787.1152604.jpg"),
    "21-2add-70degMix-25deg-60s-N2-1800s":     ("1786453579.2646108.jpg", "1786454481.7354987.jpg"),
}

TEST_RAW.mkdir(parents=True, exist_ok=True)

for condition, (pretest_name, posttest_name) in CONDITION_PHOTOS.items():
    real_cond_dir = REAL_RAW / condition
    test_cond_dir = TEST_RAW / condition
    test_cond_dir.mkdir(exist_ok=True)

    # copy (not move) params.json -- read-only against the real folder
    shutil.copy(real_cond_dir / "params.json", test_cond_dir / "params.json")

    # copy the correct photos in, replacing whatever stale pair might already be in the test dir
    for jpg in test_cond_dir.glob("*.jpg"):
        jpg.unlink()
    shutil.copy(STRANDED_IMAGES / pretest_name, test_cond_dir / pretest_name)
    shutil.copy(STRANDED_IMAGES / posttest_name, test_cond_dir / posttest_name)

    print(f"\n=== {condition} ===")
    result = membrane_imaging.run(test_cond_dir)
    print(f"  pretest image: {result['image_path']}")

    report_text = llm_context.generate_quality_report_text(result)
    print(f"  quality_report: {report_text[:120]}...")

    llm_context.ensure_condition_row(condition, test_cond_dir, TEST_AGG_LLM)
    llm_context.attach_branch_result_to_csv(
        condition, "quality", result, TEST_AGG, TEST_AGG_LLM, report_text=report_text
    )

print(f"\nTest CSV: {TEST_AGG_LLM}")

# Write to the REAL quality_evaluation_log.html (that's what actually gets opened/checked) --
# merges the real current-campaign CSV (via generate_quality_log's own AGG_LLM auto-discovery)
# with this isolated test CSV, and checks TEST_RAW for these 10 conditions' corrected photos
# before falling back to the real data/raw/ (which still has the stale duplicate photos for
# them -- data/raw/ itself is never written to by this script).
generate_quality_log.EXTRA_RAW_DIRS = [TEST_RAW]
generate_quality_log.generate(extra_csv_paths=[TEST_AGG_LLM])
print(f"Quality log: {generate_quality_log.OUTPUT}")
