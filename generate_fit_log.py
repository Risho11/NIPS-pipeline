#!/usr/bin/env python3
"""
generate_fit_log.py — build fit_evaluation_log.html

Reads results_reps.csv (plus any extra CSVs passed in), finds the
corresponding segmentation plots, and writes a side-by-side HTML log:
  left  → score breakdown table for all reps of the condition
  right → segmentation plot images

Run standalone (uses results_reps.csv):
    python generate_fit_log.py

Or import and call from test_processing.py:
    import generate_fit_log
    generate_fit_log.generate(extra_csv_paths=[OUTPUT_CSV])

When the same condition appears in multiple CSVs, the most recently
dated entry wins — so re-running test_processing on a condition
automatically updates that condition's card.
"""

import base64
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
PLOTS_DIR = ROOT / "pipeline-plots"
MAIN_CSV  = ROOT / "results_reps.csv"
OUTPUT    = ROOT / "fit_evaluation_log.html"
PASS_THRESHOLD = 70

# Score components in display order
COMPONENTS = [
    ("elastic_r2",              30, "elastic R²"),
    ("plateau_r2_start",        15, "plateau R² (first 40%)"),
    ("densification_r2",        15, "densif R²"),
    ("yield_accuracy",          25, "yield accuracy"),
    ("junction_continuity",     15, "junction continuity"),
    ("plateau_r2_full_penalty",  0, "plateau full R² pen"),
    ("elastic_modulus_penalty",  0, "E-mod penalty"),
    ("bp1_accuracy_penalty",     0, "bp1 penalty"),
]


# ── helpers ──────────────────────────────────────────────────────────────────

def strip_rep(name: str) -> str:
    """'17-5deg-350s-N2-1800s | rep 1' → '17-5deg-350s-N2-1800s'"""
    return name.split(" | rep")[0].split(" | sample")[0].strip()


def load_csvs(extra_csv_paths=None):
    """
    Load results_reps.csv and any extra CSVs (e.g. from test runs).
    For duplicate condition+rep rows, the one with the most recent date wins.
    Returns a DataFrame with one row per replicate.
    """
    frames = []
    paths = [MAIN_CSV] + (list(extra_csv_paths) if extra_csv_paths else [])
    for p in paths:
        p = Path(p)
        if p.exists() and p.stat().st_size > 0:
            try:
                frames.append(pd.read_csv(p))
            except Exception:
                pass

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["condition"] = df["name"].apply(strip_rep)

    # Keep most recent entry per (condition, Trial) pair
    df["_date_sort"] = pd.to_datetime(df["date"].str.replace(r"\n", " ", regex=True), errors="coerce")
    df = df.sort_values("_date_sort", ascending=True)
    df = df.drop_duplicates(subset=["condition", "Trial"], keep="last")
    return df


def find_plots(condition_name: str):
    """
    Search pipeline-plots/ for the most recent run folder that contains
    this condition. Returns (seg_images, comparison_images, run_folder_name).

    Seg images are relative paths from ROOT; sorted by rep number.
    """
    if not PLOTS_DIR.exists():
        return [], [], None

    # Run folders sorted newest-first (names are date-stamped so lexsort works)
    run_dirs = sorted(PLOTS_DIR.glob("*/"), reverse=True)
    for run_dir in run_dirs:
        cond_dir = run_dir / condition_name
        if not cond_dir.is_dir():
            continue

        seg = []
        for rep_dir in sorted(cond_dir.glob("rep-*/")):
            hits = sorted(rep_dir.glob("Segmentation_rep-*.png"))
            if hits:
                seg.append(hits[0].relative_to(ROOT))

        comps = sorted(
            [p.relative_to(ROOT) for p in cond_dir.glob("Comparison_CV*.png")]
        )
        return seg, comps, run_dir.name

    return [], [], None


def parse_breakdown(json_str):
    """Parse the Good Fit Breakdown JSON string. Returns dict or {}."""
    if not json_str or pd.isna(json_str):
        return {}
    try:
        return json.loads(json_str)
    except Exception:
        return {}


def score_color(score):
    """Return a CSS colour string based on score."""
    if score is None or pd.isna(score):
        return "#aaa"         # gray — pre-processing failure
    if score >= PASS_THRESHOLD:
        return "#2e7d32"      # green
    if score >= 60:
        return "#e65100"      # orange — just below threshold
    return "#b71c1c"          # red


