#!/usr/bin/env python3
"""
generate_fit_log.py — build fit_evaluation_log.html

Reads results_reps.csv (plus any extra CSVs from test runs), finds the
corresponding segmentation plots, and writes a side-by-side HTML log.

Layout per condition:
  ┌─ condition header (colour = all-pass / mixed / all-fail / preproc-failure) ─┐
  │ rep 1: toe ε / supervisor checkboxes / breakdown table | Segmentation image  │
  │ rep 2: ...                                                                    │
  │ rep 3: ...                                                                    │
  │ Comparison_CV images + raw_average_curves (full width)                        │
  │ Pre CV / Post CV summary                                                      │
  │ [▶ Average Fits] (collapsed by default)                                       │
  └──────────────────────────────────────────────────────────────────────────────┘

Run standalone:
    python generate_fit_log.py

Called automatically by tests/test_processing.py after each test run.
When the same condition appears in multiple CSVs, the most recently
dated entry wins — re-running always replaces, never appends.
"""

import datetime
import json
import re
import shutil
from pathlib import Path

import pandas as pd

FILE_DIR    = Path(__file__).parent
ROOT        = FILE_DIR.parent  # project root — this script lives in EVALUATE/
PLOTS_DIR   = ROOT / "data" / "plots"
RESULTS_DIR = ROOT / "data" / "results"
RAW_ROOT    = ROOT / "data" / "raw"
# Lives under docs/ so GitHub Pages can serve it straight off main (Settings > Pages > docs/).
OUTPUT      = ROOT / "docs" / "fit_evaluation_log.html"
PASS_THRESHOLD = 70

_SPECIMEN_TS_RE = re.compile(r"(\d{8})_(\d{6})")


def true_condition_date(cond_name):
    """Earliest Specimen_*.csv timestamp for this condition under data/raw/.

    The CSV `date` column is NOT the campaign date -- save_to_csv() stamps it with
    datetime.now() at processing time (curve_segmentation.py). That's fine for a live
    run_loop.py run (now ~= when it happened), but a reprocess/backfill through
    test_processing.py stamps every row with today's date regardless of when the
    specimens were actually pulled, which silently wrecked "newest first" card order
    after a full-batch rerun (everything ties on the rerun date). Reading the real
    timestamp baked into each raw specimen filename instead.
    """
    d = RAW_ROOT / cond_name
    if not d.is_dir():
        return None
    stamps = []
    for f in d.glob("Specimen_*.csv"):
        m = _SPECIMEN_TS_RE.search(f.name)
        if m:
            try:
                stamps.append(datetime.datetime.strptime(m.group(1) + m.group(2), "%m%d%Y%H%M%S"))
            except ValueError:
                pass
    return min(stamps) if stamps else None

COMPONENTS = [
    ("elastic_r2",               30, "elastic R²"),
    ("plateau_r2_start",         15, "plateau R² (first 40%)"),
    ("densification_r2",         15, "densif R²"),
    ("yield_accuracy",           25, "yield accuracy"),
    ("junction_continuity",      15, "junction continuity"),
    ("plateau_r2_full_penalty",   0, "plateau full R² pen"),
    ("elastic_modulus_penalty",   0, "E-mod penalty"),
    ("bp1_accuracy_penalty",      0, "bp1 penalty"),
    ("slope_ratio_penalty",            0, "slope ratio pen"),
    ("changepoint_curvature_penalty",  0, "CP curvature pen"),
]

PENALTY_KEYS = {"plateau_r2_full_penalty", "elastic_modulus_penalty", "bp1_accuracy_penalty", "slope_ratio_penalty", "changepoint_curvature_penalty"}
CAT_KEYS     = {"catastrophic_slope_vs_modulus", "catastrophic_slope_ordering"}


# ── data helpers ──────────────────────────────────────────────────────────────

def strip_rep(name: str) -> str:
    return name.split(" | rep")[0].split(" | sample")[0].strip()


def load_csvs(extra_csv_paths=None):
    frames = []
    main_csvs = sorted(RESULTS_DIR.glob("begins_*/reps.csv"))
    for p in main_csvs + list(extra_csv_paths or []):
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


def load_agg_cvs(agg_csv_paths=None):
    """Return dict: condition_name -> (pre_cv, post_cv) from agg CSVs."""
    frames = []
    main_aggs = sorted(RESULTS_DIR.glob("begins_*/agg.csv"))
    for p in main_aggs + list(agg_csv_paths or []):
        p = Path(p)
        if p.exists() and p.stat().st_size > 0:
            try:
                frames.append(pd.read_csv(p))
            except Exception:
                pass
    if not frames:
        return {}
    df = pd.concat(frames, ignore_index=True)
    df["_date_sort"] = pd.to_datetime(
        df["date"].str.replace(r"\n", " ", regex=True), errors="coerce"
    )
    df = df.sort_values("_date_sort", ascending=True)
    df = df.drop_duplicates(subset=["name"], keep="last")

    result = {}
    for _, row in df.iterrows():
        raw_name = str(row.get("name", ""))
        cv_val = row.get("CV Mean")
        if pd.isna(cv_val):
            cv_val = None
        if raw_name.endswith("_preDiscard"):
            cond = raw_name[: -len("_preDiscard")]
            entry = result.setdefault(cond, [None, None])
            entry[0] = cv_val
        elif raw_name.endswith("_postDiscard"):
            cond = raw_name[: -len("_postDiscard")]
            entry = result.setdefault(cond, [None, None])
            entry[1] = cv_val
        else:
            entry = result.setdefault(raw_name, [None, None])
            if entry[0] is None:
                entry[0] = cv_val
    return {k: tuple(v) for k, v in result.items()}


