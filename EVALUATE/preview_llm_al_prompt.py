"""Build an actual AL prompt offline using one warm-start and one campaign row.

No API client, credentials, hardware, or model calls are used. Only the AL
functions are loaded from their syntax tree; the completion call is intercepted.
"""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'src' / 'pipeline'
sys.path.insert(0, str(PIPELINE))
from property_context import build_performance_observations, format_prompt_context
import polymer_additive_bounds as bounds


def load_offline_al(capture):
    prompts = ast.parse((PIPELINE / 'system_prompt.py').read_text(encoding='utf-8'))
    prompt_names = {'OPTIMIZATION_VALIDATION_INSTRUCTIONS', 'ACTIVE_LEARNING_PROMPT_TEMPLATE',
                    'ACTIVE_LEARNING_MODULUS_PORE_FRACTION_PROMPT_TEMPLATE'}
    assignments = [n for n in prompts.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id in prompt_names for t in n.targets)]
    prompt_namespace = {}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), '<offline-system-prompts>', 'exec'), prompt_namespace)
    system_prompt = SimpleNamespace(**{key: prompt_namespace[key] for key in prompt_names})
    tree = ast.parse((PIPELINE / 'activeLearning_29.py').read_text(encoding='utf-8'))
    names = {'current_ranges', '_normalized_search_mode', 'build_search_strategy_instructions',
             '_llm_al', 'LLM_AL', 'LLM_AL_modulus_pore_fraction'}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    def intercept(_client, **kwargs):
        capture.extend(kwargs['messages'])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Offline preview'))])
    namespace = {'bounds': bounds, 'system_prompt': system_prompt,
                 'format_prompt_context': format_prompt_context, 'client': None,
                 'create_chat_completion': intercept, 'time': SimpleNamespace(sleep=lambda _: None),
                 'Path': Path}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'_BASE_RANGES', '_DEFAULT_SEARCH_MODE'}:
                    namespace[target.id] = ast.literal_eval(node.value)
    source = 'from __future__ import annotations\n' + '\n'.join(ast.unparse(node) for node in functions)
    exec(compile(source, '<offline-al-preview>', 'exec'), namespace)
    return namespace


def main():
    warm = ROOT / 'data/warm_start/primospire_nmp.csv'
    campaign = ROOT / 'data/results/begins_2026-10-30/llm.csv'
    hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (warm, campaign)}
    rows = []
    for path, source in ((warm, 'warm_start'), (campaign, 'current_campaign')):
        data = pd.read_csv(path)
        finite = data[['Elastic Modulus Mean', 'Pore Fraction Mean']].notna().all(axis=1)
        # Use an older warm-start row so this two-source example does not repeat
        # the latest campaign sample now that exports include all notebook campaigns.
        row = data.loc[finite].iloc[0 if source == 'warm_start' else -1].copy()
        row['_observation_source'] = source
        rows.append(row)
    history = pd.DataFrame(rows)
    observations = build_performance_observations(history)
    messages = []
    al = load_offline_al(messages)
    al['LLM_AL_modulus_pore_fraction'](observations, search_mode='balanced', sleep=0)
    target = ROOT / 'data/toe_reprocessing/llm_al_prompt_example.txt'
    target.parent.mkdir(parents=True, exist_ok=True)
    text = 'OFFLINE EXAMPLE: one warm-start row + one campaign row; no API request.\n'
    for message in messages:
        content = message['content']
        if isinstance(content, list):
            content = '\n'.join(block['text'] for block in content if block['type'] == 'text')
        text += '\n=== ' + message['role'].upper() + ' ===\n' + content + '\n'
    target.write_text(text, encoding='utf-8')
    for path, digest in hashes.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Source changed: {path}'
    print('Prompt saved:', target)
    for observation in json.loads(observations)['observations']:
        values = observation['measurements']
        print(json.dumps({'source': observation['identity']['source'],
                          'condition': observation['identity']['condition'],
                          'measurements': {k: values.get(k) for k in (
                              'Elastic Modulus Mean', 'Elastic Modulus SD', 'Pore Fraction Mean', 'Pore Fraction SD')}}, indent=2))
    print('Both source files retain their original full-precision contents.')


if __name__ == '__main__':
    main()