def pts_cell_style(key, pts):
    """CSS background for a breakdown row, by component + pts."""
    if pts is None or pd.isna(pts):
        return "background:#f5f5f5;"
    if isinstance(pts, (int, float)):
        if pts < 0:
            return "background:#ffebee; color:#b71c1c; font-weight:bold;"
        if key in ("plateau_r2_full_penalty", "elastic_modulus_penalty",
                   "bp1_accuracy_penalty") and pts == 0:
            return "background:#f1f8e9; color:#33691e;"   # light green — penalty didn't fire
    return ""


# ── HTML generation ───────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 13px;
       background: #f0f0f0; color: #222; }
h1  { font-size: 1.4rem; padding: 16px 24px; background: #263238; color: #fff; }
.meta { font-size: 0.75rem; color: #90a4ae; padding: 4px 24px 12px;
        background: #263238; }
.legend { display: flex; gap: 16px; flex-wrap: wrap;
          padding: 10px 24px; background: #37474f; font-size: 11px; }
.legend-item { display: flex; align-items: center; gap: 5px; color: #eceff1; }
.dot  { width: 10px; height: 10px; border-radius: 50%; }

.condition-card {
    margin: 16px 24px;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 2px 6px rgba(0,0,0,.15);
    background: #fff;
}
.cond-header {
    display: flex; align-items: baseline; gap: 12px;
    padding: 10px 16px;
    color: #fff;
    font-weight: 600;
    font-size: 1rem;
}
.cond-header .run-tag { font-size: 11px; opacity: .8; font-weight: normal; }
.cond-header .summary { font-size: 11px; opacity: .9; margin-left: auto; }

.cond-body {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0;
}
.breakdown-panel { padding: 12px 16px; border-right: 1px solid #e0e0e0; }
.breakdown-panel table { border-collapse: collapse; width: 100%; }
.breakdown-panel th {
    background: #eceff1; font-size: 11px; font-weight: 600;
    padding: 4px 8px; text-align: center; border: 1px solid #cfd8dc;
    white-space: nowrap;
}
.breakdown-panel td {
    padding: 3px 8px; border: 1px solid #eceff1; font-size: 12px;
    white-space: nowrap;
}
.breakdown-panel td.comp-name { color: #455a64; font-size: 11px; }
.breakdown-panel td.pts { text-align: center; font-weight: 500; }
.breakdown-panel td.note-cell { color: #607d8b; font-size: 10px; max-width: 200px;
    overflow: hidden; text-overflow: ellipsis; }
.score-row td { font-weight: bold; font-size: 13px; padding: 5px 8px; }
.preproc-note { font-size: 11px; color: #b71c1c; padding: 4px 0; font-style: italic; }
.flags { margin-top: 8px; font-size: 11px; color: #455a64; line-height: 1.5; }
.flags strong { color: #b71c1c; }

.images-panel {
    display: flex; flex-wrap: wrap; align-items: flex-start;
    gap: 8px; padding: 12px; background: #fafafa;
}
.img-group { display: flex; flex-direction: column; gap: 4px; align-items: center; }
.img-group img {
    max-width: 320px; max-height: 240px; object-fit: contain;
    border: 1px solid #ddd; border-radius: 3px; cursor: zoom-in;
    transition: transform .15s;
}
.img-group img:hover { transform: scale(1.03); }
.img-group .img-label { font-size: 10px; color: #78909c; }
.no-plots { font-size: 11px; color: #90a4ae; padding: 8px; font-style: italic; }

/* Expand image on click via <details> trick */
.img-full { display: none; }
"""

JS = """
document.querySelectorAll('.img-group img').forEach(img => {
  img.addEventListener('click', () => {
    const w = window.open('', '_blank');
    w.document.write('<img src="' + img.src + '" style="max-width:100%;height:auto;">');
  });
});
"""


def build_breakdown_table(reps_data):
    """
    reps_data: list of dicts, one per rep, each with keys:
      'score', 'pass', 'breakdown' (parsed dict), 'is_preproc_failure'
    Returns HTML string.
    """
    n = len(reps_data)
    rep_labels = [f"R{i+1}" for i in range(n)]

    rows = []

    # Header row
    header_cells = "".join(f"<th>{lbl}</th>" for lbl in rep_labels)
    rows.append(f"<tr><th>Component</th>{header_cells}<th style='min-width:130px'>Notes</th></tr>")

    # Component rows
    for key, max_pts, label in COMPONENTS:
        max_str = f" /{max_pts}" if max_pts > 0 else ""
        cells = []
        notes = []
        for r in reps_data:
            bd = r["breakdown"]
            if key in bd:
                entry = bd[key]
                pts = entry.get("pts")
                note = entry.get("note", "")
                style = pts_cell_style(key, pts)
                if pts is not None:
                    cells.append(f'<td class="pts" style="{style}">{pts}</td>')
                else:
                    cells.append(f'<td class="pts" style="color:#aaa">—</td>')
                notes.append(note)
            else:
                cells.append('<td class="pts" style="color:#aaa">—</td>')
                notes.append("")

        # Show the most informative note (first non-empty, or combine if different)
        unique_notes = list(dict.fromkeys(n for n in notes if n))
        note_text = notes[0] if unique_notes else ""  # show R1 note by default
        # If all same, show once; if different, show R1 note (user can hover for details)
        cells_html = "".join(cells)
        rows.append(
            f'<tr>'
            f'<td class="comp-name">{label}{max_str}</td>'
            f'{cells_html}'
            f'<td class="note-cell" title="{note_text}">{note_text}</td>'
            f'</tr>'
        )

    # Score row
    score_cells = []
    for r in reps_data:
        score = r["score"]
        passed = r["pass"]
        if r["is_preproc_failure"]:
            score_cells.append('<td class="pts" style="color:#aaa">—</td>')
        elif score is None or pd.isna(score):
            score_cells.append('<td class="pts" style="color:#aaa">—</td>')
        else:
            s = int(score)
            col = score_color(s)
            mark = "✓" if passed else "✗"
            score_cells.append(f'<td class="pts" style="color:{col}">{s} {mark}</td>')

    rows.append(
        f'<tr class="score-row">'
        f'<td class="comp-name">SCORE /100</td>'
        + "".join(score_cells) +
        f'<td></td></tr>'
    )

    return "<table>" + "".join(rows) + "</table>"


def condition_card(cond_name, group_df, seg_images, comp_images, run_folder):
    """Build the HTML card for one condition."""

    reps_data = []
    # Sort reps by trial label for consistent ordering
    group_df = group_df.sort_values("Trial")

    for _, row in group_df.iterrows():
        score = row.get("Good Fit Score")
        good  = row.get("Good Fit", False)
        bd    = parse_breakdown(row.get("Good Fit Breakdown"))
        is_preproc = (score is None or pd.isna(score))
        reps_data.append({
            "score": score,
            "pass": bool(good),
            "breakdown": bd,
            "is_preproc_failure": is_preproc,
        })

    # Header colour based on majority pass
    n_pass = sum(r["pass"] for r in reps_data)
    n_total = len(reps_data)
    if n_total == 0:
        header_color = "#607d8b"
    elif all(r["is_preproc_failure"] for r in reps_data):
        header_color = "#78909c"   # gray — all pre-processing failures
    elif n_pass == n_total:
        header_color = "#2e7d32"   # all pass
    elif n_pass == 0:
        header_color = "#b71c1c"   # all fail
    else:
        header_color = "#e65100"   # mixed

    # Score summary string  e.g. "70✓ 66✗ 90✓"
    score_bits = []
    for r in reps_data:
        if r["is_preproc_failure"]:
            score_bits.append("—")
        elif r["score"] is None or pd.isna(r["score"]):
            score_bits.append("—")
        else:
            mark = "✓" if r["pass"] else "✗"
            score_bits.append(f'{int(r["score"])}{mark}')
    summary_str = "  ".join(score_bits)

    run_tag = run_folder or "unknown run"

    # --- Breakdown panel ---
    table_html = build_breakdown_table(reps_data)

    # Flags: collect notable penalties / issues across reps
    flags = []
    for i, r in enumerate(reps_data):
        bd = r["breakdown"]
        if r["is_preproc_failure"]:
            flags.append(f"<strong>R{i+1}:</strong> pre-processing failure — no membrane detected (thickness invalid)")
            continue
        for key in ("bp1_accuracy_penalty", "plateau_r2_full_penalty"):
            if key in bd:
                pts = bd[key].get("pts", 0)
                if isinstance(pts, (int, float)) and pts < 0:
                    note = bd[key].get("note", "")
                    label = "bp1 penalty" if key == "bp1_accuracy_penalty" else "plateau R² penalty"
                    flags.append(f"<strong>R{i+1} {label} {pts}:</strong> {note}")
        # Catastrophic
        for cat_key in ("catastrophic_slope_vs_modulus", "catastrophic_slope_ordering"):
            if cat_key in bd:
                note = bd[cat_key].get("note", "")
                flags.append(f"<strong>R{i+1} CATASTROPHIC:</strong> {note}")
        # yield_accuracy low
        if "yield_accuracy" in bd:
            pts = bd["yield_accuracy"].get("pts", 25)
            if isinstance(pts, (int, float)) and pts < 10:
                note = bd["yield_accuracy"].get("note", "")
                flags.append(f"<strong>R{i+1} low yield accuracy {pts}/25:</strong> {note}")

    flags_html = ""
    if flags:
        items = "".join(f"<li>{f}</li>" for f in flags)
        flags_html = f'<div class="flags"><ul>{items}</ul></div>'

    breakdown_html = f"""
    <div class="breakdown-panel">
      {table_html}
      {flags_html}
    </div>"""

    # --- Images panel ---
    imgs_html = ""
    for img_path in seg_images:
        label = img_path.parent.name  # e.g. "rep-1"
        imgs_html += f"""
        <div class="img-group">
          <img src="{img_path}" alt="{label}" loading="lazy">
          <span class="img-label">{label}</span>
        </div>"""

    # Comparison CVs (if any)
    for img_path in comp_images:
        label = img_path.stem  # e.g. "Comparison_CV_postDiscard"
        imgs_html += f"""
        <div class="img-group">
          <img src="{img_path}" alt="{label}" loading="lazy">
          <span class="img-label">{label}</span>
        </div>"""

    if not imgs_html:
        imgs_html = '<span class="no-plots">No plots found — run processing first</span>'

    images_html = f'<div class="images-panel">{imgs_html}</div>'

    return f"""
<div class="condition-card">
  <div class="cond-header" style="background:{header_color}">
    <span>{cond_name}</span>
    <span class="run-tag">{run_tag}</span>
    <span class="summary">{n_pass}/{n_total} pass &nbsp;|&nbsp; {summary_str}</span>
  </div>
  <div class="cond-body">
    {breakdown_html}
    {images_html}
  </div>
</div>"""


def generate(extra_csv_paths=None, output_path=None):
    """
    Main entry point.
    extra_csv_paths: list of Path/str — additional CSVs to merge (e.g. test_reps.csv).
                     For duplicate conditions, the most recently dated entry wins.
    output_path:     where to write the HTML (defaults to ROOT/fit_evaluation_log.html).
    """
    out = Path(output_path) if output_path else OUTPUT

    df = load_csvs(extra_csv_paths)
    if df.empty:
        print("[fit log] No data found — skipping HTML generation.")
        return

    # Sort conditions by most recent date (newest first)
    df["_date_sort"] = pd.to_datetime(
        df["date"].str.replace(r"\n", " ", regex=True), errors="coerce"
    )
    cond_order = (
        df.groupby("condition")["_date_sort"]
        .max()
        .sort_values(ascending=False)
        .index.tolist()
    )

    cards_html = ""
    for cond in cond_order:
        group = df[df["condition"] == cond]
        seg_imgs, comp_imgs, run_folder = find_plots(cond)
        cards_html += condition_card(cond, group, seg_imgs, comp_imgs, run_folder)

    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_conditions = len(cond_order)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fit Evaluation Log</title>
<style>{CSS}</style>
</head>
<body>
<h1>Fit Evaluation Log</h1>
<div class="meta">
  Generated {generated_at} &nbsp;·&nbsp; {n_conditions} condition(s) &nbsp;·&nbsp;
  Pass threshold: {PASS_THRESHOLD}/100 &nbsp;·&nbsp;
  Click any image to open full size
</div>
<div class="legend">
  <div class="legend-item"><div class="dot" style="background:#2e7d32"></div> all reps pass</div>
  <div class="legend-item"><div class="dot" style="background:#e65100"></div> mixed</div>
  <div class="legend-item"><div class="dot" style="background:#b71c1c"></div> all fail</div>
  <div class="legend-item"><div class="dot" style="background:#78909c"></div> pre-processing failure</div>
  <div class="legend-item" style="color:#e0e0e0; font-size:11px">
    Scores sorted newest → oldest &nbsp;·&nbsp; re-run processing to update a condition
  </div>
</div>
{cards_html}
<script>{JS}</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"[fit log] Written → {out}  ({n_conditions} conditions)")


if __name__ == "__main__":
    generate()