def copy_asset(path: Path, assets_dir: Path, cond_safe: str, used_assets: set = None) -> str:
    """Copy path into assets_dir/cond_safe/ (scoped per-condition since rep filenames like
    Segmentation_rep-1.png repeat across conditions) and return the relative <img src> for it.
    Linked files instead of base64 data URIs -- embedding kept fit_evaluation_log.html at ~80MB
    (every plot re-encoded inline on every regen), which blew past GitHub's recommended file
    size and made every commit carry a full new multi-MB blob. Plain files sit outside git
    history (or diff cleanly) and load faster in the browser besides.

    Only copies when the dest is missing/stale (mtime-gated) -- generate() no longer wipes
    assets_dir up front, so an unchanged source file keeps its dest's original mtime. That's
    what lets `git add` skip rehashing it via git's stat cache instead of touching all ~2000
    asset files (and their full content) on every regen.
    """
    dest_dir = assets_dir / cond_safe
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if not dest.exists() or dest.stat().st_mtime < path.stat().st_mtime:
        shutil.copy2(path, dest)
    if used_assets is not None:
        used_assets.add(dest.resolve())
    return f"assets/fit/{cond_safe}/{path.name}"


_RUN_SUFFIX_RE = re.compile(r"^_run(\d+)$")


def _best_condition_dir(parent_dir: Path, condition_name: str):
    """Find condition_name (or condition_name_run2, _run3, ...) under parent_dir and return
    the highest-numbered one -- curve_segmentation.process_zero_sample_pairs_pipeline never
    overwrites a same-day plot folder, it bumps to _run2/_run3/... on every rerun instead, so
    the plain condition_name folder can be a stale run from earlier the same day while the
    freshest plots sit in a _runN sibling. condition_name itself counts as run 1.
    """
    best, best_n = None, -1
    if not parent_dir.is_dir():
        return None
    for child in parent_dir.iterdir():
        if not child.is_dir():
            continue
        if child.name == condition_name:
            n = 1
        elif child.name.startswith(condition_name + "_run"):
            m = _RUN_SUFFIX_RE.match(child.name[len(condition_name):])
            if not m:
                continue
            n = int(m.group(1))
        else:
            continue
        if n > best_n:
            best, best_n = child, n
    return best


def find_plots(condition_name: str):
    """
    Return (seg_paths, comp_paths, avg_fit_paths, run_folder_name).
    comp_paths includes raw_average_curves.png if present.
    avg_fit_paths contains average_fit_*.png from averageFits/.
    Priority: real run-* dirs first, then pseudo-runs/test-* dirs.
    Within each day-folder, the most recently-rerun _runN variant wins over the plain folder.
    Prefers Segmentation images; falls back to Pre-Processing.
    """
    candidates = []

    if PLOTS_DIR.exists():
        for d in sorted(PLOTS_DIR.glob("run-*/"), reverse=True):
            cond = _best_condition_dir(d, condition_name)
            if cond is not None:
                candidates.append(cond)
        pseudo = PLOTS_DIR / "pseudo-runs"
        if pseudo.exists():
            for d in sorted(pseudo.glob("test-*/"), reverse=True):
                cond = _best_condition_dir(d, condition_name)
                if cond is not None:
                    candidates.append(cond)

    for old in sorted(ROOT.glob("pipeline_plots_*/"), reverse=True):
        cond = _best_condition_dir(old, condition_name)
        if cond is not None:
            candidates.append(cond)

    def get_seg(cond_dir, pattern):
        seg = []
        for rep_dir in sorted(cond_dir.glob("rep-*/")):
            hits = sorted(rep_dir.glob(pattern))
            if hits:
                seg.append(hits[0])
        return seg

    def get_derivs(cond_dir):
        derivs = []
        for rep_dir in sorted(cond_dir.glob("rep-*/")):
            hits = sorted(rep_dir.glob("Derivatives_rep-*.png"))
            derivs.append(hits[0] if hits else None)
        return derivs

    def get_comps(cond_dir):
        comps = sorted(cond_dir.glob("Comparison_CV*.png"))
        avg_dir = cond_dir / "averageFits"
        if avg_dir.is_dir():
            raw_avg = avg_dir / "raw_average_curves.png"
            if raw_avg.exists():
                comps = list(comps) + [raw_avg]
        return comps

    def get_avg_fits(cond_dir):
        avg_dir = cond_dir / "averageFits"
        if not avg_dir.is_dir():
            return []
        # return (fit_png, eval_dict_or_None, deriv_png_or_None) triples
        triples = []
        for png in sorted(avg_dir.glob("average_fit_*.png")):
            json_path = avg_dir / (png.stem + "_eval.json")
            eval_data = None
            if json_path.exists():
                try:
                    eval_data = json.loads(json_path.read_text())
                except Exception:
                    pass
            deriv_png = avg_dir / ("Derivatives_" + png.name)
            triples.append((png, eval_data, deriv_png if deriv_png.exists() else None))
        return triples

    # Images: test runs first (so regenerated plots take priority over old real-run PNGs).
    # Run tag (name shown in header): real runs first (original naming convention).
    test_cands = [c for c in candidates if c.parent.name.startswith("test-")]
    real_cands = [c for c in candidates if not c.parent.name.startswith("test-")]
    comp_search_order = test_cands + real_cands

    # seg_run from real runs first (naming), seg images from test runs first (freshness)
    seg_run = None
    for cond_dir in candidates:
        if get_seg(cond_dir, "Segmentation_rep-*.png") or get_seg(cond_dir, "Pre-Processing_rep-*.png"):
            seg_run = cond_dir.parent.name
            break

    seg = []
    seg_dir = None
    for cond_dir in comp_search_order:
        s = get_seg(cond_dir, "Segmentation_rep-*.png")
        if s:
            seg = s
            seg_dir = cond_dir
            break
    if not seg:
        for cond_dir in comp_search_order:
            s = get_seg(cond_dir, "Pre-Processing_rep-*.png")
            if s:
                seg = s
                seg_dir = cond_dir
                break

    if seg_run is None and seg_dir is not None:
        seg_run = seg_dir.parent.name

    # Derivatives: same priority as comp/avg — test runs first (most recent)
    derivs = []
    for cond_dir in comp_search_order:
        d = get_derivs(cond_dir)
        if any(p is not None for p in d):
            derivs = d
            break

    comps = []
    for cond_dir in comp_search_order:
        c = get_comps(cond_dir)
        if c:
            comps = c
            break

    avg_fits = []
    for cond_dir in comp_search_order:
        a = get_avg_fits(cond_dir)
        if a:
            avg_fits = a
            break

    return seg, comps, avg_fits, derivs, seg_run


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


