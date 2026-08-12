"""llm_context.py — single place that decides what data reaches the LLM and how it's labeled.

Two report channels feed activeLearning_29.py's LLM_AL: "performance" (curve_segmentation's own
mechanical-property data — built natively in curve_segmentation.py's own save_to_csv/
formatted_parameters_withProp, not touched here) and "quality" (image_processing and any future
quality-type branches — handled generically here). Grouping is by branch TYPE
(master_processing.BRANCH_CONFIG[name]["type"]), not by individual branch name, so a new branch
of an existing type needs no new plumbing — just add it to BRANCH_CONFIG.

This is also where the fixed/contextual "formatted_parameters" key list lives (extending
curve_segmentation.FORMATTED_PARAMS_KEYS) — add or remove keys here, in one place, before any
processing starts, rather than hunting through curve_segmentation.py/master_processing.py/
run_loop.py.
"""
import datetime
import json
from pathlib import Path

import pandas as pd

import curve_segmentation
import membrane_quality_llm

# Extends curve_segmentation's fixed-params list. These are context for the initial report
# (Generate_report), never something the LLM chooses (see run_loop.py's separate PARAMS_SCHEMA).
# Add/remove keys here freely -- e.g. if a campaign never wires up the humidity sensor, remove
# "Humidity Mean" and it stops showing up in formatted_parameters.
curve_segmentation.FORMATTED_PARAMS_KEYS = curve_segmentation.FORMATTED_PARAMS_KEYS + [
    "Air Temp Mean", "Humidity Mean",
]

# Which fields from a branch's result get summarized into its {type}_report text. Only
# non-"performance" types need an entry here -- curve_segmentation already builds its own report
# text natively. Missing type -> falls back to including every JSON-safe field (see
# attach_branch_result_to_csv).
REPORT_KEYS_BY_TYPE = {
    "quality": ["test_point", "safe_radius"],
}


def _json_safe_subset(result: dict) -> dict:
    """Keep only keys whose value actually JSON-serializes. No hardcoded field names, so this
    doesn't need touching when a branch's return shape changes."""
    safe = {}
    for k, v in result.items():
        try:
            json.dumps(v)
            safe[k] = v
        except TypeError:
            continue
    return safe


def scrub_raw_result_columns(agg_llm_path):
    """Drop any "{type}_result" column from the LLM-facing CSV. curve_segmentation's
    promote_condition/promote_to_main copies a matched row VERBATIM (every column) from
    results_agg.csv into results_agg_llm.csv -- including any raw "{type}_result" column a
    previous round's attach_branch_result_to_csv already wrote into results_agg.csv. Those raw
    columns must never live in the LLM-facing CSV, so this is called every round (right after
    run_branches(), before anything else touches agg_llm_path) to enforce that regardless of
    how a stray column got copied in."""
    agg_llm_path = Path(agg_llm_path)
    if not agg_llm_path.exists() or agg_llm_path.stat().st_size == 0:
        return
    df = pd.read_csv(agg_llm_path)
    result_cols = [c for c in df.columns if c.endswith("_result")]
    if result_cols:
        df = df.drop(columns=result_cols)
        df.to_csv(agg_llm_path, index=False)


def ensure_condition_row(condition_name, condition_dir, agg_llm_path):
    """Create a minimal row for this condition in results_agg_llm.csv if one doesn't already
    exist. Needed because curve_segmentation (the "performance" branch) is the only thing that
    otherwise creates rows -- without this, a quality-only (or any non-performance) campaign
    would have no row to attach results to or build a report from. No-ops if a row already
    exists (curve_segmentation ran and its row is more complete) or params.json is missing."""
    agg_llm_path = Path(agg_llm_path)
    if agg_llm_path.exists() and agg_llm_path.stat().st_size > 0:
        existing_df = pd.read_csv(agg_llm_path)
        if (existing_df["name"] == condition_name).any():
            return

    params_path = Path(condition_dir) / "params.json"
    if not params_path.exists():
        return
    with open(params_path, encoding="utf-8") as f:
        params = json.load(f)

    row = {"name": condition_name, "date": datetime.datetime.now().strftime("%Y-%m-%d\n%H:%M:%S")}
    row.update({k: v for k, v in params.items() if k not in ("air_data", "stock_metadata")})
    air = params.get("air_data") or {}
    row["Air Temp Mean"] = air.get("temperature")
    row["Humidity Mean"] = air.get("humidity")
    row["formatted_parameters"] = curve_segmentation.formatted_parameters(row)
    row["formatted_parameters_withProp"] = row["formatted_parameters"]
    row["initial_report"] = ""
    row["final_report"] = ""

    new_df = pd.DataFrame([row])
    if agg_llm_path.exists() and agg_llm_path.stat().st_size > 0:
        existing = pd.read_csv(agg_llm_path)
        new_df = pd.concat([existing, new_df], ignore_index=True)
    agg_llm_path.parent.mkdir(parents=True, exist_ok=True)
    new_df.to_csv(agg_llm_path, index=False)


