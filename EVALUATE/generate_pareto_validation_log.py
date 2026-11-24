"""Build the fit log from the V1–V5 records used for the frozen validation plan.

Run: uv run python EVALUATE/generate_pareto_validation_log.py
No notebook cells, warm-start exports, or hardware commands are executed.
"""

import html
import json
import re
from pathlib import Path
import shutil

import generate_fit_log as fit
from export_pareto_protocol import read_frozen_conditions

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs' / 'pareto_validation' / 'index.html'


def read_selections():
    selections = []
    for slug, chemistry in [('psf', 'PSf / PolarClean'), ('primospire', 'Primospire / NMP')]:
        selections.extend(dict(row, chemistry=chemistry) for row in read_frozen_conditions(slug, root=ROOT))
    conditions = [row['condition'] for row in selections]
    if not conditions or len(set(conditions)) != len(conditions):
        raise ValueError('Expected nonempty, distinct selected conditions.')
    return selections


def generate():
    selections = read_selections()
    selected = {row['condition'] for row in selections}
    available = set(fit.load_csvs()['condition'])
    if selected - available:
        raise ValueError(f'Missing fit records: {sorted(selected - available)}')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # Seed published plot identities so clean checkouts can reuse reviewed assets.
    source_index = ROOT / 'docs' / 'fit_evaluation_log_plots.json'
    if source_index.exists():
        index = json.loads(source_index.read_text(encoding='utf-8'))
        index = {key: value for key, value in index.items() if key in selected}
        for condition, entry in index.items():
            source = ROOT / 'docs' / 'assets' / 'fit' / fit._safe_key(condition)
            target = OUTPUT.parent / 'assets' / 'fit' / fit._safe_key(condition)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
        OUTPUT.with_name('index_plots.json').write_text(json.dumps(index), encoding='utf-8')
    fit.generate(output_path=OUTPUT, condition_filter=selected)
    document = OUTPUT.read_text(encoding='utf-8')
    rendered = re.findall(r'<div class="card"[^>]*data-name="([^"]+)"', document)
    if len(rendered) != len(selected) or set(rendered) != {name.lower() for name in selected}:
        raise ValueError('Rendered fit cards do not match the frozen validation selections.')
    document = document.replace('Fit Evaluation Log', 'Pareto Validation Fit Log')
    document = document.replace('href="index.html"', 'href="../index.html"')
    document = document.replace('href="fit_evaluation_log.html"', 'href="../fit_evaluation_log.html"')
    document = document.replace('href="quality_evaluation_log.html"', 'href="../quality_evaluation_log.html"')
    columns = [('chemistry', 'Chemistry'), ('validation_id', 'Point'),
               ('selection_reason', 'Reason for selection'),
               ('condition', 'Selected source condition'), ('campaign', 'Campaign'),
               ('paired_samples', 'Usable historical samples'),
               ('Elastic Modulus median', 'Historical median modulus (bar)'),
               ('Pore Fraction median', 'Historical median pore fraction'),
               ('Elastic Modulus between CV %', 'Between-sample modulus CV (%)'),
               ('Pore Fraction between CV %', 'Between-sample pore-fraction CV (%)'),
               ('Elastic Modulus Mean', 'Source sample modulus (bar)'),
               ('Pore Fraction Mean', 'Source sample pore fraction')]
    summary = '<section style="padding:20px;overflow-x:auto"><h2>Selected validation points</h2>'
    summary += ('<p>The original validation plan specifies three independent synthesis repeats '
                'per condition; two compression tests at the bottom two locations per sample '
                '(coupon tests 2 and 4, the casting-start side), plus two matched blank-coupon zero tests. '
                'The fits below are historical measurements, not new validation results. '
                'Pore fraction is a compression-fit estimate. Source conditions and nomination-time '
                'statistics are recorded in the <a href="psf_selected_conditions.csv">PSf</a> and '
                '<a href="primospire_selected_conditions.csv">Primospire</a> selection tables.</p>')
    summary += ('<p>V1–V5 follow the archived selection for each chemistry. '
                'Each chemistry includes three repeat-supported anchors, one promising '
                'limited-repeat candidate, and one candidate adding tradeoff coverage. Anchor flags '
                'require at least three usable paired samples and CV ≤25% for both responses; '
                'these are prioritization criteria, not proof of reproducibility. Recipes with '
                '&lt;75% usable pairs or observed CV &gt;50% are excluded from selection. '
                'Poor historical repeats are included when calculating variability. Source samples '
                'are actual eligible observations nearest their recipe medians. The notebooks '
                'document the utility and coverage heuristic.</p>')
    summary += ('<p>Protocol: <a href="../../protocols/pareto_validation_plan.json">frozen experiment plan</a> '
                'and <a href="../PARETO_VALIDATION.md">Mini PC run instructions</a>. '
                'The complete plan contains 30 new samples, 60 membrane tests and 60 zero tests.</p>')
    summary += '<table><thead><tr>' + ''.join(f'<th>{label}</th>' for _, label in columns) + '</tr></thead><tbody>'
    for row in selections:
        summary += '<tr>' + ''.join(f'<td>{html.escape(row[key])}</td>' for key, _ in columns) + '</tr>'
    summary += '</tbody></table></section>'
    from pareto_reproduction import audit
    summary += audit(selections, OUTPUT.parent)
    document = document.replace('<div class="legend">', summary + '\n<div class="legend">', 1)
    OUTPUT.write_text(document, encoding='utf-8')
    print(f'Selection-only HTML: {OUTPUT} ({len(selected)} conditions)')


if __name__ == '__main__':
    generate()