def _safe_key(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", s)


# ── HTML pieces ───────────────────────────────────────────────────────────────

CSS = """
:root { --navbar-h: 68px; }
body.scrolled { --navbar-h: 42px; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 13px;
       background: #ececec; color: #222; }
h1   { height: var(--navbar-h); font-size: 1.35rem; padding: 0 22px; background: #263238; color: #fff;
       display: flex; align-items: center; gap: 16px;
       position: sticky; top: 0; z-index: 600; box-shadow: 0 2px 6px rgba(0,0,0,.2);
       transition: height .15s ease, font-size .15s ease; overflow: hidden; }
body.scrolled h1 { font-size: 1.05rem; }
.page-nav { display: flex; gap: 8px; font-size: 12px; font-weight: normal; }
.page-nav a { color: #90a4ae; text-decoration: none; padding: 3px 9px; border-radius: 3px; }
.page-nav a:hover { background: #37474f; color: #fff; }
.page-nav a.active { background: #455a64; color: #fff; }
.meta { font-size: 11px; color: #90a4ae; padding: 3px 22px 10px;
        background: #263238; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
          padding: 8px 22px; background: #37474f; font-size: 11px; }
.legend-item { display: flex; align-items: center; gap: 5px; color: #eceff1; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
#toggle-all, #export-flags {
    margin-left: auto; padding: 4px 10px; font-size: 11px; cursor: pointer;
    background: #546e7a; color: #eceff1; border: 1px solid #78909c;
    border-radius: 3px; white-space: nowrap;
}
#export-flags { margin-left: 0; }
#toggle-all:hover, #export-flags:hover { background: #607d8b; }
#export-flags.dirty { background: #e65100; border-color: #ff9800; }

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
    cursor: pointer; user-select: none;
}
.card-header .toggle-icon { font-size: 12px; opacity: .8; transition: transform .18s; flex-shrink: 0; }
.card-header.collapsed .toggle-icon { transform: rotate(-90deg); }
.card-header .run-tag  { font-size: 11px; opacity: .8; font-weight: normal; }
.card-header .summary  { font-size: 11px; opacity: .9; margin-left: auto; }
.card-body.collapsed   { display: none; }

/* ── rep row ── */
.rep-row {
    display: grid;
    grid-template-columns: minmax(220px, 30%) 1fr;
    border-top: 1px solid #e8e8e8;
    min-height: 0;
}
.rep-row:first-of-type { border-top: none; }
.rep-deriv {
    display: none;
    padding: 10px;
    background: #f5f5f5;
    border-left: 1px solid #e8e8e8;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    min-width: 0;
}
.rep-deriv img { max-width: 100%; max-height: 280px; object-fit: contain;
    border: 1px solid #ddd; border-radius: 3px; cursor: zoom-in; }
.rep-deriv img:hover { box-shadow: 0 0 0 2px #90a4ae; }
body.show-derivs .rep-row-has-deriv { grid-template-columns: minmax(220px, 30%) 1fr 1fr; }
body.show-derivs .rep-row-has-deriv .rep-deriv { display: flex; }
@media (max-width: 750px) {
    .rep-row { grid-template-columns: 1fr; }
    .rep-left { border-right: none; border-bottom: 1px solid #e8e8e8; }
}

/* breakdown side */
.rep-left {
    padding: 10px 14px;
    border-right: 1px solid #e8e8e8;
    display: flex; flex-direction: column; gap: 6px;
}
.score-badge {
    font-size: 1.05rem; font-weight: 700; letter-spacing: .02em;
}
.breakdown-table { border-collapse: collapse; width: 100%; table-layout: fixed; }
.breakdown-table td {
    padding: 2px 5px; font-size: 11px;
    border-bottom: 1px solid #f2f2f2;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.breakdown-table td.comp { color: #546e7a; width: 72%; }
.breakdown-table td.pts  { text-align: right; font-weight: 600; width: 28%; }
.breakdown-table td.note { display: none; }
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

/* toe region */
.toe-val { font-size: 11px; color: #607d8b; }

/* supervisor checkboxes */
.supervisor-row { display: flex; gap: 10px; flex-wrap: wrap; padding: 3px 0; }
.sv-label { font-size: 11px; display: flex; align-items: center; gap: 3px;
            cursor: pointer; color: #444; }
.sv-label input[type=checkbox] { accent-color: #546e7a; cursor: pointer; }
.sv-label.sv-good input { accent-color: #2e7d32; }
.sv-label.sv-badfit input { accent-color: #b71c1c; }
.sv-label.sv-badeval input { accent-color: #e65100; }
.sv-label.sv-disabled { opacity: 0.32; pointer-events: none; }

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

/* CV summary line */
.cv-summary {
    padding: 5px 14px; font-size: 11px; color: #546e7a;
    background: #f3f3f3; border-top: 1px solid #e0e0e0;
}

/* average fits collapsible */
.avg-fits-header {
    padding: 6px 14px; font-size: 11px; font-weight: 600;
    cursor: pointer; background: #eceff1; color: #455a64;
    border-top: 1px solid #cfd8dc; user-select: none;
}
.avg-fits-header:hover { background: #e0e7eb; }
.avg-fits-scores { font-weight: normal; opacity: 0.75; margin-left: 8px; }
.avg-fits-body { display: block; background: #f9f9f9; border-top: 1px solid #e0e0e0; }
.avg-fits-body.collapsed { display: none; }
.avg-fits-body .rep-row { border-top: 1px solid #e8e8e8; }
.avg-fits-body .rep-row:first-child { border-top: none; }

/* ── filter bar ── */
#filter-bar {
    display: flex; flex-wrap: wrap; align-items: center; gap: 16px;
    padding: 8px 22px; background: #455a64; font-size: 11px; color: #eceff1;
    border-bottom: 1px solid #37474f;
    position: sticky; top: var(--navbar-h); z-index: 500;
    box-shadow: 0 2px 6px rgba(0,0,0,.2);
    transition: top .15s ease;
}
#filter-bar label { display: flex; align-items: center; gap: 5px; cursor: pointer; }
#filter-bar input[type=checkbox] { accent-color: #90a4ae; cursor: pointer; }
#search-bar {
    background: #546e7a; color: #eceff1; border: 1px solid #78909c;
    border-radius: 3px; padding: 3px 8px; font-size: 11px; width: 200px;
    outline: none;
}
#search-bar::placeholder { color: #90a4ae; }
#search-bar:focus { border-color: #b0bec5; }
#run-select { background: #546e7a; color: #eceff1;
    border: 1px solid #78909c; border-radius: 3px; padding: 3px 7px;
    font-size: 11px; cursor: pointer; }
/* pen-clicker toggle: stays visually "pressed in" while active */
#sort-toggle {
    background: #546e7a; color: #eceff1; border: 1px solid #78909c;
    border-radius: 3px; padding: 4px 10px; font-size: 11px; cursor: pointer;
    box-shadow: 0 2px 3px rgba(0,0,0,.3);
    transform: translateY(0); transition: transform .08s ease, box-shadow .08s ease;
}
#sort-toggle:hover { background: #607d8b; }
#sort-toggle.pressed {
    background: #78909c; border-color: #90a4ae; color: #fff;
    box-shadow: none;
    transform: translateY(0.5px);
}
#sort-toggle.pressed:hover { background: #839aa5; }
#filter-count { color: #90a4ae; font-style: italic; }

/* hover tooltip for breakdown notes */
#bd-tooltip {
    position: fixed; z-index: 9999; pointer-events: none;
    background: #263238; color: #eceff1; font-size: 11px;
    padding: 5px 9px; border-radius: 4px; max-width: 280px;
    white-space: normal; word-break: break-word;
    box-shadow: 0 2px 8px rgba(0,0,0,.35);
    opacity: 0; transition: opacity .1s;
}
.breakdown-table td.comp[data-note] { cursor: help; }
"""

JS = """
// navbar starts full-size; once the page scrolls (so it's actually pinned via
// position:sticky) it shrinks -- .scrolled flips --navbar-h, which both the
// navbar's height and #filter-bar's stacking offset read from, so they stay
// flush with no extra JS needed to keep them in sync.
window.addEventListener('scroll', () => {
  document.body.classList.toggle('scrolled', window.scrollY > 4);
}, { passive: true });

document.querySelectorAll('img[data-fullsrc], .rep-right img, .comp-group img').forEach(img => {
  img.addEventListener('click', () => {
    const w = window.open('', '_blank');
    w.document.write('<body style="margin:0;background:#111"><img src="'
      + img.src + '" style="max-width:100%;height:auto;display:block;margin:auto"></body>');
  });
});
document.querySelectorAll('.card-header').forEach(header => {
  header.addEventListener('click', () => {
    const isOpen = !header.classList.contains('collapsed');
    header.nextElementSibling.classList.toggle('collapsed', isOpen);
    header.classList.toggle('collapsed', isOpen);
    syncToggleAllLabel();
  });
});
function syncToggleAllLabel() {
  const btn = document.getElementById('toggle-all');
  const allCollapsed = [...document.querySelectorAll('.card-header')].every(h => h.classList.contains('collapsed'));
  btn.textContent = allCollapsed ? 'Expand All' : 'Collapse All';
}
// ── filters ──────────────────────────────────────────────────────────────────
const cards = [...document.querySelectorAll('.card')];

// build run-date dropdown dynamically from cards
const runSelect = document.getElementById('run-select');
const uniqueRuns = [...new Set(cards.map(c => c.dataset.run))].sort().reverse();
uniqueRuns.forEach(run => {
  const opt = document.createElement('option');
  opt.value = run; opt.textContent = run;
  runSelect.appendChild(opt);
});

function applyFilters() {
  const activeStatus = new Set(
    [...document.querySelectorAll('#filter-bar input[data-status]:checked')].map(i => i.dataset.status)
  );
  const runVal = runSelect.value;
  const toeOnly = document.getElementById('filter-toe').checked;
  const searchVal = document.getElementById('search-bar').value.trim().toLowerCase();
  let visible = 0;
  cards.forEach(card => {
    const runMatch = !runVal || card.dataset.run === runVal;
    const toeMatch = !toeOnly || card.dataset.hasToe === '1';
    const searchMatch = !searchVal || card.dataset.name.includes(searchVal);
    const show = activeStatus.has(card.dataset.status) && runMatch && toeMatch && searchMatch;
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.getElementById('filter-count').textContent = `${visible} / ${cards.length} shown`;
}

// cards start in DOM order by real campaign date (server-rendered, newest first -- see
// true_condition_date() in generate_fit_log.py); `cards` itself is never reordered, only the
// DOM nodes are, so it always holds that original by-campaign order to toggle back to.
// #sort-toggle is a pen-clicker: off (default) = that campaign order; pressed = by processing
// date instead (data-procdate, when the row was last actually (re)run -- useful right after a
// batch reprocess to see what just changed, separate from true campaign chronology).
const sortToggle = document.getElementById('sort-toggle');
const cardsContainer = cards[0] ? cards[0].parentElement : null;
function applySortOrder() {
  if (!cardsContainer) return;
  const byProcessing = sortToggle.classList.contains('pressed');
  const ordered = byProcessing
    ? [...cards].sort((a, b) => Number(b.dataset.procdate) - Number(a.dataset.procdate))
    : cards;
  ordered.forEach(card => cardsContainer.appendChild(card));
}
sortToggle.addEventListener('click', () => {
  sortToggle.classList.toggle('pressed');
  applySortOrder();
});

document.querySelectorAll('#filter-bar input[type=checkbox]').forEach(cb => {
  cb.addEventListener('change', applyFilters);
});
runSelect.addEventListener('change', applyFilters);
document.getElementById('search-bar').addEventListener('input', applyFilters);
document.getElementById('filter-toe').addEventListener('change', applyFilters);
document.getElementById('toggle-derivs').addEventListener('change', function() {
  const show = this.checked;
  document.querySelectorAll('.rep-row-has-deriv').forEach(row => {
    row.style.gridTemplateColumns = show ? 'minmax(220px, 30%) 1fr 1fr' : '';
  });
  document.querySelectorAll('.rep-deriv').forEach(el => {
    el.style.display = show ? 'flex' : 'none';
  });
});
applyFilters();
// ─────────────────────────────────────────────────────────────────────────────

const tip = document.getElementById('bd-tooltip');
document.querySelectorAll('.breakdown-table td.comp[data-note]').forEach(td => {
  td.addEventListener('mouseenter', e => {
    const note = td.dataset.note;
    if (!note) return;
    tip.textContent = note;
    tip.style.opacity = '1';
  });
  td.addEventListener('mousemove', e => {
    tip.style.left = (e.clientX + 12) + 'px';
    tip.style.top  = (e.clientY + 12) + 'px';
  });
  td.addEventListener('mouseleave', () => { tip.style.opacity = '0'; });
});
document.getElementById('toggle-all').addEventListener('click', () => {
  const allCollapsed = [...document.querySelectorAll('.card-header')].every(h => h.classList.contains('collapsed'));
  document.querySelectorAll('.card-header').forEach(h => {
    h.classList.toggle('collapsed', !allCollapsed);
    h.nextElementSibling.classList.toggle('collapsed', !allCollapsed);
  });
  syncToggleAllLabel();
});

// ── average fits toggle ───────────────────────────────────────────────────────
document.querySelectorAll('.avg-fits-header').forEach(h => {
  h.addEventListener('click', () => {
    const body = h.nextElementSibling;
    const nowCollapsed = body.classList.toggle('collapsed');
    const icon = h.querySelector('.avg-icon');
    if (icon) icon.textContent = nowCollapsed ? '▶' : '▼';
  });
});

// ── supervisor checkboxes — git-committed JSON persistence ────────────────────
// Flags live in supervisor_flags.json (checked into the repo, sits next to this
// HTML) instead of localStorage, so they follow the page across browsers/devices
// via git rather than being stuck to one browser's local storage. Editing a box
// only changes the in-page copy; hit "Export Flags" and overwrite
// supervisor_flags.json with the download, then commit, to make it stick.
let svFlags = {};
const exportBtn = document.getElementById('export-flags');

function _markDirty() {
  exportBtn.classList.add('dirty');
  exportBtn.textContent = 'Export Flags*';
}

function _updateSvRow(row, fromLoad) {
  const badfit  = row.querySelector('[data-flag="badfit"]').checked;
  const badeval = row.querySelector('[data-flag="badeval"]').checked;
  const good    = row.querySelector('[data-flag="good"]').checked;
  const goodLabel  = row.querySelector('.sv-good');
  const badLabels  = [...row.querySelectorAll('.sv-label:not(.sv-good)')];
  goodLabel.classList.toggle('sv-disabled',  badfit || badeval);
  badLabels.forEach(l => l.classList.toggle('sv-disabled', good));
  const k = row.dataset.key;
  svFlags[k] = { badfit, badeval, good };
  if (!fromLoad) _markDirty();
}

async function loadSvFlags() {
  try {
    const res = await fetch('supervisor_flags.json', { cache: 'no-store' });
    if (res.ok) svFlags = await res.json();
  } catch (e) {
    // file:// or offline — fetch of a local JSON is blocked by CORS in most
    // browsers; just start from an empty set rather than failing the page.
  }
  document.querySelectorAll('.supervisor-row').forEach(row => {
    const k = row.dataset.key;
    const f = svFlags[k] || {};
    row.querySelector('[data-flag="badfit"]').checked  = !!f.badfit;
    row.querySelector('[data-flag="badeval"]').checked = !!f.badeval;
    row.querySelector('[data-flag="good"]').checked    = !!f.good;
    _updateSvRow(row, /*fromLoad=*/true);
    row.querySelectorAll('[data-flag]').forEach(cb => cb.addEventListener('change', () => _updateSvRow(row)));
  });
}
loadSvFlags();

exportBtn.addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(svFlags, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'supervisor_flags.json';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  exportBtn.classList.remove('dirty');
  exportBtn.textContent = 'Export Flags';
});
"""


def build_rep_breakdown(rep_data, rep_index):
    """Return the HTML for one rep's breakdown table + score badge."""
    bd    = rep_data["breakdown"]
    score = rep_data["score"]
    passed = rep_data["pass"]
    is_preproc = rep_data["is_preproc_failure"]
    toe   = rep_data.get("toe_region")
    sv_key = rep_data.get("sv_key", "")

    # Toe region line
    if toe is not None and not (isinstance(toe, float) and pd.isna(toe)):
        toe_html = f'<div class="toe-val">toe ε = {float(toe):.4f}</div>'
    else:
        toe_html = '<div class="toe-val">toe ε = —</div>'

    # Supervisor checkboxes
    sv_html = f"""<div class="supervisor-row" data-key="{sv_key}">
  <label class="sv-label sv-badfit"><input type="checkbox" data-flag="badfit"> Bad Fit</label>
  <label class="sv-label sv-badeval"><input type="checkbox" data-flag="badeval"> Bad Eval</label>
  <label class="sv-label sv-good"><input type="checkbox" data-flag="good"> Good</label>
</div>"""

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
        return (toe_html + sv_html + badge
                + '<div style="font-size:11px;color:#9e9e9e;margin-top:4px">No fit data — membrane not detected</div>')

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
            f'<td class="comp" data-note="{note}">{label}</td>'
            f'<td class="pts">{pts_str}{max_str}</td>'
            f'<td class="note">{note}</td>'
            f'</tr>'
        )

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
    return toe_html + sv_html + badge + table


