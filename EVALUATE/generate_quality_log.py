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
import hashlib
import re
import shutil
from pathlib import Path

import pandas as pd

FILE_DIR = Path(__file__).parent
ROOT     = FILE_DIR.parent  # project root — this script lives in EVALUATE/


def _default_agg_llm_sources():
    """Every *llm*.csv this project has ever written quality_report data into, across every
    location the convention has lived at over time: root-level leftovers (pre-reorg / stray
    re-adds), data/archive/old_csv/ and data/archive/results-legacy/ (both archived off their
    original root/ and data/results/ flat-file locations), and data/results/**/ (the current
    per-campaign CONTINUE_CAMPAIGN folders). A single "most recent file" pick silently loses
    everything older whenever the convention changes again -- load_quality_rows merges and
    dedupes all of these by name (latest date wins), so nothing gets lost just because a newer,
    smaller CSV happened to be written most recently."""
    candidates = set()
    candidates.update(ROOT.glob("*llm*.csv"))
    candidates.update((ROOT / "data" / "archive" / "old_csv").glob("*llm*.csv"))
    candidates.update((ROOT / "data" / "archive" / "results-legacy").glob("*llm*.csv"))
    candidates.update((ROOT / "data" / "results").glob("**/*llm*.csv"))
    return sorted(candidates)


AGG_LLM  = _default_agg_llm_sources()
RAW_DIR  = ROOT / "data" / "raw"
# Lives under docs/ so GitHub Pages can serve it straight off main (Settings > Pages > docs/).
OUTPUT   = ROOT / "docs" / "quality_evaluation_log.html"

# Extra raw-condition-folder roots to check *before* RAW_DIR (e.g. an isolated test recovery
# run's corrected photos for a condition whose real data/raw/<condition>/ still has stale ones).
# First root that actually contains the condition's folder wins.
EXTRA_RAW_DIRS = []

# compression-test-data/ (pre-reorg name for data/raw/, renamed in commit ea7a43d) has been
# archived to data/archive/compression-test-data-legacy/ -- every condition that was unique to
# it got copied into data/raw/ first, so this fallback now only matters for fake-data/ and any
# stray re-adds from checkouts that predated the rename. Checked after EXTRA_RAW_DIRS/RAW_DIR
# since it's the legacy fallback, not the primary location.
LEGACY_RAW_DIR = ROOT / "data" / "archive" / "compression-test-data-legacy"


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


def copy_asset(path: Path, assets_dir: Path, cond_safe: str) -> str:
    """Copy path into assets_dir/cond_safe/ and return the relative <img src> for it. Linked
    files instead of base64 data URIs -- same fix as generate_fit_log.py's copy_asset, same
    reason: embedding kept this file at 40MB+ and growing every regen."""
    dest_dir = assets_dir / cond_safe
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if not dest.exists() or dest.stat().st_mtime < path.stat().st_mtime:
        shutil.copy2(path, dest)
    return f"assets/quality/{cond_safe}/{path.name}"


# Current QualityChecker.format is "Presence / Vertical Coverage / Uniformity / Defects /
# Summary" bullets (system_prompt.py) -- each rendered as "- **Label:** text" or
# "**Label**: text", dash and colon placement both vary by model run. Matches one bullet's
# label + everything up to the next bullet (or end of string).
_HEURISTIC_RE = re.compile(
    r"-?\s*\*\*(?P<label>[^*]+?)\*\*\s*:?\s*(?P<value>.*?)(?=(?:\n\s*-?\s*\*\*)|\Z)",
    re.DOTALL,
)

# Labels this build's heuristics use. A report using the retired plain "Coverage" bullet
# (pre "Vertical Coverage" wording) came from an older prompt version and is filtered out
# in generate() rather than shown next to current-format reports as if comparable.
CURRENT_HEURISTIC_LABELS = {"presence", "vertical coverage", "uniformity", "defects", "summary"}


def report_labels(text: str) -> list:
    return [m.group("label").strip().rstrip(":").strip() for m in _HEURISTIC_RE.finditer(str(text))]


def report_is_current_format(text: str) -> bool:
    """False if the report uses a retired heuristic label (e.g. bare 'Coverage' instead of
    'Vertical Coverage') -- a stale-prompt report, not comparable to current-format ones."""
    labels = report_labels(text)
    if not labels:
        return False
    return all(label.lower() in CURRENT_HEURISTIC_LABELS for label in labels)


def render_report(text: str) -> str:
    """Render the LLM's labeled-bullet report as a clean label/value layout. Falls back to a
    light markdown→paragraph rendering for anything that doesn't match the bullet shape."""
    import html as _html
    text = _html.escape(str(text))

    rows = [
        (m.group("label").strip().rstrip(":").strip(), re.sub(r"\s+", " ", m.group("value")).strip())
        for m in _HEURISTIC_RE.finditer(text)
    ]
    rows = [(label, value) for label, value in rows if label]
    if rows:
        parts = []
        for label, value in rows:
            value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
            row_class = "quality-summary-row" if label.lower() == "summary" else "quality-heuristic-row"
            parts.append(
                f'<div class="{row_class}"><span class="q-label">{label}</span>'
                f'<span class="q-value">{value}</span></div>'
            )
        return '<div class="quality-heuristics">' + "".join(parts) + "</div>"

    # fallback: light markdown for anything that isn't the bullet-report shape
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
.card-header .date { font-size: 11px; opacity: .7; margin-left: auto; font-weight: normal; }
.card-body.collapsed { display: none; }

