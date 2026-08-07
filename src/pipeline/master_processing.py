"""master_processing.py — dispatches independent testing branches.

Each branch (curve_segmentation, image_processing, ...) can be switched off via BRANCH_CONFIG
without touching the others. Disabling a branch is the only thing that skips it — an *enabled*
branch that raises is a real failure and propagates up (see run_branches docstring). If every
branch is disabled, run_loop.py falls back to its own additive-sweep passthrough cycle
(ITERATE_ADDITIVES / _next_iteration_params) instead of calling anything here (see
confirm_settings/any_branch_enabled).

Each branch also has a "type" ("performance" or "quality") — see llm_context.py for how a
branch's result becomes CSV columns and reaches the LLM, grouped by type rather than by
individual branch name.
"""
from pathlib import Path

import curve_segmentation
import membrane_imaging

DATA_ROOT = Path(__file__).resolve().parent.parent.parent  # src/pipeline/master_processing.py -> repo root
SAMPLE_DATA_FOLDER = "data/raw"  # single source of truth for the folder convention

BRANCH_CONFIG = {
    "curve_segmentation": {"enabled": False, "type": "performance"},
    "image_processing": {"enabled": True, "type": "quality"},
}


def get_condition_dir(condition_name, data_root=DATA_ROOT) -> Path:
    return Path(data_root) / SAMPLE_DATA_FOLDER / condition_name


def any_branch_enabled() -> bool:
    return any(cfg["enabled"] for cfg in BRANCH_CONFIG.values())


def confirm_settings():
    """Validate/log BRANCH_CONFIG before anything (server, robot run) starts.
    Zero branches enabled is valid — logged, not raised — it means run_loop.py will
    fall back to its own additive-sweep cycle (no testing, no data collection)."""
    if any_branch_enabled():
        active = [name for name, cfg in BRANCH_CONFIG.items() if cfg["enabled"]]
        print(f"[master_processing] active branches: {active}")
    else:
        print("[master_processing] no branches enabled — robot will run with "
              "NO testing and NO data collection (additive-sweep passthrough)")


def _run_curve_segmentation(condition_name, data_root, csv_paths=None):
    reps_path, agg_path, agg_llm_path = csv_paths or (
        Path(data_root) / "data" / "results" / "results_reps.csv",
        Path(data_root) / "data" / "results" / "results_agg.csv",
        Path(data_root) / "data" / "results" / "results_agg_llm.csv",
    )
    output = curve_segmentation.process_zero_sample_pairs_pipeline(
        folder_name=SAMPLE_DATA_FOLDER,
        data_root=str(data_root),
        strict=False,
        load_cutoff=1.0,
        thickness_info=False,
        thickness_map=None,
        creep_info=True,
        cutoff_load_thickness=1,
        cutoff_load_displacement=2,
        condition_filter=condition_name,
    )
    curve_segmentation.save_to_csv(
        output, data_root=data_root, output_path=reps_path, aggregate_path=agg_path
    )
    curve_segmentation.promote_condition(condition_name, agg_path, agg_llm_path)
    return output


def _run_image_processing(condition_name, data_root, csv_paths=None):
    return membrane_imaging.run(get_condition_dir(condition_name, data_root))


_BRANCH_FNS = {
    "curve_segmentation": _run_curve_segmentation,
    "image_processing": _run_image_processing,
}


def run_branches(condition_name, data_root=DATA_ROOT, csv_paths=None) -> dict:
    """Run each enabled branch. Deliberately NOT wrapped in try/except: an enabled branch
    that throws is a real failure and should propagate/stop the loop, same as today.
    Disabling a branch (config) is the only thing that skips it; an exception never causes
    silent fallback to "the other branch still ran." Also doesn't inspect or assume anything
    about what a branch function returns beyond "it's some value" — a branch's internal
    inputs/outputs can change freely without touching this file.

    csv_paths overrides curve_segmentation's output CSVs (reps, agg, agg_llm) — used by
    tests/test_master.py to point at real data/raw/ for input while writing to
    an isolated test folder. Defaults to today's production paths under data_root.
    """
    results = {}
    for name, fn in _BRANCH_FNS.items():
        if not BRANCH_CONFIG[name]["enabled"]:
            continue
        results[name] = fn(condition_name, data_root, csv_paths)
    return results