def _epoch_ms(dt_val):
    """datetime.datetime or pd.Timestamp (or None/NaT) -> epoch milliseconds, 0 if unknown."""
    if dt_val is None or pd.isna(dt_val):
        return 0
    return int(dt_val.timestamp() * 1000)


def condition_card(cond_name, group_df, seg_images, comp_images, avg_fit_images,
                   deriv_images, run_folder, assets_dir, used_assets, pre_cv=None, post_cv=None,
                   sort_date=None, proc_date=None):
    group_df = group_df.sort_values("Trial").reset_index(drop=True)
    cond_safe = _safe_key(cond_name)

    # avg evaluation comes from JSON sidecars, not CSV rows — use all rows as reps
    rep_rows_df = group_df.reset_index(drop=True)

    reps_data = []
    for idx, (_, row) in enumerate(rep_rows_df.iterrows()):
        score = row.get("Good Fit Score")
        is_preproc = score is None or (isinstance(score, float) and pd.isna(score))
        toe = row.get("Toe Region")
        reps_data.append({
            "score": score,
            "pass": bool(row.get("Good Fit", False)),
            "breakdown": parse_breakdown(row.get("Good Fit Breakdown")),
            "is_preproc_failure": is_preproc,
            "toe_region": toe,
            "sv_key": f"{cond_safe}_{idx}",
        })

    n_pass  = sum(r["pass"] for r in reps_data)
    n_total = len(reps_data)

    if all(r["is_preproc_failure"] for r in reps_data):
        hdr_color = "#78909c"
        status = "preproc"
    elif n_pass == n_total:
        hdr_color = "#2e7d32"
        status = "pass"
    elif n_pass == 0:
        hdr_color = "#b71c1c"
        status = "fail"
    else:
        hdr_color = "#e65100"
        status = "mixed"

    score_bits = []
    for r in reps_data:
        if r["is_preproc_failure"] or r["score"] is None or (isinstance(r["score"], float) and pd.isna(r["score"])):
            score_bits.append("—")
        else:
            mark = "✓" if r["pass"] else "✗"
            score_bits.append(f'{int(r["score"])}{mark}')
    avg_score_bits = []
    for avg_img_path, eval_data, _deriv in avg_fit_images:
        if eval_data is not None:
            s = eval_data.get("Good Fit Score")
            p = bool(eval_data.get("Good Fit", False))
            if s is not None:
                mark = "✓" if p else "✗"
                lbl = avg_img_path.stem.replace("average_fit_", "") if hasattr(avg_img_path, "stem") else ""
                avg_score_bits.append(f'avg({lbl}):{int(s)}{mark}')
    summary_str = "  ".join(score_bits)

    run_tag = run_folder or "unknown run"

    # ── rep rows ─────────────────────────────────────────────────────────────
    rep_rows_html = ""
    for i, rep_data in enumerate(reps_data):
        breakdown_html = build_rep_breakdown(rep_data, i)
        img_html = '<span class="no-img">No plot found</span>'
        if i < len(seg_images):
            try:
                uri = copy_asset(seg_images[i], assets_dir, cond_safe, used_assets)
                img_html = f'<img src="{uri}" alt="rep-{i+1}">'
            except Exception:
                pass

        deriv_col = ""
        deriv_path = deriv_images[i] if i < len(deriv_images) else None
        if deriv_path is not None:
            try:
                uri = copy_asset(deriv_path, assets_dir, cond_safe, used_assets)
                deriv_col = f'<div class="rep-deriv"><img src="{uri}" alt="deriv-{i+1}"></div>'
            except Exception:
                pass

        rep_rows_html += f"""
  <div class="rep-row{' rep-row-has-deriv' if deriv_col else ''}">
    <div class="rep-left">{breakdown_html}</div>
    <div class="rep-right">{img_html}</div>
    {deriv_col}
  </div>"""

    # ── comparison CV + raw average images ───────────────────────────────────
    comp_html = ""
    for img_path in comp_images:
        try:
            uri = copy_asset(img_path, assets_dir, cond_safe, used_assets)
            label = img_path.stem
            comp_html += f"""
    <div class="comp-group">
      <img src="{uri}" alt="{label}">
      <span class="img-label">{label}</span>
    </div>"""
        except Exception:
            pass
    comp_row = f'<div class="comp-row">{comp_html}</div>' if comp_html else ""

    # ── CV summary line ───────────────────────────────────────────────────────
    cv_parts = []
    if pre_cv is not None:
        cv_parts.append(f"Pre CV: {pre_cv:.4f}")
    if post_cv is not None:
        cv_parts.append(f"Post CV: {post_cv:.4f}")
    cv_summary = (f'<div class="cv-summary">{" &nbsp;|&nbsp; ".join(cv_parts)}</div>'
                  if cv_parts else "")

    # ── average fits collapsible ──────────────────────────────────────────────
    avg_fits_html = ""
    if avg_fit_images:
        inner = ""
        for img_path, eval_data, deriv_path in avg_fit_images:
            try:
                uri = copy_asset(img_path, assets_dir, cond_safe, used_assets)
                stem = img_path.stem
                suffix = stem.replace("average_fit_", "")
                if eval_data is not None:
                    bd_data = {
                        "score": eval_data.get("Good Fit Score"),
                        "pass": bool(eval_data.get("Good Fit", False)),
                        "breakdown": parse_breakdown(eval_data.get("Good Fit Breakdown")),
                        "is_preproc_failure": False,
                        "toe_region": eval_data.get("Toe Region"),
                        "sv_key": f"{cond_safe}_avg_{suffix}",
                    }
                    left_html = build_rep_breakdown(bd_data, 0)
                else:
                    left_html = f'<span style="font-size:11px;color:#bbb;font-style:italic">{stem}</span>'
                deriv_col = ""
                if deriv_path is not None:
                    try:
                        d_uri = copy_asset(deriv_path, assets_dir, cond_safe, used_assets)
                        deriv_col = f'<div class="rep-deriv"><img src="{d_uri}" alt="deriv-{stem}"></div>'
                    except Exception:
                        pass
                inner += f"""
      <div class="rep-row{' rep-row-has-deriv' if deriv_col else ''}">
        <div class="rep-left" style="background:#f7f9fa">{left_html}</div>
        <div class="rep-right"><img src="{uri}" alt="{stem}"></div>
        {deriv_col}
      </div>"""
            except Exception:
                pass
        if inner:
            avg_score_header = "  ".join(avg_score_bits)
            score_span = (f' <span class="avg-fits-scores">{avg_score_header}</span>'
                          if avg_score_header else "")
            avg_fits_html = f"""
  <div class="avg-fits-header"><span class="avg-icon">▶</span> Average Fits{score_span}</div>
  <div class="avg-fits-body collapsed">{inner}
  </div>"""

    has_toe = any(
        r.get("toe_region") is not None
        and not (isinstance(r["toe_region"], float) and pd.isna(r["toe_region"]))
        and float(r["toe_region"]) != 0
        for r in reps_data
    )

    sort_epoch_ms = _epoch_ms(sort_date)
    proc_epoch_ms = _epoch_ms(proc_date)

    return f"""
<div class="card" data-status="{status}" data-run="{run_tag}" data-has-toe="{'1' if has_toe else '0'}" data-name="{cond_name.lower()}" data-sortdate="{sort_epoch_ms}" data-procdate="{proc_epoch_ms}">
  <div class="card-header" style="background:{hdr_color}">
    <span class="toggle-icon">▾</span>
    <span>{cond_name}</span>
    <span class="run-tag">{run_tag}</span>
    <span class="summary">{n_pass}/{n_total} pass &nbsp;|&nbsp; {summary_str}</span>
  </div>
  <div class="card-body">
    {rep_rows_html}
    {comp_row}
    {cv_summary}
    {avg_fits_html}
  </div>
</div>"""


