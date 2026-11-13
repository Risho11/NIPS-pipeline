"""Refresh only validation outputs using notebook settings, without warm-start writes.

uv run --with ipython python EVALUATE/refresh_pareto_validation.py
"""

import argparse
import ast
import base64
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from pareto_candidate_selection import assess_candidates, choose_candidates

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = '''### Reproducibility-aware selection for further validation

Five **distinct recorded recipes** balance repeat evidence, promising modulus/pore fraction, and coverage of their tradeoff. Candidates start with this notebook's unchanged quality/date/chemistry filters. Historical repeats are then searched across all campaigns, including poor outcomes excluded from these plots. Exact recorded process settings must match; known chemistry conflicts never match. Missing chemistry permits matching only within the same named recipe family. Raw `params.json` takes precedence. Conditions with missing process settings cannot establish an exact match. Stock age and ambient conditions may differ.

Separate raw sample records count as historical sample evidence, not compression locations. A usable pair requires finite, positive modulus and pore fraction within [0, 1]. Missing/invalid pairs count against the usable fraction; finite poor outcomes remain in the statistics. Each recipe is summarized using its paired-sample medians, lower quartiles and between-sample CVs. These are measured descriptive statistics; medians can combine different samples and are not an invented experimental observation. The displayed source sample is an actual eligible measurement nearest its recipe's median responses, rather than its best run.

**Selection rule:** recipes with <75% usable paired coverage or observed between-sample CV >50% for either response are retained in the assessment but excluded from selection. Up to three anchors have at least three usable paired samples and CV <=25% for both responses: highest median modulus, highest median pore fraction among remaining recipes, then highest balanced utility. These are prioritization rules, not validated reproducibility tolerances. One slot favors promising conditions with only one or two usable samples. Remaining slots balance utility and distance from already selected recipe medians. Labels V1–V5 follow increasing historical median pore fraction.

**Utility:** median and lower-quartile responses are normalized by each objective's candidate-median range. Performance = half the sum of normalized medians plus half the sum of lower-quartile scores clipped to [0,1]. Multiply by sample evidence (1 for >=3 usable pairs, 0.85 for two, 0.65 for one), paired fraction, and 1/(1 + largest between-sample CV as a fraction). Unknown CV receives a scoring penalty of 0.50, not a substituted measurement. Coverage slots multiply utility by (1 + distance to the nearest selected median in normalized objective space). The heuristic expresses an explicit tradeoff, not an optimized or statistically certified experimental design.

The left panel shows **actual source measurements** against the original single-sample Pareto front; selected recipes need not lie on that front. The right panel shows typical historical performance and usable paired-sample counts. Reasons, measured medians, CVs and historical counts appear in the table. Historical chemistry labels retain the notebook's provenance limitations.

Plan: **three independently synthesized samples per selected condition, two compression tests per sample at the bottom two locations**. No hardware is operated here. The separate Mini PC runner is implemented in src/pipeline/run_pareto_validation.py; see docs/PARETO_VALIDATION.md. It uses coupon tests 2 and 4 on the casting-start side, with two matched blank-coupon zero tests per sample.
'''


def validation_source(chemistry, output):
    return f'''from pareto_validation import select_validation_points, plot_validation_points

VALIDATION_POINT_COUNT = 5
validation_points, validation_front, validation_conditions = select_validation_points(
    campaign_detailed, count=VALIDATION_POINT_COUNT
)
figure_validation, axes_validation = plot_validation_points(
    validation_points, validation_front, validation_conditions, {chemistry!r}
)
plt.show()
validation_columns = ['validation_id', 'selection_reason', 'campaign', 'condition', 'iteration',
                      'historical_samples', 'paired_samples', 'paired_fraction', 'repeat_supported',
                      'chemistry_recorded', 'Elastic Modulus median', 'Pore Fraction median',
                      'Elastic Modulus between CV %', 'Pore Fraction between CV %',
                      'Elastic Modulus Mean', 'Elastic Modulus SD',
                      'Pore Fraction Mean', 'Pore Fraction SD']
validation_columns += [column for column in PARETO_PARAMETERS if column not in validation_columns]
validation_columns += ['sample_repeats', 'compression_tests_per_sample']
display(validation_conditions.reindex(columns=validation_columns))
print(f'{{len(validation_conditions)}} conditions; {{3 * len(validation_conditions)}} independent samples; '
      f'{{6 * len(validation_conditions)}} compression tests total.')
if SAVE_OUTPUTS:
    validation_output = repo_root / 'EVALUATE' / {output!r}
    validation_output.mkdir(parents=True, exist_ok=True)
    figure_validation.savefig(validation_output / 'pareto_validation_selection.png',
                              dpi=180, bbox_inches='tight')
    validation_conditions.to_csv(validation_output / 'pareto_validation_conditions.csv', index=False)
    validation_conditions.attrs['candidate_assessment'].to_csv(
        validation_output / 'pareto_validation_candidate_assessment.csv', index=False)
'''


