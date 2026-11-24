"""Render the grouped 10-panel plots without executing warm-start exports or selection."""
import ast
import base64
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from grouped_pareto import collapsed_table_html

from notebook_selection import load_notebook_selection

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = '''### Pareto front of similar-condition groups, with between-sample error bars

This plot uses **all repeat groups** from the consistency analysis, not the five selected validation recipes. It inherits this notebook's date, chemistry and quality filters and its `REPEAT_TOLERANCES`. Polymer concentration, nitrogen state and bath-solvent concentration match exactly; complete-linkage grouping limits exposure span to 10 s, bath-temperature span to 3°C, casting-speed span to 3 mm/s, and ambient-humidity span to 5 percentage points by default. Edit the existing tolerances cell to change these rules.

Each point is the arithmetic mean of the recorded sample means within one group. **Horizontal and vertical error bars are ±1 sample SD between sample means** (`ddof=1`), using the same samples with finite modulus and pore fraction for both axes. At least two paired samples are required. Labels show group ID and paired n. Singletons, samples with missing matching inputs, and groups with fewer than two finite paired observations do not enter this grouped frontier. The membership table below identifies the contributing samples.

The 2×5 layout, ten parameter panels, color maps, axis labels and black dashed frontier follow the existing Pareto plots. Colors show the mean recorded parameter among the contributing samples; minimum, maximum and available count are retained in the table. They are descriptive group summaries, not a new recipe. Mixing temperature, bath residence time, additive content and stock age are **not matched** by these similarity rules and may vary within a group. Chemistry identities and solvent identities are not additional matching keys; interpret groups within this notebook's chemistry scope. Error bars therefore describe variability among similar conditions, not necessarily exact-recipe reproducibility or a confidence interval. Dominance is computed on group means while maximizing both responses; overlapping SD bars do not establish statistically significant superiority. Pore fraction remains a compression-fit estimate.
'''

RECIPE_DESCRIPTION = '''### Typical measured performance by recipe

The panels show the median elastic modulus and median pore fraction across screened films with matching recorded process settings. Known chemistry fields must agree. When chemistry records are incomplete, only films in the same named recipe family can match. Raw casting settings take precedence. A recipe with a single retained film contributes its measured pair.

Each point is a pair of recipe medians. Its two coordinates can come from different films. The dashed line connects non-dominated median pairs. Colors describe the actual retained film closest to its recipe medians, so stock age and room humidity refer to that film. The table identifies the contributing films. The adjacent similar-condition plot groups films within process tolerances and shows the mean and between-film SD for groups with at least two films.

The screened Pareto exports are saved in the `screened/` subfolder. The historical recipe medians used by the downstream reproducibility analysis remain at their original paths.
'''


def recipe_source(chemistry):
    return f'''from pareto_candidate_selection import assess_candidates
from grouped_pareto import prepare_recipe_pareto, plot_recipe_pareto
from grouped_pareto import collapsed_table_html
from IPython.display import HTML

typical_recipe_summary = prepare_recipe_pareto(assess_candidates(campaign_detailed, history=campaign_detailed))
figure_typical_recipes, axes_typical_recipes = plot_recipe_pareto(
    typical_recipe_summary, PARETO_PARAMETERS, {chemistry!r}, property_label
)
plt.show()
display(HTML(collapsed_table_html(typical_recipe_summary, 'Show recipe summary table')))
print(f'{{len(typical_recipe_summary)}} recipes, including '
      f"{{int((typical_recipe_summary['paired_samples'] == 1).sum())}} with one usable sample.")
if SAVE_OUTPUTS:
    typical_output = SCREENED_PARETO_OUTPUT
    typical_output.mkdir(parents=True, exist_ok=True)
    figure_typical_recipes.savefig(typical_output / 'typical_recipe_pareto.png',
                                   dpi=180, bbox_inches='tight')
    typical_recipe_summary.to_csv(typical_output / 'typical_recipe_pareto.csv', index=False)
'''


def source(chemistry):
    return f'''import grouped_pareto
importlib.reload(grouped_pareto)
from grouped_pareto import summarize_grouped_pareto, plot_grouped_pareto
from grouped_pareto import collapsed_table_html
from IPython.display import HTML

grouped_pareto_summary = summarize_grouped_pareto(repeat_rows, PARETO_PARAMETERS)
figure_grouped_pareto, axes_grouped_pareto = plot_grouped_pareto(
    grouped_pareto_summary, PARETO_PARAMETERS, {chemistry!r}, property_label
)
plt.show()
display(HTML(collapsed_table_html(grouped_pareto_summary, 'Show group summary table')))
print(f'{{len(grouped_pareto_summary)}} groups; '
      f"{{int(grouped_pareto_summary['n_paired'].sum())}} paired sample observations; "
      'error bars = ±1 between-sample SD.')
if SAVE_OUTPUTS:
    grouped_output = SCREENED_PARETO_OUTPUT
    grouped_output.mkdir(parents=True, exist_ok=True)
    figure_grouped_pareto.savefig(grouped_output / 'similar_condition_pareto.png',
                                  dpi=180, bbox_inches='tight')
    grouped_pareto_summary.to_csv(grouped_output / 'similar_condition_pareto.csv', index=False)
'''