.params-line { font-size: 11px; color: #78909c; padding: 8px 14px 0; word-break: break-word; }

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

.quality-heuristics { display: flex; flex-direction: column; gap: 2px; }
.quality-heuristic-row { display: grid; grid-template-columns: 130px 1fr; gap: 10px;
    padding: 6px 0; border-bottom: 1px solid #f0f0f0; }
.quality-heuristic-row .q-label { font-weight: 700; font-size: 10.5px; text-transform: uppercase;
    letter-spacing: .04em; color: #607d8b; }
.quality-heuristic-row .q-value { font-size: 12.5px; line-height: 1.5; }
.quality-summary-row { margin-top: 10px; padding: 9px 11px; background: #eceff1;
    border-left: 3px solid #607d8b; border-radius: 3px; display: flex; flex-direction: column; gap: 2px; }
.quality-summary-row .q-label { font-size: 10px; text-transform: uppercase; letter-spacing: .04em;
    color: #78909c; }
.quality-summary-row .q-value { font-size: 12.5px; font-weight: 600; color: #263238; line-height: 1.5; }

#filter-count { color: #90a4ae; font-style: italic; }
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
  const q = searchBar.value.trim().toLowerCase();
  let visible = 0;
  cards.forEach(c => {
    const show = !q || c.dataset.name.toLowerCase().includes(q);
    c.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.getElementById('filter-count').textContent = `${visible} / ${cards.length} shown`;
}

searchBar.addEventListener('input', applyFilters);
applyFilters();
"""


def _safe_key(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", s)


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


def quality_card(row, assets_dir):
    name = str(row["name"])
    cond_safe = _safe_key(name)
    pretest = row["_pretest"]
    posttest = row["_posttest"]

    if pretest is not None:
        photo_html = f'<img src="{copy_asset(pretest, assets_dir, cond_safe)}" alt="{name} membrane photo">'
        photo_html += f'<div class="cap">{pretest.name} — sent to vision LLM</div>'
        if posttest is not None:
            photo_html += (
                f'<div class="post-photo"><img src="{copy_asset(posttest, assets_dir, cond_safe)}" alt="post-test photo">'
                f'<div class="cap">post-test ({posttest.name})</div></div>'
            )
    else:
        photo_html = '<div class="no-photo">No photo found in data/raw/' + name + '/</div>'

    report_html = render_report(row["quality_report"])
    params = str(row.get("formatted_parameters", "") or "")
    date = str(row.get("date", "")).replace("\n", " ")

    return f"""
<div class="card" data-name="{name}">
  <div class="card-header">
    <span class="toggle-icon">▼</span>
    <span>{name}</span>
    <span class="date">{date}</span>
  </div>
  <div class="card-body">
    <div class="params-line">{params}</div>
    <div class="quality-row">
      <div class="photo-col">{photo_html}</div>
      <div class="report-col">{report_html}</div>
    </div>
  </div>
</div>"""


def generate(output_path=None, extra_csv_paths=None):
    out = Path(output_path) if output_path else OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)

    # Rebuilt from scratch every call -- clear stale per-condition asset folders first so a
    # condition that disappears (or gets dropped as an image failure below) doesn't leave
    # orphan images behind.
    # Namespaced under assets/quality/ -- generate_fit_log.py shares docs/assets/ and rmtree's
    # its own subfolder on every regen too; a bare shared "assets/" dir meant either script's
    # rerun wiped the other's images out from under it.
    assets_dir = out.parent / "assets" / "quality"
    if assets_dir.exists():
        shutil.rmtree(assets_dir)

    df = load_quality_rows(extra_csv_paths)
    if df.empty:
        print("[quality log] No quality_report data found — skipping HTML generation.")
        return

    resolved = _resolve_photos(df["name"].astype(str).tolist())
    stale_hashes = _find_stale_hashes(resolved)

    df["_cond_dir"], df["_pretest"], df["_posttest"], df["_hash"] = zip(
        *(resolved[str(n)] for n in df["name"])
    )

    # Same photo (by content hash) reused across 2+ conditions means a stale/duplicate image
    # got attached instead of that condition's real membrane shot -- the report generated from
    # it describes the wrong photo, so it's not salvageable data, just drop it rather than
    # displaying a report next to a banner saying not to trust it.
    is_stale = df["_hash"].isin(stale_hashes)
    n_stale = int(is_stale.sum())

    # Reports from a retired prompt version (e.g. bare "Coverage" instead of "Vertical
    # Coverage") aren't comparable to current-format ones -- drop them rather than showing
    # old and new heuristic wording side by side as if equivalent.
    is_old_format = ~df["quality_report"].apply(report_is_current_format)
    n_old_format = int((is_old_format & ~is_stale).sum())

    n_dropped = n_stale + n_old_format
    df = df[~is_stale & ~is_old_format].copy()

    cards_html = "".join(quality_card(row, assets_dir) for _, row in df.iterrows())

    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    dropped_bits = []
    if n_stale:
        dropped_bits.append(f"{n_stale} duplicate/stale photo")
    if n_old_format:
        dropped_bits.append(f"{n_old_format} outdated prompt format")
    dropped_note = (
        f" &nbsp;·&nbsp; <span style=\"color:#ffab91\">{n_dropped} dropped "
        f"({', '.join(dropped_bits)})</span>" if dropped_bits else ""
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
  &nbsp;·&nbsp; to update: run <code style="background:#263238;padding:1px 4px;border-radius:2px">python EVALUATE/generate_quality_log.py</code>{dropped_note}</div>
<div id="filter-bar">
  <span style="opacity:.7;font-weight:600">Filter:</span>
  <input id="search-bar" type="search" placeholder="Search conditions…">
  <span id="filter-count"></span>
  <button id="toggle-all">Collapse All</button>
</div>
{cards_html}
<script>{JS}</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"[quality log] Written → {out}  ({len(df)} conditions, {n_stale} stale-photo + "
          f"{n_old_format} outdated-format dropped)")


if __name__ == "__main__":
    generate()
