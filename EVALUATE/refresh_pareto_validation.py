"""Refresh the retrospective notebook rankings and their screened analysis exports.

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

from notebook_selection import load_notebook_selection

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = '''### Retrospective ranking of screened films

This retrospective ranking proposes up to five recipes from the screened films. Labels C1–C5 identify candidates in this analysis. The historical validation experiments retain their original V identifiers. Only screened films with matching recorded process settings contribute to repeat counts, medians, lower quartiles and between-film CVs. The representative film is the measured pair closest to the two recipe medians.

Every retained film has a paired objective measurement. The paired fraction in this table is therefore conditional on passing screening and equals one. It cannot estimate how often an attempted casting produced usable data. The between-film CV describes dispersion among retained repeats. With one film the CV is unavailable.

The ranking excludes recipes with an observed CV above 50% for either objective. Up to three anchors have at least three measured films and CV at most 25% for both responses. The anchors prioritize median modulus, then median pore fraction, then joint utility. One slot favors a promising recipe with one or two films. Remaining slots balance utility and distance from the selected recipes. These cutoffs are prioritization choices.

For utility, the median and lower quartile of each objective are scaled by the range of candidate medians. The score weights the median and clipped lower-quartile sums equally, then discounts for small sample counts and the largest between-film CV. An unknown CV receives a scoring penalty of 0.50. The left panel shows the actual representative films against the screened single-film Pareto front. The right panel shows recipe medians and retained film counts.
'''


def validation_source(chemistry):
    return f'''from pareto_validation import select_validation_points, plot_validation_points

CANDIDATE_COUNT = 5
candidate_points, candidate_front, screened_candidates = select_validation_points(
    campaign_detailed, count=CANDIDATE_COUNT, history=campaign_detailed, id_prefix='C'
)
figure_screened_candidates, axes_screened_candidates = plot_validation_points(
    candidate_points, candidate_front, screened_candidates, {chemistry!r}
)
plt.show()
candidate_columns = ['validation_id', 'selection_reason', 'campaign', 'condition', 'iteration',
                      'historical_samples', 'paired_samples', 'paired_fraction', 'repeat_supported',
                      'chemistry_recorded', 'Elastic Modulus median', 'Pore Fraction median',
                      'Elastic Modulus between CV %', 'Pore Fraction between CV %',
                      'Elastic Modulus Mean', 'Elastic Modulus SD',
                      'Pore Fraction Mean', 'Pore Fraction SD']
candidate_columns += [column for column in PARETO_PARAMETERS if column not in candidate_columns]
candidate_columns += ['sample_repeats', 'compression_tests_per_sample']
candidate_table = screened_candidates.reindex(columns=candidate_columns).rename(columns={{'validation_id': 'candidate_id'}})
candidate_table.attrs = {{}}
display(candidate_table)
print(f'{{len(screened_candidates)}} retrospective candidate recipes.')
if SAVE_OUTPUTS:
    candidate_output = SCREENED_PARETO_OUTPUT
    candidate_output.mkdir(parents=True, exist_ok=True)
    figure_screened_candidates.savefig(candidate_output / 'candidate_ranking.png',
                              dpi=180, bbox_inches='tight')
    screened_candidates.rename(columns={{'validation_id': 'candidate_id'}}).to_csv(candidate_output / 'candidate_ranking.csv', index=False)
    screened_candidates.attrs['candidate_assessment'].to_csv(
        candidate_output / 'candidate_assessment.csv', index=False)
'''


def refresh(preview=False):
    for name in ['campaign_trends.ipynb', 'primospire_nmp_campaign_trends.ipynb']:
        path = ROOT / 'EVALUATE' / name
        notebook = json.loads(path.read_text(encoding='utf-8'))
        namespace = {'display': lambda *args: None}
        # These setup/filter cells only read measured data. Deliberately skip the
        # trend-plot cell, which also exports warm-start files.
        for index in [1, 3]:
            exec(compile(''.join(notebook['cells'][index]['source']), f'{name}:{index}', 'exec'), namespace)
        detailed, _ = load_notebook_selection(name, quiet=True)
        namespace['campaign_detailed'] = detailed
        candidates = assess_candidates(detailed, history=detailed)
        chosen, candidates = choose_candidates(candidates, id_prefix='C')
        columns = ['condition', 'historical_samples', 'paired_samples', 'repeat_supported',
                   'Elastic Modulus median', 'Pore Fraction median',
                   'Elastic Modulus between CV %', 'Pore Fraction between CV %', 'selection_utility']
        print('\n', name, '\nSELECTED\n', chosen[columns + ['selection_reason']].to_string(index=False))
        print('\nLEADING CANDIDATES\n', candidates.sort_values('selection_utility', ascending=False)[columns].head(15).to_string(index=False))
        if preview:
            continue
        chemistry = 'PSf / PolarClean' if name == 'campaign_trends.ipynb' else 'Primospire / NMP'
        section = next(c for c in notebook['cells'] if c['cell_type'] == 'markdown' and
                       ''.join(c['source']).startswith('### Retrospective ranking of screened films'))
        section['source'] = DESCRIPTION.splitlines(keepends=True)
        cell = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('PARETO_X ='))
        for node in ast.parse(''.join(cell['source'])).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PARETO_PARAMETERS' for t in node.targets):
                exec(compile(ast.Module(body=[node], type_ignores=[]), name, 'exec'), namespace)
        cell = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('from pareto_validation import'))
        cell['source'] = validation_source(chemistry).splitlines(keepends=True)
        tables = []
        namespace['display'] = tables.append
        exec(compile(''.join(cell['source']), name, 'exec'), namespace)
        chosen = namespace['screened_candidates']
        assert len(chosen) == 5 and chosen['condition'].is_unique
        output_dir = namespace['SCREENED_PARETO_OUTPUT']
        output_dir.mkdir(parents=True, exist_ok=True)
        # Preserve full precision separately from the notebook HTML display.
        chosen.rename(columns={'validation_id': 'candidate_id'}).to_csv(output_dir / 'candidate_ranking.csv', index=False)
        chosen.attrs['candidate_assessment'].to_csv(output_dir / 'candidate_assessment.csv', index=False)
        png = io.BytesIO()
        namespace['figure_screened_candidates'].savefig(png, format='png', dpi=120, bbox_inches='tight')
        (output_dir / 'candidate_ranking.png').write_bytes(png.getvalue())
        cell['outputs'] = [
            dict(output_type='display_data', metadata={}, data={'image/png': base64.b64encode(png.getvalue()).decode('ascii')}),
            dict(output_type='display_data', metadata={}, data={'text/html': tables[0].to_html(index=False), 'text/plain': tables[0].to_string(index=False)}),
            dict(output_type='stream', name='stdout', text=f'{len(chosen)} retrospective candidate recipes.\n'),
        ]
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        plt.close('all')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    refresh(parser.parse_args().preview)
