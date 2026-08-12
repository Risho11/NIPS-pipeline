#!/usr/bin/env python3
"""
generate_quality_log.py — build quality_evaluation_log.html

Sibling to generate_fit_log.py (mechanical fit quality) but for the image_processing
branch's vision-LLM quality check: reads results_agg_llm.csv's "quality_report" column
(the vision LLM's qualitative assessment, written by membrane_quality_llm.py via
llm_context.generate_quality_report_text), finds the membrane photo it judged in
data/raw/<condition>/ (same earliest-timestamp selection membrane_imaging._find_pretest_image
uses), and lays photo + LLM report out side by side per condition.

Run standalone:
    python EVALUATE/generate_quality_log.py
"""
import base64
import hashlib
import re
from pathlib import Path

import pandas as pd

FILE_DIR = Path(__file__).parent
ROOT     = FILE_DIR.parent  # project root — this script lives in EVALUATE/


def _default_agg_llm_sources():
    """Every *llm*.csv this project has ever written quality_report data into, across every
    location the convention has lived at over time: root-level leftovers (pre-reorg / stray
    re-adds), old_csv/ (the historical archive), and data/results/**/ (both the old flat file
    and per-campaign CONTINUE_CAMPAIGN folders). A single "most recent file" pick silently loses
    everything older whenever the convention changes again -- load_quality_rows merges and
    dedupes all of these by name (latest date wins), so nothing gets lost just because a newer,
    smaller CSV happened to be written most recently."""
    candidates = set()
    candidates.update(ROOT.glob("*llm*.csv"))
    candidates.update((ROOT / "old_csv").glob("*llm*.csv"))
    candidates.update((ROOT / "data" / "results").glob("**/*llm*.csv"))
    return sorted(candidates)


AGG_LLM  = _default_agg_llm_sources()
RAW_DIR  = ROOT / "data" / "raw"
OUTPUT   = FILE_DIR / "quality_evaluation_log.html"

# Extra raw-condition-folder roots to check *before* RAW_DIR (e.g. an isolated test recovery
# run's corrected photos for a condition whose real data/raw/<condition>/ still has stale ones).
# First root that actually contains the condition's folder wins.
EXTRA_RAW_DIRS = []

# compression-test-data/ is the pre-reorg name for data/raw/ (renamed in commit ea7a43d) --
# older conditions (and some stray re-adds from checkouts that predated the rename) still only
# exist there, never got copied into data/raw/. Checked after EXTRA_RAW_DIRS/RAW_DIR since it's
# the legacy fallback, not the primary location.
LEGACY_RAW_DIR = ROOT / "compression-test-data"


def _pretest_image(condition_dir: Path):
    """Mirrors membrane_imaging._find_pretest_image: earliest-timestamped jpg in the
    folder is the one actually sent to the vision LLM (move_and_rename drops pre- and
    post-test photos into the same folder)."""
    jpgs = sorted(condition_dir.glob("*.jpg")) + sorted(condition_dir.glob("*.jpeg"))
    if not jpgs:
        return None, None

    def _timestamp(path):
        m = re.match(r"([\d.]+)", path.stem)
        return float(m.group(1)) if m else path.stat().st_ctime

    jpgs = sorted(jpgs, key=_timestamp)
    pretest = jpgs[0]
    posttest = jpgs[-1] if len(jpgs) > 1 else None
    return pretest, posttest


def img_to_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    ext = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return f"data:image/{mime};base64,{b64}"


def render_report(text: str) -> str:
    """Light markdown→HTML for the LLM's report text (### headers, **bold**, paragraphs).
    Not a general markdown parser — just enough for this model's consistent output shape."""
    import html as _html
    text = _html.escape(str(text))
    lines = text.split("\n")
    out, para = [], []

    def flush():
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()

    for line in lines:
        line = line.strip()
        if not line:
            flush()
            continue
        m = re.match(r"^(#{2,4})\s+(.*)", line)
        if m:
            flush()
            level = min(len(m.group(1)) + 2, 6)  # ## -> h4, ### -> h5, cap at h6
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        para.append(line)
    flush()
    return "\n".join(out)