def attach_branch_result_to_csv(condition_name, branch_type, branch_result, agg_path, agg_llm_path,
                                 report_text=None):
    """Generic per-TYPE merge, split across the two CSVs curve_segmentation already writes:
      - results_agg.csv (agg_path): full raw result, JSON-encoded, in a "{type}_result" column
        -- the historical/full record. Attached to every row belonging to this condition (plain
        name, or _preDiscard/_postDiscard variants).
      - results_agg_llm.csv (agg_llm_path): NOT the raw column -- only report_text (see below)
        in a "{type}_report" text column, since that's what actually reaches the LLM (see
        build_observations). Never touches formatted_parameters_withProp -- that stays
        curve_segmentation's own "performance" channel, kept separate on purpose.
    report_text: pass a pre-built string (e.g. from a dedicated LLM call, see
      generate_quality_report_text) to use as-is. If None, falls back to filtering
      branch_result's JSON-safe fields through REPORT_KEYS_BY_TYPE -- kept as a pure/local
      merge with no network call buried inside it.
    Not used for the "performance" type. No-ops if there's no result or no CSV row yet.
    """
    if branch_result is None:
        return
    safe_result = _json_safe_subset(branch_result)
    blob = json.dumps(safe_result)
    if report_text is None:
        keys = REPORT_KEYS_BY_TYPE.get(branch_type, list(safe_result))
        report_subset = {k: safe_result[k] for k in keys if k in safe_result}
        report_text = f"{branch_type}: {report_subset}"

    result_col = f"{branch_type}_result"
    report_col = f"{branch_type}_report"

    agg_path = Path(agg_path)
    if agg_path.exists():
        df = pd.read_csv(agg_path)
        candidate_names = [condition_name, f"{condition_name}_preDiscard", f"{condition_name}_postDiscard"]
        mask = df["name"].isin(candidate_names)
        if mask.any():
            df.loc[mask, result_col] = blob
            df.loc[mask, report_col] = report_text
            df.to_csv(agg_path, index=False)

    agg_llm_path = Path(agg_llm_path)
    if agg_llm_path.exists():
        llm_df = pd.read_csv(agg_llm_path)
        llm_mask = llm_df["name"] == condition_name
        if llm_mask.any():
            idx = llm_df[llm_mask].index[-1]
            llm_df.loc[idx, report_col] = report_text
            llm_df.to_csv(agg_llm_path, index=False)


