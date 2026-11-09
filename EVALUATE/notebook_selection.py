"""Use the two analysis notebooks as the source of truth for warm-start selection.

Only configuration, function definitions, and the loading/filtering cell run.
Plotting, model fitting, exports, and later notebook cells are not executed.
"""
import contextlib
import io
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import campaign_trends as analysis

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_OUTPUTS = {
    'campaign_trends.ipynb': 'polysulfone_polarclean.csv',
    'primospire_nmp_campaign_trends.ipynb': 'primospire_nmp.csv',
}
SETTING_NAMES = ('PROPERTIES', 'CAMPAIGNS', 'START', 'END', 'LAST_CAMPAIGN',
                 'ANALYSIS_START_DATE', 'SAMPLE_START_DATE', 'SAMPLE_END_DATE',
                 'CHEMISTRY_FILTER', 'MIN_THICKNESS', 'MAX_CV', 'MAX_DISCARDS',
                 'EXCLUDED_SAMPLES', 'DAY_ROLLOVER_HOUR')


def selection_settings(namespace):
    settings = {key: namespace[key] for key in SETTING_NAMES if key in namespace}
    if isinstance(settings.get('EXCLUDED_SAMPLES'), dict):
        settings['EXCLUDED_SAMPLES'] = [
            {'campaign': key[0], 'condition': key[1], 'reason': reason}
            for key, reason in settings['EXCLUDED_SAMPLES'].items()
        ]
    return settings


def load_notebook_selection(notebook_name, root=ROOT, *, quiet=False):
    if notebook_name not in NOTEBOOK_OUTPUTS:
        raise ValueError(f'Unsupported analysis notebook: {notebook_name}')
    root = Path(root).resolve()
    path = root / 'EVALUATE' / notebook_name
    notebook = json.loads(path.read_text(encoding='utf-8'))
    cells = [''.join(c['source']) for c in notebook['cells'] if c['cell_type'] == 'code']
    markers = (r'^PROPERTIES\s*=\s*\[', r'^def infer_chemistry\(', r'^campaign = select_campaign\(all_data')
    selected = []
    for marker in markers:
        matches = [source for source in cells if re.search(marker, source, re.MULTILINE)]
        if len(matches) != 1:
            raise ValueError(f'{notebook_name}: expected exactly one selection cell containing {marker!r}')
        selected.append(matches[0])
    namespace = {'repo_root': root, 'Path': Path, 'plt': plt, 'display': lambda *a, **k: None}
    for name in ('load_campaign_data', 'select_campaign', 'available_properties', 'POLARCLEAN_LAST_CAMPAIGN'):
        namespace[name] = getattr(analysis, name)
    output = io.StringIO()
    with contextlib.redirect_stdout(output) if quiet else contextlib.nullcontext():
        for index, source in enumerate(selected):
            exec(compile(source, f'{path}:selection-{index}', 'exec'), namespace)
    # This is the same enrichment performed by plot_detailed_campaign; it drops no rows.
    data = namespace['campaign'].copy().sort_values('sample_time').reset_index(drop=True)
    data['iteration'] = data.index + 1
    return data, selection_settings(namespace)