# ── main ──────────────────────────────────────────────────────────────────────

def generate(extra_csv_paths=None, output_path=None, agg_csv_paths=None):
    """
    Regenerate fit_evaluation_log.html from scratch.
    extra_csv_paths: additional reps CSVs to merge (e.g. from test_processing.py).
    agg_csv_paths:   additional agg CSVs for pre/postDiscard CV values.
    output_path:     override output location.
    """
    out = Path(output_path) if output_path else OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)

    # Supervisor flags are git-committed state the page loads via fetch (see JS below) --
    # only create the file if it's missing so a regen never clobbers existing flags.
    flags_path = out.parent / "supervisor_flags.json"
    if not flags_path.exists():
        flags_path.write_text("{}", encoding="utf-8")

    # Namespaced under assets/fit/ -- generate_quality_log.py shares docs/assets/ and manages
    # its own subfolder too; a bare shared "assets/" dir meant either script's rerun wiped the
    # other's images out from under it.
    #
    # NOT wiped wholesale up front: copy_asset() only rewrites a dest whose mtime is stale, so an
    # unchanged source keeps its dest's original mtime -- which lets `git add` skip rehashing it
    # via git's stat cache. Rebuilding this dir from scratch every regen (the old approach) gave
    # every one of the ~2000 asset files a fresh mtime even when content was identical, forcing
    # `git add` to rehash all of them. Stale files (from a condition that disappeared from the
    # data) are pruned below instead, after we know exactly which dest paths this run touched.
    assets_dir = out.parent / "assets" / "fit"
    assets_dir.mkdir(parents=True, exist_ok=True)
    used_assets = set()

    df = load_csvs(extra_csv_paths)
    if df.empty:
        print("[fit log] No data found — skipping HTML generation.")
        return

    cv_map = load_agg_cvs(agg_csv_paths)

    df["_date_sort"] = pd.to_datetime(
        df["date"].str.replace(r"\n", " ", regex=True), errors="coerce"
    )
    # Card order = real campaign date (raw specimen filenames), not the CSV `date` column --
    # see true_condition_date() docstring. Falls back to the CSV date only for a condition
    # whose raw/ folder is missing (e.g. archived away), so it doesn't just vanish from order.
    _csv_max_by_cond = df.groupby("condition")["_date_sort"].max()

    def _cond_sort_key(cond):
        raw_date = true_condition_date(cond)
        if raw_date is not None:
            return raw_date
        csv_date = _csv_max_by_cond.get(cond)
        return csv_date.to_pydatetime() if pd.notna(csv_date) else datetime.datetime.min

    cond_order = sorted(df["condition"].unique(), key=_cond_sort_key, reverse=True)

    cards_html = ""
    for cond in cond_order:
        group = df[df["condition"] == cond]
        seg_imgs, comp_imgs, avg_fit_imgs, deriv_imgs, run_folder = find_plots(cond)
        pre_cv, post_cv = cv_map.get(cond, (None, None))
        cards_html += condition_card(
            cond, group, seg_imgs, comp_imgs, avg_fit_imgs, deriv_imgs, run_folder, assets_dir,
            used_assets, pre_cv=pre_cv, post_cv=post_cv, sort_date=_cond_sort_key(cond),
            proc_date=_csv_max_by_cond.get(cond),
        )

    # prune assets nothing in this run referenced (stale conditions, renamed/removed images)
    for stale in assets_dir.rglob("*"):
        if stale.is_file() and stale.resolve() not in used_assets:
            stale.unlink()
    for stale_dir in sorted(assets_dir.rglob("*"), reverse=True):
        if stale_dir.is_dir() and not any(stale_dir.iterdir()):
            stale_dir.rmdir()

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fit Evaluation Log</title>
<style>{CSS}</style>
</head>
<body>
<h1>Fit Evaluation Log
  <span class="page-nav">
    <a href="index.html">Home</a>
    <a href="fit_evaluation_log.html" class="active">Fit Evaluation</a>
    <a href="quality_evaluation_log.html">Quality Evaluation</a>
  </span>