def refresh():
    for name, chemistry in [
        ('campaign_trends.ipynb', 'PSf / PolarClean'),
        ('primospire_nmp_campaign_trends.ipynb', 'Primospire / NMP'),
    ]:
        path = ROOT / 'EVALUATE' / name
        notebook = json.loads(path.read_text(encoding='utf-8'))
        namespace = {'display': lambda *args: None}
        for index in [1, 3]:
            exec(compile(''.join(notebook['cells'][index]['source']), name, 'exec'), namespace)
        detailed, _ = load_notebook_selection(name, quiet=True)
        namespace['campaign_detailed'] = detailed
        repeat = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('import campaign_repeatability'))
        exec(compile(''.join(repeat['source']), name, 'exec'), namespace)
        pareto = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('PARETO_X ='))
        for node in ast.parse(''.join(pareto['source'])).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PARETO_PARAMETERS' for t in node.targets):
                namespace['PARETO_PARAMETERS'] = ast.literal_eval(node.value)
        tables = []
        namespace['display'] = tables.append
        code = source(chemistry)
        exec(compile(code, name, 'exec'), namespace)
        figure = namespace['figure_grouped_pareto']
        table = namespace['grouped_pareto_summary']
        assert namespace['axes_grouped_pareto'].shape == (2, 5)
        assert (table['n_paired'] >= 2).all()
        buffer = io.BytesIO()
        figure.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        directory = namespace['SCREENED_PARETO_OUTPUT']
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'similar_condition_pareto.png').write_bytes(buffer.getvalue())
        table.to_csv(directory / 'similar_condition_pareto.csv', index=False)
        cells = [dict(cell_type='markdown', metadata={}, source=DESCRIPTION.splitlines(keepends=True)),
                 dict(cell_type='code', metadata={}, execution_count=None, source=code.splitlines(keepends=True), outputs=[
                     dict(output_type='display_data', metadata={}, data={'image/png': base64.b64encode(buffer.getvalue()).decode()}),
                     dict(output_type='display_data', metadata={}, data={'text/html': collapsed_table_html(table, 'Show group summary table'), 'text/plain': f'Group summary table ({len(table)} rows; expand in HTML view)'}),
                 ])]
        existing = next((i for i, c in enumerate(notebook['cells']) if ''.join(c['source']).startswith('### Pareto front of similar-condition groups')), None)
        if existing is None:
            index = next(i for i, c in enumerate(notebook['cells']) if ''.join(c['source']).startswith('### Reproducibility-aware selection'))
            notebook['cells'][index:index] = cells
        else:
            notebook['cells'][existing:existing + 2] = cells
        tables.clear()
        recipe_code = recipe_source(chemistry)
        exec(compile(recipe_code, name, 'exec'), namespace)
        recipe_table = namespace['typical_recipe_summary']
        recipe_figure = namespace['figure_typical_recipes']
        assert namespace['axes_typical_recipes'].shape == (2, 5)
        recipe_buffer = io.BytesIO()
        recipe_figure.savefig(recipe_buffer, format='png', dpi=100, bbox_inches='tight')
        (directory / 'typical_recipe_pareto.png').write_bytes(recipe_buffer.getvalue())
        recipe_table.to_csv(directory / 'typical_recipe_pareto.csv', index=False)
        recipe_cells = [dict(cell_type='markdown', metadata={}, source=RECIPE_DESCRIPTION.splitlines(keepends=True)),
                        dict(cell_type='code', metadata={}, execution_count=None, source=recipe_code.splitlines(keepends=True), outputs=[
                            dict(output_type='display_data', metadata={}, data={'image/png': base64.b64encode(recipe_buffer.getvalue()).decode()}),
                            dict(output_type='display_data', metadata={}, data={'text/html': collapsed_table_html(recipe_table, 'Show recipe summary table'), 'text/plain': f'Recipe summary table ({len(recipe_table)} rows; expand in HTML view)'}),
                        ])]
        recipe_index = next((i for i, c in enumerate(notebook['cells']) if ''.join(c['source']).startswith('### Typical measured performance by recipe')), None)
        if recipe_index is None:
            recipe_index = next(i for i, c in enumerate(notebook['cells']) if ''.join(c['source']).startswith('### Pareto front of similar-condition groups'))
            notebook['cells'][recipe_index:recipe_index] = recipe_cells
        else:
            notebook['cells'][recipe_index:recipe_index + 2] = recipe_cells
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(name, ':', len(table), 'groups;', int(table['n_paired'].sum()), 'samples')
        print('Typical-performance view:', len(recipe_table), 'recipes')
        plt.close('all')


if __name__ == '__main__':
    refresh()