def refresh(preview=False):
    for name in ['campaign_trends.ipynb', 'primospire_nmp_campaign_trends.ipynb']:
        path = ROOT / 'EVALUATE' / name
        notebook = json.loads(path.read_text(encoding='utf-8'))
        namespace = {'display': lambda *args: None}
        # These setup/filter cells only read measured data. Deliberately skip the
        # trend-plot cell, which also exports warm-start files.
        for index in [1, 3, 5, 6]:
            exec(compile(''.join(notebook['cells'][index]['source']), f'{name}:{index}', 'exec'), namespace)
        detailed = namespace['campaign'].sort_values('sample_time').reset_index(drop=True).copy()
        detailed['iteration'] = detailed.index + 1
        namespace['campaign_detailed'] = detailed
        candidates = assess_candidates(detailed)
        chosen, candidates = choose_candidates(candidates)
        columns = ['condition', 'historical_samples', 'paired_samples', 'repeat_supported',
                   'Elastic Modulus median', 'Pore Fraction median',
                   'Elastic Modulus between CV %', 'Pore Fraction between CV %', 'selection_utility']
        print('\n', name, '\nSELECTED\n', chosen[columns + ['selection_reason']].to_string(index=False))
        print('\nLEADING CANDIDATES\n', candidates.sort_values('selection_utility', ascending=False)[columns].head(15).to_string(index=False))
        if preview:
            continue
        chemistry = 'PSf / PolarClean' if name == 'campaign_trends.ipynb' else 'Primospire / NMP'
        output = 'campaign_trends_output' if name == 'campaign_trends.ipynb' else 'primospire_nmp_campaign_trends_output'
        section = next(c for c in notebook['cells'] if c['cell_type'] == 'markdown' and (
            ''.join(c['source']).startswith('### Proposed validation conditions') or
            ''.join(c['source']).startswith('### Reproducibility-aware selection')))
        section['source'] = DESCRIPTION.splitlines(keepends=True)
        cell = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('PARETO_X ='))
        for node in ast.parse(''.join(cell['source'])).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PARETO_PARAMETERS' for t in node.targets):
                exec(compile(ast.Module(body=[node], type_ignores=[]), name, 'exec'), namespace)
        cell = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('from pareto_validation import'))
        cell['source'] = validation_source(chemistry, output).splitlines(keepends=True)
        tables = []
        namespace['display'] = tables.append
        exec(compile(''.join(cell['source']), name, 'exec'), namespace)
        chosen = namespace['validation_conditions']
        assert len(chosen) == 5 and chosen['condition'].is_unique
        output_dir = ROOT / 'docs' / 'pareto_validation'
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = 'psf' if name == 'campaign_trends.ipynb' else 'primospire'
        # Preserve full precision separately from the notebook HTML display.
        chosen.to_csv(output_dir / f'{prefix}_selected_conditions.csv', index=False)
        chosen.attrs['candidate_assessment'].to_csv(output_dir / f'{prefix}_candidate_assessment.csv', index=False)
        png = io.BytesIO()
        namespace['figure_validation'].savefig(png, format='png', dpi=120, bbox_inches='tight')
        (output_dir / f'{prefix}_selection.png').write_bytes(png.getvalue())
        cell['outputs'] = [
            dict(output_type='display_data', metadata={}, data={'image/png': base64.b64encode(png.getvalue()).decode('ascii')}),
            dict(output_type='display_data', metadata={}, data={'text/html': tables[0].to_html(index=False), 'text/plain': tables[0].to_string(index=False)}),
            dict(output_type='stream', name='stdout', text=f'{len(chosen)} conditions; {3*len(chosen)} independent samples; {6*len(chosen)} compression tests total.\n'),
        ]
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        plt.close('all')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    refresh(parser.parse_args().preview)
