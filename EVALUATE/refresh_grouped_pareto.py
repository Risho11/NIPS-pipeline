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

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTION = '''### Pareto front of similar-condition groups, with between-sample error bars

This plot uses **all repeat groups** from the consistency analysis, not the five selected validation recipes. It inherits this notebook's date, chemistry and quality filters and its `REPEAT_TOLERANCES`. Polymer concentration, nitrogen state and bath-solvent concentration match exactly; complete-linkage grouping limits exposure span to 10 s, bath-temperature span to 3°C, casting-speed span to 3 mm/s, and ambient-humidity span to 5 percentage points by default. Edit the existing tolerances cell to change these rules.

Each point is the arithmetic mean of the recorded sample means within one group. **Horizontal and vertical error bars are ±1 sample SD between sample means** (`ddof=1`), using the same samples with finite modulus and pore fraction for both axes. At least two paired samples are required. Labels show group ID and paired n. Singletons, samples with missing matching inputs, and groups with fewer than two finite paired observations do not enter this grouped frontier. The membership table below identifies the contributing samples.

The 2×5 layout, ten parameter panels, color maps, axis labels and black dashed frontier follow the existing Pareto plots. Colors show the mean recorded parameter among the contributing samples; minimum, maximum and available count are retained in the table. They are descriptive group summaries, not a new recipe. Mixing temperature, bath residence time, additive content and stock age are **not matched** by these similarity rules and may vary within a group. Chemistry identities and solvent identities are not additional matching keys; interpret groups within this notebook's chemistry scope. Error bars therefore describe variability among similar conditions, not necessarily exact-recipe reproducibility or a confidence interval. Dominance is computed on group means while maximizing both responses; overlapping SD bars do not establish statistically significant superiority. Pore fraction remains a compression-fit estimate.
'''

RECIPE_DESCRIPTION = '''### Typical measured performance by recipe — ten parameter panels

This is the **recipe-level historical-median view** from the earlier typical-performance plot, now in the same 2×5 parameter layout. It includes every assessed eligible recipe, **including recipes with one usable sample**, rather than only the five selected validation conditions. Recipe eligibility starts with this notebook's filters; historical statistics then use all available matching recorded recipes, including poor repeats outside those filters. Matching requires exact recorded process settings and no known chemistry conflicts; incomplete chemistry permits matching only within the same named recipe family. Original raw settings take precedence. Only paired finite observations with positive modulus and pore fraction in [0,1] enter the medians.

Each point is the recipe's median elastic modulus and median pore fraction across its usable historical samples. These two medians need not come from one physical sample. The black dashed front maximizes both medians; **no SD error bars are shown in this median view**. Frontier labels show recipe ID, usable n and parameter value; the table identifies every recipe. Colors use the recorded parameter of the actual eligible representative sample nearest the recipe medians, matching the earlier typical-performance view. Stock age and ambient humidity therefore describe that representative sample, not every historical repeat. No unseen outcomes are predicted or filled in.

Compare this with the adjacent similar-condition-group plot: it uses group **means ±1 between-sample SD**, merges nearby conditions within tolerances and requires at least two samples. Counts differ because the two views use different matching and sample-inclusion rules. Neither view by itself certifies that a recipe has been validated.
'''


def recipe_source(chemistry, output):
    return f'''from pareto_candidate_selection import assess_candidates
from grouped_pareto import prepare_recipe_pareto, plot_recipe_pareto
from grouped_pareto import collapsed_table_html
from IPython.display import HTML

typical_recipe_summary = prepare_recipe_pareto(assess_candidates(campaign_detailed))
figure_typical_recipes, axes_typical_recipes = plot_recipe_pareto(
    typical_recipe_summary, PARETO_PARAMETERS, {chemistry!r}, property_label
)
plt.show()
display(HTML(collapsed_table_html(typical_recipe_summary, 'Show recipe summary table')))
print(f'{{len(typical_recipe_summary)}} recipes, including '
      f"{{int((typical_recipe_summary['paired_samples'] == 1).sum())}} with one usable sample.")
if SAVE_OUTPUTS:
    typical_output = repo_root / 'EVALUATE' / {output!r}
    typical_output.mkdir(parents=True, exist_ok=True)
    figure_typical_recipes.savefig(typical_output / 'typical_recipe_pareto.png',
                                   dpi=180, bbox_inches='tight')
    typical_recipe_summary.to_csv(typical_output / 'typical_recipe_pareto.csv', index=False)
'''


def source(chemistry, output):
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
    grouped_output = repo_root / 'EVALUATE' / {output!r}
    grouped_output.mkdir(parents=True, exist_ok=True)
    figure_grouped_pareto.savefig(grouped_output / 'similar_condition_pareto.png',
                                  dpi=180, bbox_inches='tight')
    grouped_pareto_summary.to_csv(grouped_output / 'similar_condition_pareto.csv', index=False)
'''


def refresh():
    for name, chemistry, output in [
        ('campaign_trends.ipynb', 'PSf / PolarClean', 'campaign_trends_output'),
        ('primospire_nmp_campaign_trends.ipynb', 'Primospire / NMP', 'primospire_nmp_campaign_trends_output'),
    ]:
        path = ROOT / 'EVALUATE' / name
        notebook = json.loads(path.read_text(encoding='utf-8'))
        namespace = {'display': lambda *args: None}
        for index in [1, 3, 5, 6]:
            exec(compile(''.join(notebook['cells'][index]['source']), name, 'exec'), namespace)
        detailed = namespace['campaign'].sort_values('sample_time').reset_index(drop=True).copy()
        detailed['iteration'] = detailed.index + 1
        namespace['campaign_detailed'] = detailed
        repeat = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('import campaign_repeatability'))
        exec(compile(''.join(repeat['source']), name, 'exec'), namespace)
        pareto = next(c for c in notebook['cells'] if ''.join(c['source']).startswith('PARETO_X ='))
        for node in ast.parse(''.join(pareto['source'])).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PARETO_PARAMETERS' for t in node.targets):
                namespace['PARETO_PARAMETERS'] = ast.literal_eval(node.value)
        tables = []
        namespace['display'] = tables.append
        code = source(chemistry, output)
        exec(compile(code, name, 'exec'), namespace)
        figure = namespace['figure_grouped_pareto']
        table = namespace['grouped_pareto_summary']
        assert namespace['axes_grouped_pareto'].shape == (2, 5)
        assert (table['n_paired'] >= 2).all()
        buffer = io.BytesIO()
        figure.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        directory = ROOT / 'EVALUATE' / output
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
        recipe_code = recipe_source(chemistry, output)
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
