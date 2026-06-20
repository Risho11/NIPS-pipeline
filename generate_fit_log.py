#!/usr/bin/env python3
"""
generate_fit_log.py — build fit_evaluation_log.html

Reads results_reps.csv (plus any extra CSVs from test runs), finds the
corresponding segmentation plots, and writes a side-by-side HTML log.

Layout per condition:
  ┌─ condition header (colour = all-pass / mixed / all-fail / preproc-failure) ─┐
  │ rep 1 breakdown  │  Segmentation_rep-1.png                                  │
  │ rep 2 breakdown  │  Segmentation_rep-2.png                                  │
  │ rep 3 breakdown  │  Segmentation_rep-3.png                                  │
  │ Comparison_CV images (full width, if present)                                │
  └──────────────────────────────────────────────────────────────────────────────┘

Run standalone:
    python generate_fit_log.py

Called automatically by TESTS/test_processing.py after each test run.
When the same condition appears in multiple CSVs, the most recently
dated entry wins — re-running always replaces, never appends.
"""

import base64
import json
from pathlib import Path

import pandas as pd

ROOT      = Path(__file__).parent
PLOTS_DIR = ROOT / "pipeline-plots"
MAIN_CSV  = ROOT / "results_reps.csv"
OUTPUT    = ROOT / "fit_evaluation_log.html"
PASS_THRESHOLD = 70

COMPONENTS = [
    ("elastic_r2",               30, "elastic R²"),
    ("plateau_r2_start",         15, "plateau R² (first 40%)"),
    ("densification_r2",         15, "densif R²"),
    ("yield_accuracy",           25, "yield accuracy"),
    ("junction_continuity",      15, "junction continuity"),
    ("plateau_r2_full_penalty",   0, "plateau full R² pen"),
    ("elastic_modulus_penalty",   0, "E-mod penalty"),
    ("bp1_accuracy_penalty",      0, "bp1 penalty"),
    ("slope_ratio_penalty",       0, "slope ratio pen"),
]

PENALTY_KEYS = {"plateau_r2_full_penalty", "elastic_modulus_penalty", "bp1_accuracy_penalty", "slope_ratio_penalty"}
CAT_KEYS     = {"catastrophic_slope_vs_modulus", "catastrophic_slope_ordering"}


# ── data helpers ──────────────────────────────────────────────────────────────

def strip_rep(name: str) -> str:
    return name.split(" | rep")[0].split(" | sample")[0].strip()


def load_csvs(extra_csv_paths=None):
    frames = []
    for p in [MAIN_CSV] + list(extra_csv_paths or []):
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
    df["_date_sort"] = pd.to_datetime(
        df["date"].str.replace(r"\n", " ", regex=True), errors="coerce"
    )
    df = df.sort_values("_date_sort", ascending=True)
    df = df.drop_duplicates(subset=["condition", "Trial"], keep="last")
    return df


def img_to_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _collect_seg(cond_dir: Path) -> list:
    seg = []
    for rep_dir in sorted(cond_dir.glob("rep-*/")):
        hits = sorted(rep_dir.glob("Segmentation_rep-*.png"))
        if not hits:
            hits = sorted(rep_dir.glob("Pre-Processing_rep-*.png"))
        if hits:
            seg.append(hits[0])
    return seg


def find_plots(condition_name: str):
    """
    Return (seg_paths, comp_paths, run_folder_name) for the most recent run
    that contains this condition. seg_paths is a list sorted by rep directory
    so index 0 → rep-1, index 1 → rep-2, etc.
    Falls back to pipeline_plots_* (old flat format) when not found in
    pipeline-plots/run-*/.
    Falls back to Pre-Processing images when Segmentation images are missing.
    """
    if PLOTS_DIR.exists():
        for run_dir in sorted(PLOTS_DIR.glob("*/"), reverse=True):
            cond_dir = run_dir / condition_name
            if not cond_dir.is_dir():
                continue
            seg = _collect_seg(cond_dir)
            comps = sorted(cond_dir.glob("Comparison_CV*.png"))
            return seg, comps, run_dir.name

    # Fall back to old-format pipeline_plots_* directories
    for old_dir in sorted(ROOT.glob("pipeline_plots_*/"), reverse=True):
        cond_dir = old_dir / condition_name
        if not cond_dir.is_dir():
            continue
        seg = _collect_seg(cond_dir)
        comps = sorted(cond_dir.glob("Comparison_CV*.png"))
        if seg:
            return seg, comps, old_dir.name

    return [], [], None