def _summarize_report_text(text, max_chars=240):
    """Cheap local lead-truncation for a historical {type}_report -- no LLM call (these reports
    are long free-text vision-LLM output, and build_observations joining the FULL text of every
    past round makes quality_observations grow unbounded over a campaign). Not a real summary,
    just the report's lead sentence(s), which is where these reports tend to state their verdict
    first. current_condition_name's row is exempted in build_observations and always gets the
    full text -- only history gets truncated."""
    text = str(text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def build_observations(agg_llm_path, branch_type, current_condition_name=None):
    """Join a "{type}_report" column across all rows -- mirrors how "performance" observations
    are already built by joining final_report across campaign history in run_loop.py. Every
    block is labeled with its condition name + formatted_parameters (performance_observations
    gets this for free via fmt_params_with_prop; quality_report is bare LLM text with nothing
    tying it to a specific condition otherwise, so it's prepended here) so the LLM can actually
    map each observation back to the run that produced it. Every row except
    current_condition_name's is truncated via _summarize_report_text so campaign history doesn't
    balloon the prompt; current_condition_name's row (this round's result) always gets the full
    report text. Empty string if the file/column doesn't exist yet (branch never ran, or
    disabled all along)."""
    agg_llm_path = Path(agg_llm_path)
    if not agg_llm_path.exists():
        return ""
    df = pd.read_csv(agg_llm_path)
    col = f"{branch_type}_report"
    if col not in df.columns:
        return ""
    texts = []
    for _, row in df.iterrows():
        val = row.get(col)
        if pd.isna(val):
            continue
        text = str(val)
        if current_condition_name is not None and row.get("name") == current_condition_name:
            body = text
        else:
            body = _summarize_report_text(text)
        name = row.get("name", "")
        params = row.get("formatted_parameters", "")
        texts.append(f"[{name}] ({params})\n{body}")
    return "\n\n---\n\n".join(texts)


def generate_quality_report_text(image_processing_result):
    """Calls the dedicated vision LLM (membrane_quality_llm.py) on the branch's photo. Kept as
    its own module-level function (not folded into attach_branch_result_to_csv) since it's a
    live network/API call, not a pure local merge -- and so it can be monkeypatched to a stub
    in tests instead of making a real paid vision-LLM call every run."""
    image_path = image_processing_result.get("image_path")
    if not image_path:
        return None
    return membrane_quality_llm.Generate_quality_report(image_path)


def _clear_stale_performance_outcome(condition_name, agg_llm_path):
    """formatted_parameters_withProp is only ever appended to by curve_segmentation's own row
    creation -- nothing else writes it, and ensure_condition_row no-ops on an existing row. So
    if this round has no performance branch result, any fit-outcome text already sitting in that
    column (from a previous round where curve_segmentation *was* on) is stale and must not keep
    feeding final_report/LLM_AL as if a fit check just happened. Reset it back to bare
    formatted_parameters (no-op if there was never any outcome text to begin with)."""
    agg_llm_path = Path(agg_llm_path)
    if not agg_llm_path.exists() or agg_llm_path.stat().st_size == 0:
        return
    df = pd.read_csv(agg_llm_path)
    mask = df["name"] == condition_name
    if mask.any() and "formatted_parameters" in df.columns:
        df.loc[mask, "formatted_parameters_withProp"] = df.loc[mask, "formatted_parameters"]
        df.to_csv(agg_llm_path, index=False)


def attach_all_branch_results(condition_name, branch_results, branch_config, agg_path, agg_llm_path):
    """Same per-branch attach strategy for both run_loop.py and tests/test_master.py: skip
    "performance" (curve_segmentation already wrote its own native columns), generate a real
    quality report via the dedicated vision LLM for "quality"-type branches, attach everything
    else generically. One implementation, so the two callers can't drift apart."""
    performance_ran = any(branch_config[name]["type"] == "performance" for name in branch_results)
    if not performance_ran:
        _clear_stale_performance_outcome(condition_name, agg_llm_path)
    for branch_name, result in branch_results.items():
        branch_type = branch_config[branch_name]["type"]
        if branch_type == "performance":
            continue
        report_text = generate_quality_report_text(result) if branch_type == "quality" else None
        attach_branch_result_to_csv(condition_name, branch_type, result, agg_path, agg_llm_path,
                                     report_text=report_text)


def generate_reports_and_suggestion(condition_name, agg_llm_path, activeLearning, locked_additive_wt=None):
    """Exact strategy run_loop.py uses to go from a CSV row to a next-params suggestion: build
    initial_report (performance, via activeLearning.Generate_report), fold the mech-property
    outcome text into final_report, join performance_observations across campaign history, pull
    quality_observations (already-built quality_report column), call activeLearning.LLM_AL with
    both. Returns the raw params_suggestion string. `activeLearning` is passed in (not imported
    here) so tests/test_master.py can monkeypatch activeLearning_29.Generate_report/LLM_AL to
    stubs before calling this, rather than reimplementing the flow.

    locked_additive_wt: pass run_loop.LOCK_ADDITIVE_WT_VALUE when that campaign-phase lock is
    active, so LLM_AL's system prompt says additive_wt is locked instead of quoting the full
    triangle -- otherwise the LLM keeps proposing nonzero additive_wt that gets silently
    overridden downstream, and never learns why (see activeLearning_29.current_ranges)."""
    agg_llm_path = Path(agg_llm_path)
    if not agg_llm_path.exists() or agg_llm_path.stat().st_size == 0:
        raise ValueError(f"LLM CSV doesn't exist or is empty: {agg_llm_path}")
    llm_df = pd.read_csv(agg_llm_path)
    if llm_df.empty:
        raise ValueError(f"LLM CSV has no data rows: {agg_llm_path}")
    for col in ["initial_report", "final_report", "LLM_suggestion"]:
        if col in llm_df.columns:
            llm_df[col] = llm_df[col].astype(object)
    mask = llm_df["name"] == condition_name
    idx = llm_df[mask].index[-1] if mask.any() else llm_df.index[-1]
    fmt_params = llm_df.at[idx, "formatted_parameters"]
    initial_report = activeLearning.Generate_report(fmt_params)

    _fp_withprop = str(llm_df.at[idx, "formatted_parameters_withProp"])
    fmt_params_with_prop = _fp_withprop[len(fmt_params):]  # result string = withProp minus the params prefix
    final_report = initial_report + "\n" + fmt_params_with_prop

    llm_df.at[idx, "initial_report"] = initial_report
    llm_df.at[idx, "formatted_parameters_withProp"] = fmt_params + fmt_params_with_prop  # idempotent
    llm_df.at[idx, "final_report"] = final_report
    llm_df.to_csv(agg_llm_path, index=False)

    performance_observations = "\n\n---\n\n".join(llm_df["final_report"].dropna().tolist())
    quality_observations = build_observations(agg_llm_path, "quality", current_condition_name=condition_name)
    # ranges omitted on purpose -- LLM_AL computes it fresh from polymer_additive_bounds.py on
    # every call now, not a value cached at activeLearning_29 import time (see LLM_AL/
    # current_ranges' docstrings for why that caching was actively harmful).
    params_suggestion = activeLearning.LLM_AL(
        performance_observations, quality_observations=quality_observations,
        locked_additive_wt=locked_additive_wt,
    )

    llm_df.at[idx, "LLM_suggestion"] = params_suggestion
    llm_df.to_csv(agg_llm_path, index=False)
    return llm_df["LLM_suggestion"].dropna().iloc[-1]