</h1>
<div class="meta">Generated {generated_at} &nbsp;·&nbsp; {len(cond_order)} condition(s) &nbsp;·&nbsp;
  Pass threshold: {PASS_THRESHOLD}/100 &nbsp;·&nbsp; Click any image to open full size</div>
<div class="legend">
  <div class="legend-item"><div class="dot" style="background:#2e7d32"></div>all pass</div>
  <div class="legend-item"><div class="dot" style="background:#e65100"></div>mixed</div>
  <div class="legend-item"><div class="dot" style="background:#b71c1c"></div>all fail</div>
  <div class="legend-item"><div class="dot" style="background:#78909c"></div>pre-processing failure</div>
  <div class="legend-item" style="color:#cfd8dc;font-size:11px">newest first &nbsp;·&nbsp; to update plots: run <code style="background:#37474f;padding:1px 4px;border-radius:2px">python tests/test_processing.py</code> then <code style="background:#37474f;padding:1px 4px;border-radius:2px">python generate_fit_log.py</code></div>
</div>
<div id="filter-bar">
  <span style="opacity:.7;font-weight:600">Filter:</span>
  <label><input type="checkbox" data-status="pass"    checked> <span class="dot" style="background:#2e7d32"></span> all pass</label>
  <label><input type="checkbox" data-status="mixed"   checked> <span class="dot" style="background:#e65100"></span> mixed</label>
  <label><input type="checkbox" data-status="fail"    checked> <span class="dot" style="background:#b71c1c"></span> all fail</label>
  <label><input type="checkbox" data-status="preproc" checked> <span class="dot" style="background:#78909c"></span> pre-proc failure</label>
  <label><input type="checkbox" id="filter-toe"> toe region only</label>
  <label><input type="checkbox" id="toggle-derivs"> show derivatives</label>
  <input id="search-bar" type="search" placeholder="Search conditions…">
  <select id="run-select"><option value="">All dates</option></select>
  <button id="sort-toggle" title="Off: ordered by real campaign date. On: ordered by when each row was last (re)processed.">Newest Processed First</button>
  <span id="filter-count"></span>
  <button id="export-flags" title="Download supervisor flags as supervisor_flags.json — overwrite the repo copy and commit to sync across devices">Export Flags</button>
  <button id="toggle-all">Collapse All</button>
</div>
{cards_html}
<div id="bd-tooltip"></div>
<script>{JS}</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"[fit log] Written → {out}  ({len(cond_order)} conditions)")


if __name__ == "__main__":
    _test_reps = ROOT / "tests" / "csv_tests" / "test_reps.csv"
    _test_agg  = ROOT / "tests" / "csv_tests" / "test_agg.csv"
    generate(
        extra_csv_paths=[_test_reps] if _test_reps.exists() else [],
        agg_csv_paths=[_test_agg]   if _test_agg.exists()  else [],
    )
