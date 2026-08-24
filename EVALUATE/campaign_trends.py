"""Manual campaign-wide property trend plotting.

This module is deliberately independent of the processing pipeline.  It reads the
existing ``data/results/begins_*/agg.csv`` files and never modifies source data.

Run from the repository root, for example::

    python EVALUATE/campaign_trends.py
    python EVALUATE/campaign_trends.py --properties "Elastic Modulus" "Yield Strength"

The companion ``campaign_trends.ipynb`` is the more convenient interactive entry
point.  Functions here are kept importable so plotting and data-loading logic can be
reused without copying notebook cells.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_ROOT = REPO_ROOT / "data" / "results"
DEFAULT_RAW_ROOT = REPO_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "EVALUATE" / "campaign_trends_output"

DEFAULT_PROPERTIES = (
    "Thickness",
    "Elastic Modulus",
    "Yield Strength",
    "Pore Fraction",
    "Creep Strain",
    "Strain at 50 bar",
)

_SPECIMEN_TIMESTAMP = re.compile(r"(\d{8})_(\d{6})")


def base_condition(name: object) -> str:
    """Remove only the aggregation suffix; repeated ``_runN`` samples stay distinct."""
    value = str(name).strip()
    return re.sub(r"_(?:pre|post)Discard$", "", value, flags=re.IGNORECASE)


def _raw_condition_candidates(raw_root: Path, condition: str) -> list[Path]:
    """Return the exact raw directory for an aggregate condition."""
    if not raw_root.is_dir():
        return []
    exact = raw_root / condition
    return [exact] if exact.is_dir() else []


def specimen_time(raw_root: Path, condition: str) -> pd.Timestamp:
    """Earliest real specimen timestamp for a condition, or ``NaT`` if unavailable."""
    timestamps: list[pd.Timestamp] = []
    for folder in _raw_condition_candidates(raw_root, condition):
        for path in folder.glob("Specimen_*.csv"):
            match = _SPECIMEN_TIMESTAMP.search(path.name)
            if match:
                value = pd.to_datetime(
                    match.group(1) + match.group(2), format="%m%d%Y%H%M%S", errors="coerce"
                )
                if pd.notna(value):
                    timestamps.append(value)
    return min(timestamps) if timestamps else pd.NaT


def available_properties(frame: pd.DataFrame) -> list[str]:
    """Properties having both a mean and intra-sample SD column."""
    columns = set(frame.columns)
    return sorted(
        column[: -len(" Mean")]
        for column in columns
        if column.endswith(" Mean") and f"{column[: -len(' Mean')]} SD" in columns
    )


def load_campaign_data(
    results_root: Path | str = DEFAULT_RESULTS_ROOT,
    raw_root: Path | str = DEFAULT_RAW_ROOT,
    *,
    prefer: str = "postDiscard",
) -> pd.DataFrame:
    """Load and de-duplicate all campaign aggregate CSVs.

    One row is retained per condition.  ``postDiscard`` is preferred when it exists;
    otherwise the pre-discard/plain aggregate is retained.  Among repeated processing
    records, the newest CSV timestamp wins. ``sample_time`` comes from the raw specimen
    filename when available and falls back to the aggregate row's timestamp.
    """
    results_root, raw_root = Path(results_root), Path(raw_root)
    frames: list[pd.DataFrame] = []
    for path in sorted(results_root.glob("begins_*/agg.csv")):
        try:
            frame = pd.read_csv(path)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
            continue
        if frame.empty or "name" not in frame:
            continue
        frame["source_csv"] = str(path)
        campaign_folder = path.parent.name
        frame["campaign"] = campaign_folder[len("begins_"):] if campaign_folder.startswith("begins_") else campaign_folder
        frames.append(frame)
    if not frames:
        return pd.DataFrame()

    data = pd.concat(frames, ignore_index=True, sort=False)
    data["processed_time"] = pd.to_datetime(
        data.get("date", pd.Series(index=data.index, dtype="object"))
        .astype(str)
        .str.replace("\n", " ", regex=False),
        errors="coerce",
    )
    data["condition"] = data["name"].map(base_condition)
    name_lower = data["name"].astype(str).str.lower()
    preferred_suffix = prefer.lower()
    data["_preference"] = name_lower.str.endswith("_" + preferred_suffix).astype(int)
    data = data.sort_values(["condition", "_preference", "processed_time"])
    data = data.drop_duplicates("condition", keep="last").drop(columns="_preference")

    raw_times = {condition: specimen_time(raw_root, condition) for condition in data["condition"]}
    data["specimen_time"] = data["condition"].map(raw_times)
    data["sample_time"] = data["specimen_time"].fillna(data["processed_time"])
    data["time_source"] = data["specimen_time"].notna().map(
        {True: "raw specimen filename", False: "aggregate processed time"}
    )
    return data.sort_values("sample_time").reset_index(drop=True)


def select_campaign(
    data: pd.DataFrame,
    *,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    campaigns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filter loaded data without mutating it."""
    selected = data.copy()
    if start is not None:
        selected = selected[selected["sample_time"] >= pd.Timestamp(start)]
    if end is not None:
        end_time = pd.Timestamp(end)
        if isinstance(end, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
            end_time += pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        selected = selected[selected["sample_time"] <= end_time]
    if campaigns is not None:
        selected = selected[selected["campaign"].isin(campaigns)]
    return selected.reset_index(drop=True)


def plot_property(
    data: pd.DataFrame,
    property_name: str,
    *,
    ax: plt.Axes | None = None,
    connect_points: bool = True,
) -> plt.Axes:
    """Plot a property mean through time with ±1 intra-sample SD error bars."""
    mean_column, sd_column = f"{property_name} Mean", f"{property_name} SD"
    missing = [column for column in (mean_column, sd_column) if column not in data]
    if missing:
        raise KeyError(f"Missing columns for {property_name!r}: {', '.join(missing)}")
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 5))
    points = data.dropna(subset=["sample_time", mean_column]).sort_values("sample_time")
    error = pd.to_numeric(points[sd_column], errors="coerce").fillna(0)
    ax.errorbar(
        points["sample_time"], pd.to_numeric(points[mean_column], errors="coerce"),
        yerr=error, fmt="o-" if connect_points else "o", markersize=4, linewidth=1.2,
        capsize=3, elinewidth=1, alpha=0.9,
    )
    ax.set(title=property_name, xlabel="Sample date and time", ylabel=f"{property_name} (mean ± SD)")
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    return ax