def parse_breakdown(json_str):
    if not json_str or (isinstance(json_str, float) and pd.isna(json_str)):
        return {}
    try:
        return json.loads(json_str)
    except Exception:
        return {}


def score_color(score):
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return "#9e9e9e"
    if score >= PASS_THRESHOLD:
        return "#2e7d32"
    if score >= 60:
        return "#e65100"
    return "#b71c1c"


# ── HTML pieces ───────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 13px;
       background: #ececec; color: #222; }
h1   { font-size: 1.35rem; padding: 14px 22px; background: #263238; color: #fff; }
.meta { font-size: 11px; color: #90a4ae; padding: 3px 22px 10px;
        background: #263238; }
.legend { display: flex; gap: 14px; flex-wrap: wrap;
          padding: 8px 22px; background: #37474f; font-size: 11px; }
.legend-item { display: flex; align-items: center; gap: 5px; color: #eceff1; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }

/* ── condition card ── */
.card {
    margin: 14px 22px;
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,.14);
    background: #fff;
}
.card-header {
    display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
    padding: 9px 14px;
    color: #fff; font-weight: 600; font-size: 0.97rem;
}
.card-header .run-tag  { font-size: 11px; opacity: .8; font-weight: normal; }
.card-header .summary  { font-size: 11px; opacity: .9; margin-left: auto; }

/* ── rep row ── */
.rep-row {
    display: grid;
    grid-template-columns: 270px 1fr;
    border-top: 1px solid #e8e8e8;
    min-height: 0;
}
.rep-row:first-of-type { border-top: none; }

/* breakdown side */
.rep-left {
    padding: 10px 14px;
    border-right: 1px solid #e8e8e8;
    display: flex; flex-direction: column; gap: 6px;
}
.score-badge {
    font-size: 1.05rem; font-weight: 700; letter-spacing: .02em;
}
.breakdown-table { border-collapse: collapse; width: 100%; }
.breakdown-table td {
    padding: 2px 5px; font-size: 11px;
    border-bottom: 1px solid #f2f2f2;
    white-space: nowrap;
}
.breakdown-table td.comp { color: #546e7a; width: 140px; }
.breakdown-table td.pts  { text-align: right; font-weight: 600; width: 34px; }
.breakdown-table td.note { color: #90a4ae; font-size: 10px;
    white-space: normal; word-break: break-word; max-width: 200px; }
/* penalty row */
.pen-row td { background: #fff3e0 !important; color: #bf360c; }
/* clear penalty row (didn't fire) */
.ok-row  td { background: #f1f8e9 !important; color: #33691e; }
/* catastrophic row */
.cat-row td { background: #ffebee !important; color: #b71c1c; font-weight: 700; }
/* subtotal row (shown before catastrophic halving) */
.subtotal-row td { border-top: 1px dashed #bbb !important; padding-top: 3px !important;
    font-style: italic; color: #78909c; font-size: 11px; }
/* total score row */
.total-row td { border-top: 1px solid #ccc !important; padding-top: 4px !important;
    font-weight: 700; font-size: 12px; }

/* image side */
.rep-right {
    padding: 10px;
    background: #f9f9f9;
    display: flex; align-items: center; justify-content: center;
}
.rep-right img {
    max-width: 100%; max-height: 280px;
    object-fit: contain;
    border: 1px solid #ddd; border-radius: 3px;
    cursor: zoom-in;
    transition: box-shadow .15s;
}
.rep-right img:hover { box-shadow: 0 0 0 2px #90a4ae; }
.no-img { font-size: 11px; color: #bbb; font-style: italic; }

/* comparison CV row */
.comp-row {
    display: flex; flex-wrap: wrap; gap: 10px;
    padding: 10px 14px;
    background: #f3f3f3;
    border-top: 1px solid #e0e0e0;
}
.comp-group { display: flex; flex-direction: column; gap: 3px; align-items: center; }
.comp-group img {
    max-height: 180px; object-fit: contain;
    border: 1px solid #ddd; border-radius: 3px;
    cursor: zoom-in;
}
.comp-group img:hover { box-shadow: 0 0 0 2px #90a4ae; }
.img-label { font-size: 10px; color: #9e9e9e; }
"""

JS = """
document.querySelectorAll('img[data-fullsrc], .rep-right img, .comp-group img').forEach(img => {
  img.addEventListener('click', () => {
    const w = window.open('', '_blank');
    w.document.write('<body style="margin:0;background:#111"><img src="'
      + img.src + '" style="max-width:100%;height:auto;display:block;margin:auto"></body>');
  });
});
"""


def build_rep_breakdown(rep_data, rep_index):
    """Return the HTML for one rep's breakdown table + score badge."""
    bd    = rep_data["breakdown"]
    score = rep_data["score"]
    passed = rep_data["pass"]
    is_preproc = rep_data["is_preproc_failure"]

    # Score badge
    if is_preproc:
        badge = '<span class="score-badge" style="color:#9e9e9e">— pre-processing failure</span>'
    elif score is None or (isinstance(score, float) and pd.isna(score)):
        badge = '<span class="score-badge" style="color:#9e9e9e">—</span>'
    else:
        s = int(score)
        col = score_color(s)
        mark = "✓" if passed else "✗"
        badge = f'<span class="score-badge" style="color:{col}">{s}/100 {mark}</span>'

    if is_preproc:
        return badge + '<div style="font-size:11px;color:#9e9e9e;margin-top:4px">No fit data — membrane not detected</div>'

    rows = []
    for key, max_pts, label in COMPONENTS:
        if key not in bd:
            continue
        entry = bd[key]
        pts  = entry.get("pts")
        note = entry.get("note", "")
        max_str = f"/{max_pts}" if max_pts > 0 else ""
        pts_str = str(pts) if pts is not None else "—"

        is_penalty = key in PENALTY_KEYS
        fired = is_penalty and isinstance(pts, (int, float)) and pts < 0
        clear = is_penalty and isinstance(pts, (int, float)) and pts == 0

        row_class = "pen-row" if fired else ("ok-row" if clear else "")
        rows.append(
            f'<tr class="{row_class}">'
            f'<td class="comp">{label}</td>'
            f'<td class="pts">{pts_str}{max_str}</td>'
            f'<td class="note" title="{note}">{note}</td>'
            f'</tr>'
        )

    # Catastrophic flags (if present) — show subtotal before halving
    has_catastrophic = any(k in bd for k in CAT_KEYS)
    if has_catastrophic:
        pre_sum = sum(
            (e.get("pts") or 0)
            for k, e in bd.items()
            if not k.startswith("_") and k not in CAT_KEYS
            and isinstance(e.get("pts"), (int, float))
        )
        rows.append(
            f'<tr class="subtotal-row">'
            f'<td class="comp">subtotal</td>'
            f'<td class="pts">{pre_sum}</td>'
            f'<td class="note">before catastrophic ×0.5</td>'
            f'</tr>'
        )
    for cat_key in CAT_KEYS:
        if cat_key in bd:
            note = bd[cat_key].get("note", "")
            label = "CATASTROPHIC: slope inversion" if "vs_modulus" in cat_key else "CATASTROPHIC: slope ordering"
            rows.append(
                f'<tr class="cat-row">'
                f'<td class="comp">{label}</td>'
                f'<td class="pts">×0.5</td>'
                f'<td class="note" title="{note}">{note}</td>'
                f'</tr>'
            )

    # Total row
    s_val = int(score) if score is not None and not (isinstance(score, float) and pd.isna(score)) else "—"
    col = score_color(score) if s_val != "—" else "#9e9e9e"
    rows.append(
        f'<tr class="total-row">'
        f'<td class="comp">Score</td>'
        f'<td class="pts" style="color:{col}">{s_val}/100</td>'
        f'<td class="note"></td>'
        f'</tr>'
    )

    table = '<table class="breakdown-table">' + "".join(rows) + "</table>"
    return badge + table


def condition_card(cond_name, group_df, seg_images, comp_images, run_folder):
    group_df = group_df.sort_values("Trial").reset_index(drop=True)

    reps_data = []
    for _, row in group_df.iterrows():
        score = row.get("Good Fit Score")
        is_preproc = score is None or (isinstance(score, float) and pd.isna(score))
        reps_data.append({
            "score": score,
            "pass": bool(row.get("Good Fit", False)),
            "breakdown": parse_breakdown(row.get("Good Fit Breakdown")),
            "is_preproc_failure": is_preproc,
        })

    n_pass  = sum(r["pass"] for r in reps_data)
    n_total = len(reps_data)

    if all(r["is_preproc_failure"] for r in reps_data):
        hdr_color = "#78909c"
    elif n_pass == n_total:
        hdr_color = "#2e7d32"
    elif n_pass == 0:
        hdr_color = "#b71c1c"
    else:
        hdr_color = "#e65100"

    score_bits = []
    for r in reps_data:
        if r["is_preproc_failure"] or r["score"] is None or (isinstance(r["score"], float) and pd.isna(r["score"])):
            score_bits.append("—")
        else:
            mark = "✓" if r["pass"] else "✗"
            score_bits.append(f'{int(r["score"])}{mark}')
    summary_str = "  ".join(score_bits)

    run_tag = run_folder or "unknown run"

    # ── build one row per rep ─────────────────────────────────────────────────
    rep_rows_html = ""
    for i, rep_data in enumerate(reps_data):
        breakdown_html = build_rep_breakdown(rep_data, i)

        # Match image by index — seg_images[i] if it exists
        img_html = '<span class="no-img">No plot found</span>'
        if i < len(seg_images):
            try:
                uri = img_to_data_uri(seg_images[i])
                img_html = f'<img src="{uri}" alt="rep-{i+1}">'
            except Exception:
                pass

        rep_rows_html += f"""
  <div class="rep-row">
    <div class="rep-left">{breakdown_html}</div>
    <div class="rep-right">{img_html}</div>
  </div>"""

    # ── comparison CV images (full width) ─────────────────────────────────────
    comp_html = ""
    for img_path in comp_images:
        try:
            uri = img_to_data_uri(img_path)
            label = img_path.stem
            comp_html += f"""
    <div class="comp-group">
      <img src="{uri}" alt="{label}">
      <span class="img-label">{label}</span>
    </div>"""
        except Exception:
            pass
    comp_row = f'<div class="comp-row">{comp_html}</div>' if comp_html else ""

    return f"""
<div class="card">
  <div class="card-header" style="background:{hdr_color}">
    <span>{cond_name}</span>
    <span class="run-tag">{run_tag}</span>
    <span class="summary">{n_pass}/{n_total} pass &nbsp;|&nbsp; {summary_str}</span>
  </div>
  {rep_rows_html}
  {comp_row}
</div>"""


# ── main ──────────────────────────────────────────────────────────────────────

def generate(extra_csv_paths=None, output_path=None):
    """
    Regenerate fit_evaluation_log.html from scratch.
    extra_csv_paths: additional CSVs to merge (e.g. from test_processing.py).
    output_path:     override output location.
    """
    out = Path(output_path) if output_path else OUTPUT

    df = load_csvs(extra_csv_paths)
    if df.empty:
        print("[fit log] No data found — skipping HTML generation.")
        return

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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fit Evaluation Log</title>
<style>{CSS}</style>
</head>
<body>
<h1>Fit Evaluation Log</h1>
<div class="meta">Generated {generated_at} &nbsp;·&nbsp; {len(cond_order)} condition(s) &nbsp;·&nbsp;
  Pass threshold: {PASS_THRESHOLD}/100 &nbsp;·&nbsp; Click any image to open full size</div>
<div class="legend">
  <div class="legend-item"><div class="dot" style="background:#2e7d32"></div>all pass</div>
  <div class="legend-item"><div class="dot" style="background:#e65100"></div>mixed</div>
  <div class="legend-item"><div class="dot" style="background:#b71c1c"></div>all fail</div>
  <div class="legend-item"><div class="dot" style="background:#78909c"></div>pre-processing failure</div>
  <div class="legend-item" style="color:#cfd8dc;font-size:11px">newest first · re-run processing to update</div>
</div>
{cards_html}
<script>{JS}</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"[fit log] Written → {out}  ({len(cond_order)} conditions)")


if __name__ == "__main__":
    generate()
