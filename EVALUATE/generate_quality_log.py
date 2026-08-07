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
import re
from pathlib import Path

import pandas as pd

FILE_DIR = Path(__file__).parent
ROOT     = FILE_DIR.parent  # project root — this script lives in EVALUATE/
AGG_LLM  = ROOT / "data" / "results" / "results_agg_llm.csv"
RAW_DIR  = ROOT / "data" / "raw"
OUTPUT   = FILE_DIR / "quality_evaluation_log.html"


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


def load_quality_rows():
    if not AGG_LLM.exists() or AGG_LLM.stat().st_size == 0:
        return pd.DataFrame()
    df = pd.read_csv(AGG_LLM)
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
const searchBar = document.getElementById('search-bar');
searchBar.addEventListener('input', () => {
  const q = searchBar.value.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {
    c.style.display = c.dataset.name.toLowerCase().includes(q) ? '' : 'none';
  });
});
"""


def quality_card(row):
    name = str(row["name"])
    cond_dir = RAW_DIR / name
    pretest, posttest = (None, None)
    if cond_dir.is_dir():
        pretest, posttest = _pretest_image(cond_dir)

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

    report_html = render_report(row["quality_report"])
    params = str(row.get("formatted_parameters", "") or "")
    date = str(row.get("date", "")).replace("\n", " ")

    return f"""
<div class="card" data-name="{name}">
  <div class="card-header">
    <span class="toggle-icon">▼</span>
    <span>{name}</span>
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


def generate(output_path=None):
    out = Path(output_path) if output_path else OUTPUT
    df = load_quality_rows()
    if df.empty:
        print("[quality log] No quality_report data found — skipping HTML generation.")
        return

    cards_html = "".join(quality_card(row) for _, row in df.iterrows())

    from datetime import datetime
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

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
  &nbsp;·&nbsp; to update: run <code style="background:#263238;padding:1px 4px;border-radius:2px">python EVALUATE/generate_quality_log.py</code></div>
<div id="filter-bar">
  <input id="search-bar" type="search" placeholder="Search conditions…">
  <button id="toggle-all">Collapse All</button>
</div>
{cards_html}
<script>{JS}</script>
</body>
</html>"""

    out.write_text(html, encoding="utf-8")
    print(f"[quality log] Written → {out}  ({len(df)} conditions)")


if __name__ == "__main__":
    generate()