def plot_properties(
    data: pd.DataFrame,
    properties: Sequence[str],
    *,
    columns: int = 2,
    connect_points: bool = True,
) -> tuple[plt.Figure, list[plt.Axes]]:
    """Create a clean grid containing one time plot per requested property."""
    properties = list(properties)
    if not properties:
        raise ValueError("Choose at least one property")
    columns = max(1, min(columns, len(properties)))
    rows = math.ceil(len(properties) / columns)
    figure, axes_array = plt.subplots(rows, columns, figsize=(7 * columns, 4 * rows), squeeze=False)
    axes = list(axes_array.flat)
    for axis, property_name in zip(axes, properties):
        plot_property(data, property_name, ax=axis, connect_points=connect_points)
    for axis in axes[len(properties):]:
        axis.remove()
    figure.suptitle("Campaign property trends (error bars = ±1 intra-sample SD)", fontsize=15)
    figure.tight_layout()
    return figure, axes[: len(properties)]


def export_campaign(
    data: pd.DataFrame,
    properties: Sequence[str],
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Save the selected data and plot; return ``(csv_path, png_path)``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path, png_path = output_dir / "campaign_data.csv", output_dir / "campaign_properties.png"
    data.to_csv(csv_path, index=False)
    figure, _ = plot_properties(data, properties)
    figure.savefig(png_path, dpi=180, bbox_inches="tight")
    return csv_path, png_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--properties", nargs="+", default=list(DEFAULT_PROPERTIES))
    parser.add_argument("--start", help="Inclusive date/time, e.g. 2026-08-10")
    parser.add_argument("--end", help="Inclusive date/time, e.g. 2026-08-22")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-show", action="store_true", help="Save outputs without opening a plot window")
    args = parser.parse_args(argv)

    data = select_campaign(load_campaign_data(), start=args.start, end=args.end)
    if data.empty:
        parser.error("No aggregate campaign records matched the selection")
    invalid = sorted(set(args.properties) - set(available_properties(data)))
    if invalid:
        parser.error(f"Unavailable properties: {', '.join(invalid)}")
    csv_path, png_path = export_campaign(data, args.properties, args.output_dir)
    print(f"Loaded {len(data)} samples; wrote {csv_path} and {png_path}")
    if not args.no_show:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