def load_quality_rows(extra_csv_paths=None):
    """extra_csv_paths: additional {name, date, quality_report, ...}-shaped CSVs to merge in
    (e.g. a one-off recovery run's isolated test CSV), without touching AGG_LLM itself."""
    frames = []
    for p in list(AGG_LLM) + list(extra_csv_paths or []):
        p = Path(p)
        if p.exists() and p.stat().st_size > 0:
            frames.append(pd.read_csv(p))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "quality_report" not in df.columns:
        return pd.DataFrame()
    df = df[df["quality_report"].notna()].copy()
    if df.empty:
        return df
    df["_date_sort"] = pd.to_datetime(
        df["date"].astype(str).str.replace(r"\n", " ", regex=True), errors="coerce"
    )
    df = df.sort_values("_date_sort", ascending=False).drop_duplicates(subset=["name"], keep="first")
    return df


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 13px;
       background: #ececec; color: #222; }
h1   { font-size: 1.35rem; padding: 14px 22px; background: #263238; color: #fff;
       display: flex; align-items: baseline; gap: 16px; }
.page-nav { display: flex; gap: 8px; font-size: 12px; font-weight: normal; }
.page-nav a { color: #90a4ae; text-decoration: none; padding: 3px 9px; border-radius: 3px; }
.page-nav a:hover { background: #37474f; color: #fff; }
.page-nav a.active { background: #455a64; color: #fff; }
.meta { font-size: 11px; color: #90a4ae; padding: 3px 22px 10px; background: #263238; }
#filter-bar { display: flex; gap: 12px; align-items: center; padding: 8px 22px;
              background: #37474f; font-size: 12px; }
#filter-bar input[type=search] { padding: 4px 8px; border-radius: 3px; border: 1px solid #78909c;
              font-size: 12px; min-width: 220px; }
#toggle-all { margin-left: auto; padding: 4px 10px; font-size: 11px; cursor: pointer;
    background: #546e7a; color: #eceff1; border: 1px solid #78909c; border-radius: 3px; }
#toggle-all:hover { background: #607d8b; }

.card { margin: 14px 22px; border-radius: 6px; overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,.14); background: #fff; }
.card-header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
    padding: 9px 14px; background: #455a64; color: #fff; font-weight: 600;
    font-size: 0.97rem; cursor: pointer; user-select: none; }
.card-header .toggle-icon { font-size: 12px; opacity: .8; transition: transform .18s; flex-shrink: 0; }
.card-header.collapsed .toggle-icon { transform: rotate(-90deg); }
.card-header .params { font-size: 11px; opacity: .85; font-weight: normal; }
.card-header .date { font-size: 11px; opacity: .7; margin-left: auto; font-weight: normal; }
.card-body.collapsed { display: none; }

.quality-row { display: grid; grid-template-columns: minmax(240px, 38%) 1fr; }
@media (max-width: 800px) { .quality-row { grid-template-columns: 1fr; } }

.photo-col { padding: 14px; display: flex; flex-direction: column; gap: 8px;
             border-right: 1px solid #e8e8e8; background: #fafafa; }
.photo-col img { width: 100%; max-height: 420px; object-fit: contain; background: #111;
    border: 1px solid #ddd; border-radius: 4px; cursor: zoom-in; }
.photo-col .cap { font-size: 10.5px; color: #78909c; text-align: center; }
.photo-col .post-photo { display: flex; align-items: center; gap: 8px; }
.photo-col .post-photo img { max-height: 90px; width: auto; max-width: 120px; flex-shrink: 0; }
.photo-col .no-photo { color: #b71c1c; font-size: 12px; padding: 30px 10px; text-align: center; }

.report-col { padding: 14px 18px; overflow-x: auto; }
.report-col h4, .report-col h5 { margin: 10px 0 4px; color: #37474f; }
.report-col h4:first-child, .report-col h5:first-child { margin-top: 0; }
.report-col p { margin: 4px 0 8px; line-height: 1.5; }
.report-col strong { color: #263238; }

.card-stale .card-header { background: #b71c1c; }
.stale-tag { font-size: 10px; font-weight: 700; background: #ffab91; color: #3e0000;
    padding: 2px 6px; border-radius: 3px; letter-spacing: .03em; }
.stale-banner { background: #ffebee; color: #b71c1c; border: 1px solid #ef9a9a;
    border-radius: 4px; padding: 8px 12px; margin-bottom: 10px; font-size: 12px;
    font-weight: 600; line-height: 1.4; }

#filter-bar label { display: flex; align-items: center; gap: 5px; cursor: pointer; }
#filter-bar input[type=checkbox] { accent-color: #90a4ae; cursor: pointer; }
#filter-count { color: #90a4ae; font-style: italic; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; display: inline-block; }
"""

JS = """
document.querySelectorAll('.photo-col img').forEach(img => {
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
document.getElementById('toggle-all').addEventListener('click', () => {
  const allCollapsed = [...document.querySelectorAll('.card-header')].every(h => h.classList.contains('collapsed'));
  document.querySelectorAll('.card-header').forEach(h => {
    h.classList.toggle('collapsed', !allCollapsed);
    h.nextElementSibling.classList.toggle('collapsed', !allCollapsed);
  });
  syncToggleAllLabel();
});
const cards = [...document.querySelectorAll('.card')];
const searchBar = document.getElementById('search-bar');

function applyFilters() {
  const activeStatus = new Set(
    [...document.querySelectorAll('#filter-bar input[data-status]:checked')].map(i => i.dataset.status)
  );
  const q = searchBar.value.trim().toLowerCase();
  let visible = 0;
  cards.forEach(c => {
    const statusMatch = activeStatus.has(c.dataset.status);
    const searchMatch = !q || c.dataset.name.toLowerCase().includes(q);
    const show = statusMatch && searchMatch;
    c.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.getElementById('filter-count').textContent = `${visible} / ${cards.length} shown`;
}

document.querySelectorAll('#filter-bar input[data-status]').forEach(cb => {
  cb.addEventListener('change', applyFilters);
});
searchBar.addEventListener('input', applyFilters);
applyFilters();
"""


def _resolve_condition_dir(name):
    for root in list(EXTRA_RAW_DIRS) + [RAW_DIR, LEGACY_RAW_DIR]:
        cand = Path(root) / name
        if cand.is_dir():
            return cand
    return None


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _resolve_photos(names):
    """name -> (cond_dir, pretest, posttest, pretest_hash_or_None), resolved once and shared
    between the duplicate-photo scan and the actual card rendering."""
    resolved = {}
    for name in names:
        cond_dir = _resolve_condition_dir(name)
        pretest, posttest = (None, None)
        if cond_dir is not None:
            pretest, posttest = _pretest_image(cond_dir)
        h = _file_hash(pretest) if pretest is not None else None
        resolved[name] = (cond_dir, pretest, posttest, h)
    return resolved


def _find_stale_hashes(resolved):
    """Same photo (by content hash) reused across 2+ different conditions almost certainly
    means a stale/duplicate photo got attached instead of that condition's real membrane shot
    (see take_snapshot()'s write-path bug in run_loop.py -- this is the general form of that
    same failure class, so it catches recurrences automatically instead of hardcoding the one
    known bad file)."""
    counts = {}
    for _cond, _dir, _pre, _post, h in ((n, *v) for n, v in resolved.items()):
        if h is not None:
            counts[h] = counts.get(h, 0) + 1
    return {h for h, c in counts.items() if c > 1}


def quality_card(row, is_stale=False):
    name = str(row["name"])
    cond_dir = row["_cond_dir"]
    pretest = row["_pretest"]
    posttest = row["_posttest"]

    if pretest is not None:
        photo_html = f'<img src="{img_to_data_uri(pretest)}" alt="{name} membrane photo">'
        photo_html += f'<div class="cap">{pretest.name} — sent to vision LLM</div>'
        if posttest is not None:
            photo_html += (
                f'<div class="post-photo"><img src="{img_to_data_uri(posttest)}" alt="post-test photo">'
                f'<div class="cap">post-test ({posttest.name})</div></div>'
            )
    else:
        photo_html = '<div class="no-photo">No photo found in data/raw/' + name + '/</div>'

    if is_stale:
        report_html = (
            '<div class="stale-banner">⚠ IMAGE FAILURE — this photo is identical to another '
            "condition's, almost certainly a stale/duplicate image rather than this condition's "
            "real membrane shot. The report below was generated from that photo and should not "
            "be trusted.</div>"
        ) + render_report(row["quality_report"])
    else:
        report_html = render_report(row["quality_report"])
    params = str(row.get("formatted_parameters", "") or "")
    date = str(row.get("date", "")).replace("\n", " ")

    status = "stale" if is_stale else "ok"
    return f"""
<div class="card{' card-stale' if is_stale else ''}" data-name="{name}" data-status="{status}">
  <div class="card-header">
    <span class="toggle-icon">▼</span>
    <span>{name}</span>
    {'<span class="stale-tag">IMAGE FAILURE</span>' if is_stale else ''}
    <span class="params">{params}</span>
    <span class="date">{date}</span>
  </div>
  <div class="card-body">
    <div class="quality-row">
      <div class="photo-col">{photo_html}</div>
      <div class="report-col">{report_html}</div>
    </div>
  </div>
</div>"""


def generate(output_path=None, extra_csv_paths=None):
    out = Path(output_path) if output_path else OUTPUT
    df = load_quality_rows(extra_csv_paths)
    if df.empty:
        print("[quality log] No quality_report data found — skipping HTML generation.")
        return

    resolved = _resolve_photos(df["name"].astype(str).tolist())
    stale_hashes = _find_stale_hashes(resolved)

    df["_cond_dir"], df["_pretest"], df["_posttest"], df["_hash"] = zip(
        *(resolved[str(n)] for n in df["name"])
    )
    df["_is_stale"] = df["_hash"].apply(lambda h: h in stale_hashes)

    n_stale = int(df["_is_stale"].sum())
    cards_html = "".join(quality_card(row, is_stale=row["_is_stale"]) for _, row in df.iterrows())

    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    stale_note = (
        f" &nbsp;·&nbsp; <span style=\"color:#ffab91\">{n_stale} flagged as image failure "
        f"(duplicate/stale photo)</span>" if n_stale else ""
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quality Evaluation Log</title>
<style>{CSS}</style>
</head>
<body>
<h1>Quality Evaluation Log
  <span class="page-nav">
    <a href="fit_evaluation_log.html">Fit Evaluation</a>
    <a href="quality_evaluation_log.html" class="active">Quality Evaluation</a>
  </span>
</h1>
<div class="meta">Generated {generated_at} &nbsp;·&nbsp; {len(df)} condition(s) with a vision-LLM quality report
  &nbsp;·&nbsp; Click a photo to open full size &nbsp;·&nbsp; newest first
  &nbsp;·&nbsp; to update: run <code style="background:#263238;padding:1px 4px;border-radius:2px">python EVALUATE/generate_quality_log.py</code>{stale_note}</div>
<div id="filter-bar">
  <span style="opacity:.7;font-weight:600">Filter:</span>
  <label><input type="checkbox" data-status="ok" checked> <span class="dot" style="background:#455a64"></span> OK</label>
  <label><input type="checkbox" data-status="stale" checked> <span class="dot" style="background:#b71c1c"></span> image failure</label>
  <input id="search-bar" type="search" placeholder="Search conditions…">
  <span id="filter-count"></span>
  <button id="toggle-all">Collapse All</button>
</div>
{cards_html}
<script>{JS}</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"[quality log] Written → {out}  ({len(df)} conditions, {n_stale} flagged as image failure)")


if __name__ == "__main__":
    generate()
