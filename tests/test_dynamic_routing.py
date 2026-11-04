"""Real campaign/runtime/checkpoint consumers; native SDK and robot transports mocked."""
from contextlib import ExitStack
import csv
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('OPENROUTER_API_KEY', 'offline-test-placeholder')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
import run_loop as loop
from mas_runtime import CampaignRuntime
from mas_workspace import Workspace
from test_mas_contract import CONTEXT, PARAMS
from test_mas_runtime import FakeCodex

MATERIALS = CONTEXT['materials']


class Crash(BaseException):
    pass


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'pipeline'
        self.csv = self.root / 'data/results/begins_test/llm.csv'
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text('name,E,F,other\ncondition-A,1.234567890123,0.5,unchanged\n')
        self.checkpoint = self.root / 'raw/condition-A/.pipeline_state.json'
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_text(json.dumps(dict(params={**PARAMS, **MATERIALS},
            completed_stages=['files_saved', 'branches_processed', 'results_attached'], branch_results={})))
        (self.checkpoint.parent / 'params.json').write_text(json.dumps({**PARAMS, **MATERIALS}))
        self.workspace = self.base / 'scientific-output'
        self.sdk = FakeCodex(Workspace(self.workspace, loop._REPO_ROOT, 'synthetic'))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(loop,
            LLM_AL_SEARCH_MODE='dynamic', ITERATE_ADDITIVES=False, ITERATE_POLYMER=False,
            LOCK_ADDITIVE_WT=True, LOCK_ADDITIVE_WT_VALUE=0, LLM_AL_WARM_START_CSV=None,
            CSV_AGG_LLM=self.csv, CSV_REPS=self.csv.parent/'reps.csv', CSV_AGG=self.csv.parent/'agg.csv',
            JSON_RESULTS_DIR=self.root/'out', DATA_ROOT=self.root,
            MAS_WORKSPACE_ROOT=self.workspace, MAS_MATERIAL_KEY='synthetic'))
        self.stack.enter_context(patch.object(loop, '_current_material_context', return_value=MATERIALS))
        self.stack.enter_context(patch.object(loop, '_checkpoint_path', return_value=self.checkpoint))
        self.stack.enter_context(patch.object(loop.master_processing, 'BRANCH_CONFIG',
            {'curve_segmentation': {'enabled': True, 'type': 'performance'}}))
        self.stack.enter_context(patch.object(loop.llm_context, 'attach_experiment_time'))
        self.legacy = self.stack.enter_context(patch.object(loop.llm_context, 'generate_reports_and_suggestion',
            side_effect=AssertionError('unexpected legacy model call')))
        self.warm = self.stack.enter_context(patch.object(loop.llm_context, 'generate_warm_start_suggestion',
            side_effect=AssertionError('unexpected legacy warm-start call')))
        def runtime(workspace, context):
            self.sdk.w = workspace
            return CampaignRuntime(workspace, context, sdk_factory=lambda: self.sdk)
        self.factory = self.stack.enter_context(patch.object(loop, 'CampaignRuntime', side_effect=runtime))
        self.robot = self.stack.enter_context(patch.object(loop.url, 'run_test'))
        self.health = self.stack.enter_context(patch.object(loop.url, 'check_health', return_value={'journal_id':'journal'}))

    def state(self):
        return json.loads(self.checkpoint.read_text())

    def run_pipeline(self):
        loop._run_pipeline_and_trigger_next({**PARAMS, **MATERIALS}, resume_condition='condition-A')

    def queue(self, identity='revision-1', reason='New approved evidence changes the question'):
        return loop.request_dynamic_reconsideration('condition-A', revision_id=identity, reason=reason)

    def test_run_uses_native_reviewed_exact_params_and_existing_submission_journal(self):
        with patch.object(loop, '_enforce_stock_mixing_temperature', side_effect=AssertionError('no dynamic clamp')):
            self.run_pipeline()
        self.legacy.assert_not_called()
        sent = self.robot.call_args.args[0]
        self.assertEqual({k:v for k,v in sent.items() if k!='stock_metadata'}, {**PARAMS, **MATERIALS})
        self.assertEqual(self.robot.call_args.kwargs['journal_id'], 'journal')
        state = self.state()
        self.assertIn('next_run_submitted', state['completed_stages'])
        self.assertEqual(self.robot.call_args.kwargs['request_id'], state['submission_request_id'])
        self.assertEqual(len(self.sdk.starts), 1)
        turns = len(self.sdk.prompts)
        self.run_pipeline()
        self.robot.assert_called_once()
        self.assertEqual(len(self.sdk.prompts), turns)

    def test_hold_stop_are_preserved_with_no_inference_or_submission_on_restart(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        hold = self.state()['mas_decision']
        turns = len(self.sdk.prompts)
        self.run_pipeline()
        self.assertEqual(len(self.sdk.prompts), turns)
        self.queue()
        self.sdk.action = 'stop'
        self.run_pipeline()
        state = self.state()
        self.assertEqual([d['action'] for d in state['mas_decisions']], ['hold','stop'])
        self.assertEqual(state['mas_decisions'][0], hold)
        turns = len(self.sdk.prompts)
        self.run_pipeline()
        self.assertEqual(len(self.sdk.prompts), turns)
        self.robot.assert_not_called()
        self.health.assert_not_called()
        self.assertFalse((self.root/'out/llm_result_condition-A.json').exists())

    def test_missing_resume_recommendation_uses_actual_dynamic_hold(self):
        self.sdk.action = 'hold'
        self.assertIsNone(loop._load_resume_params_for_campaign('test'))
        self.assertEqual(self.state()['mas_decision']['action'], 'hold')
        self.assertTrue(self.factory.called)
        self.legacy.assert_not_called()
        self.robot.assert_not_called()

    def test_initial_campaign_without_history_uses_reviewed_theory_design(self):
        self.csv.unlink()
        params = loop._new_campaign_params()
        self.assertEqual(params, {**PARAMS, **MATERIALS})
        saved = json.loads((self.csv.parent/'initial_suggestion.json').read_text())
        self.assertEqual(saved['next_params'], params)
        self.assertEqual(saved['mas_decision']['inputs'], {})
        self.assertTrue(Path(saved['mas_decision']['report_path']).is_file())
        turns = len(self.sdk.prompts)
        self.assertEqual(loop._new_campaign_params(), params)
        self.assertEqual(len(self.sdk.prompts), turns)
        self.robot.assert_not_called()
        self.warm.assert_not_called()

    def test_initial_submit_rejects_coherent_feasible_cache_and_outgoing_drift(self):
        self.csv.unlink()
        params = loop._new_campaign_params()
        path = self.csv.parent/'initial_suggestion.json'
        original = json.loads(path.read_text())
        accepted = original['mas_decision']['next_params'].copy()
        drifted = dict(params, bath_temp=8.0)
        self.assertNotEqual(drifted, accepted)
        loop._validate_dynamic_params(drifted)  # Feasibility cannot authorize drift.
        turns, head = len(self.sdk.prompts), self.sdk.w.head()
        for submission in (None, dict(request_id='existing-request', journal_id='journal'),
                           dict(request_id='existing-request', journal_id='journal', submitted=True)):
            with self.subTest(submission=submission):
                saved = json.loads(json.dumps(original))
                saved['next_params'] = drifted
                if submission is not None:
                    saved['submission'] = submission
                path.write_text(json.dumps(saved))
                before = path.read_bytes()
                with patch.object(loop, '_save_json', wraps=loop._save_json) as save:
                    with self.assertRaisesRegex(ValueError, 'conditions changed after MAS review'):
                        loop._submit_dynamic_initial(dict(drifted,
                            stock_metadata=loop.activeLearning.bounds.send_metadata()))
                    save.assert_not_called()
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(json.loads(path.read_text())['mas_decision']['next_params'], accepted)
                self.robot.assert_not_called()
                self.health.assert_not_called()
        self.assertEqual(len(self.sdk.prompts), turns)
        self.assertEqual(self.sdk.w.head(), head)

    def test_initial_submit_requires_run_even_with_coherent_feasible_cache(self):
        self.csv.unlink()
        path = self.csv.parent/'initial_suggestion.json'
        supplied = {**PARAMS, **MATERIALS}
        for action in ('hold', 'stop'):
            with self.subTest(action=action):
                self.sdk.action = action
                if action == 'stop':
                    loop.request_dynamic_reconsideration(revision_id='initial-stop-review',
                        reason='Synthetic independent review now stops the initial inquiry')
                self.assertIsNone(loop._new_campaign_params())
                original = path.read_bytes()
                saved = json.loads(original)
                self.assertEqual(saved['mas_decision']['action'], action)
                self.assertIsNone(saved['mas_decision']['next_params'])
                saved['next_params'] = supplied
                path.write_text(json.dumps(saved))
                before, turns, head = path.read_bytes(), len(self.sdk.prompts), self.sdk.w.head()
                try:
                    with patch.object(loop, '_save_json', wraps=loop._save_json) as save:
                        with self.assertRaisesRegex(ValueError, 'accepted RUN'):
                            loop._submit_dynamic_initial(supplied)
                        save.assert_not_called()
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(len(self.sdk.prompts), turns)
                    self.assertEqual(self.sdk.w.head(), head)
                    self.robot.assert_not_called()
                    self.health.assert_not_called()
                finally:
                    path.write_bytes(original)

    def test_initial_warm_inputs_are_only_revealed_after_actual_bootstrap_commit(self):
        self.csv.unlink()
        warm = self.base/'warm.csv'
        warm.write_text('name,E,F\nSYNTHETIC-old,2,0.3\n')
        original = warm.read_bytes()
        with patch.object(loop, 'LLM_AL_WARM_START_CSV', warm):
            params = loop._new_campaign_params()
        saved = json.loads((self.csv.parent/'initial_suggestion.json').read_text())
        inputs = saved['mas_decision']['inputs']
        self.assertIn('warm_start', inputs)
        self.assertNotIn('.mas-inputs', self.sdk.prompts[0])
        self.assertIn(inputs['warm_start']['path'], self.sdk.prompts[-1])
        self.assertEqual(warm.read_bytes(), original)
        self.assertEqual(params, {**PARAMS, **MATERIALS})
        self.assertIsNotNone(saved['mas_decision']['knowledge_commit'])
        self.warm.assert_not_called()

    def test_initial_hold_reconsideration_is_queued_once_and_preserves_history(self):
        self.csv.unlink()
        self.sdk.bootstrap_hold = True
        self.assertIsNone(loop._new_campaign_params())
        path = self.csv.parent/'initial_suggestion.json'
        before = json.loads(path.read_text())
        turns = len(self.sdk.prompts)
        self.assertIsNone(loop._new_campaign_params())
        self.assertEqual(len(self.sdk.prompts), turns)
        loop.request_dynamic_reconsideration(revision_id='initial-review-1', reason='Theory initialization can now proceed')
        self.assertEqual(json.loads(path.read_text())['mas_decision'], before['mas_decision'])
        self.sdk.bootstrap_hold = False
        params = loop._new_campaign_params()
        state = json.loads(path.read_text())
        self.assertEqual([d['action'] for d in state['mas_decisions']], ['hold','run'])
        turns = len(self.sdk.prompts)
        loop.request_dynamic_reconsideration(revision_id='initial-review-1', reason='Theory initialization can now proceed')
        self.assertEqual(loop._new_campaign_params(), params)
        self.assertEqual(len(self.sdk.prompts), turns)
        self.robot.assert_not_called()

    def test_initial_decision_lost_save_recovers_same_request_without_new_native_turn(self):
        self.csv.unlink()
        native_save = loop._save_json
        def crash(path, state):
            if path.name == 'initial_suggestion.json' and state.get('mas_decision'):
                raise Crash('lost initial caller save')
            return native_save(path, state)
        with patch.object(loop, '_save_json', side_effect=crash):
            with self.assertRaises(Crash):
                loop._new_campaign_params()
        turns = len(self.sdk.prompts)
        self.assertEqual(loop._new_campaign_params(), {**PARAMS, **MATERIALS})
        self.assertEqual(len(self.sdk.prompts), turns)
        saved = json.loads((self.csv.parent/'initial_suggestion.json').read_text())
        self.assertEqual(len(saved['mas_decisions']), 1)
        self.robot.assert_not_called()

    def test_invalid_native_design_never_clamps_or_submits(self):
        with patch('test_mas_runtime.PARAMS', dict(PARAMS, polymer_wt=17, mixing_temp=80)):
            with self.assertRaisesRegex(ValueError, 'Undiluted'):
                self.run_pipeline()
        self.robot.assert_not_called()
        self.health.assert_not_called()
        self.assertTrue(self.state()['mas_failures'])

    def test_ambiguous_submission_reuses_exact_request_and_journal_without_new_inference(self):
        self.robot.side_effect = TimeoutError('lost acknowledgement')
        with self.assertRaises(TimeoutError):
            self.run_pipeline()
        first = dict(self.robot.call_args.kwargs)
        turns = len(self.sdk.prompts)
        before = self.checkpoint.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'physical request'):
            self.queue()
        self.assertEqual(before, self.checkpoint.read_bytes())
        self.robot.side_effect = None
        self.run_pipeline()
        self.assertEqual(self.robot.call_args.kwargs, first)
        self.assertEqual(len(self.sdk.prompts), turns)
        self.assertEqual(len(self.state()['mas_decisions']), 1)

    def test_conflicting_saved_conditions_block_submission_without_overwrite(self):
        path = self.root/'out/llm_result_condition-A.json'
        path.parent.mkdir()
        path.write_text(json.dumps({**PARAMS, **MATERIALS, 'bath_temp':25}))
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'differ from the reviewed'):
            self.run_pipeline()
        self.assertEqual(path.read_bytes(), original)
        self.robot.assert_not_called()

    def test_acknowledged_callback_and_initial_submissions_cannot_be_replaced(self):
        self.run_pipeline()
        turns = len(self.sdk.prompts)
        self.robot.reset_mock()
        self.health.reset_mock()
        self.assertIsNone(loop._load_resume_params_for_campaign('test'))
        self.assertEqual(len(self.sdk.prompts), turns)
        with self.assertRaisesRegex(RuntimeError, 'physical request'):
            self.queue()
        self.robot.assert_not_called()
        self.health.assert_not_called()

    def test_initial_lost_ack_and_acknowledged_restart_preserve_request_identity(self):
        self.csv.unlink()
        params = loop._new_campaign_params()
        self.robot.side_effect = TimeoutError('lost initial acknowledgement')
        with self.assertRaises(TimeoutError):
            loop._submit_dynamic_initial(dict(params, stock_metadata=loop.activeLearning.bounds.send_metadata()))
        saved = json.loads((self.csv.parent/'initial_suggestion.json').read_text())
        self.assertEqual({k:v for k,v in self.robot.call_args.args[0].items() if k!='stock_metadata'},
                         saved['mas_decision']['next_params'])
        first = dict(self.robot.call_args.kwargs)
        turns = len(self.sdk.prompts)
        with self.assertRaisesRegex(RuntimeError, 'physical request'):
            loop.request_dynamic_reconsideration(revision_id='initial-new', reason='New evidence')
        self.robot.side_effect = None
        loop._submit_dynamic_initial(loop._new_campaign_params())
        self.assertEqual(self.robot.call_args.kwargs, first)
        self.robot.reset_mock()
        self.health.reset_mock()
        loop._submit_dynamic_initial(loop._new_campaign_params())
        self.robot.assert_not_called()
        self.health.assert_not_called()
        self.assertEqual(json.loads((self.csv.parent/'initial_suggestion.json').read_text())['submission'],
                         dict(first, submitted=True))
        self.assertEqual(len(self.sdk.prompts), turns)

    def test_supported_reconsideration_preserves_held_decision_and_request_identity(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        before = self.state()
        self.queue()
        saved = self.state()
        self.assertEqual(saved['mas_decision'], before['mas_decision'])
        self.assertEqual(saved['completed_stages'], before['completed_stages'])
        self.assertEqual(saved['mas_request']['id'], 'revision-1')
        self.queue()
        self.sdk.action = 'run'
        self.run_pipeline()
        state = self.state()
        self.assertEqual(state['mas_decisions'][0], before['mas_decision'])
        self.assertEqual([d['action'] for d in state['mas_decisions']], ['hold','run'])
        self.assertEqual(self.robot.call_args.kwargs['request_id'], state['submission_request_id'])
        turns = len(self.sdk.prompts)
        self.queue()  # Same already-applied intent is a no-op, even after dispatch.
        self.run_pipeline()
        self.assertEqual(len(self.sdk.prompts), turns)
        self.robot.assert_called_once()
        with self.assertRaisesRegex(ValueError, 'different reason'):
            self.queue(reason='Conflicting reason')

    def test_lost_pipeline_decision_save_recovers_runtime_result_without_new_inference(self):
        native_save = loop._save_checkpoint
        def crash(condition, state):
            if state.get('mas_decision'):
                raise Crash('lost caller save after accepted runtime result')
            return native_save(condition, state)
        with patch.object(loop, '_save_checkpoint', side_effect=crash):
            with self.assertRaises(Crash):
                self.run_pipeline()
        self.assertIn('mas_request', self.state())
        self.assertNotIn('mas_decision', self.state())
        turns = len(self.sdk.prompts)
        self.run_pipeline()
        self.assertEqual(len(self.sdk.prompts), turns)
        self.assertEqual(len(self.state()['mas_decisions']), 1)
        self.robot.assert_called_once()

    def test_reconsideration_lost_caller_save_does_not_create_another_revision(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        original = self.state()['mas_decision']
        self.queue()
        self.sdk.action = 'run'
        native_save = loop._save_checkpoint
        def crash(condition, state):
            if state.get('mas_decision', {}).get('request_reason'):
                raise Crash('lost reconsideration save')
            return native_save(condition, state)
        with patch.object(loop, '_save_checkpoint', side_effect=crash):
            with self.assertRaises(Crash):
                self.run_pipeline()
        self.assertEqual(self.state()['mas_decision'], original)
        turns = len(self.sdk.prompts)
        self.run_pipeline()
        self.assertEqual(len(self.sdk.prompts), turns)
        self.assertEqual(len(self.state()['mas_decisions']), 2)
        self.robot.assert_called_once()

    def test_reconsideration_running_turn_resumes_same_native_operation(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        self.queue()
        self.sdk.interrupt_once = True
        with self.assertRaises(TimeoutError):
            self.run_pipeline()
        native_count = len(self.sdk.threads['main'].data.turns)
        pending = json.loads((self.workspace/'.mas-state.json').read_text())['active']
        self.sdk.action = 'run'
        self.run_pipeline()
        self.assertEqual(len(self.sdk.threads['main'].data.turns), native_count)
        self.assertEqual(self.state()['mas_decision']['runtime_operation_id'], pending)
        self.robot.assert_called_once()

    def test_new_measured_input_requires_explicit_review_and_preserves_old_snapshot(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        prior = self.state()['mas_decision']
        old = Path(prior['inputs']['selected']['path'])
        original = old.read_bytes()
        self.csv.write_text('name,E,F,other\ncondition-A,9,0.1,unchanged\n')
        self.run_pipeline()  # Held result remains held, no automatic inference.
        self.queue()
        self.sdk.action = 'run'
        self.run_pipeline()
        self.assertEqual(old.read_bytes(), original)
        self.assertNotEqual(self.state()['mas_decision']['inputs']['selected']['path'], str(old))
        self.robot.assert_called_once()

    def test_shared_csv_columns_and_actual_readable_accepted_location(self):
        self.run_pipeline()
        with self.csv.open(newline='') as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual([rows[0][k] for k in ('E','F','other')], ['1.234567890123','0.5','unchanged'])
        for key in ('initial_report','final_report','LLM_suggestion'):
            self.assertTrue(rows[0][key])
        report = Path(self.state()['mas_decision']['report_path'])
        self.assertTrue(report.is_file())
        self.assertIn('Campaign decision: run', report.read_text())
        self.assertIn(str(report), rows[0]['final_report'])
        self.assertIn(report.relative_to(self.workspace).as_posix(), self.sdk.w.git('ls-files').stdout.decode())

    def test_caller_source_condition_is_explicit_in_main_question(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        self.assertIn('condition-A', self.sdk.prompts[-1])
        self.assertEqual(self.state()['mas_decision']['source_condition'], 'condition-A')

    def test_changed_feasible_cached_tuple_cannot_replace_actual_reviewed_execution(self):
        with patch.object(loop, '_write_dynamic_params', side_effect=Crash('before execution payload save')):
            with self.assertRaises(Crash):
                self.run_pipeline()
        state = self.state()
        state['mas_decision']['next_params']['bath_temp'] = 8  # Feasible, but never reviewed.
        self.checkpoint.write_text(json.dumps(state))
        self.robot.assert_not_called()
        with self.assertRaises(ValueError):
            self.run_pipeline()
        self.robot.assert_not_called()

    def test_retired_modules_and_checkpoints_are_rejected_not_migrated(self):
        for module in ('codex_context','mas_records','mas_schema','mas_analysis'):
            self.assertIsNone(importlib.util.find_spec(module), module)
        state = self.state()
        state['mas_decision'] = dict(action='hold', reason='old fixed stage')
        self.checkpoint.write_text(json.dumps(state))
        with self.assertRaisesRegex(ValueError, 'Retired'):
            self.run_pipeline()
        self.assertEqual(self.state()['mas_decision'], state['mas_decision'])
        self.factory.assert_not_called()
        self.robot.assert_not_called()

    def test_retired_initial_payload_is_preserved_and_not_adopted(self):
        path = self.csv.parent/'initial_suggestion.json'
        path.write_text(json.dumps(dict(search_mode='dynamic', next_params={**PARAMS, **MATERIALS})))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Retired'):
            loop._new_campaign_params()
        self.assertEqual(path.read_bytes(), before)
        self.factory.assert_not_called()
        self.robot.assert_not_called()

    def test_missing_binding_fixed_sweep_and_disabled_performance_fail_before_models(self):
        with patch.object(loop, 'MAS_WORKSPACE_ROOT', None), self.assertRaisesRegex(ValueError, 'explicit'):
            self.run_pipeline()
        with patch.object(loop, 'ITERATE_ADDITIVES', True), self.assertRaisesRegex(ValueError, 'fixed iteration'):
            self.run_pipeline()
        with patch.object(loop.master_processing, 'BRANCH_CONFIG', {}), self.assertRaisesRegex(ValueError, 'performance'):
            self.run_pipeline()
        self.factory.assert_not_called()
        self.robot.assert_not_called()

    def test_all_non_mas_modes_still_use_legacy_generator(self):
        for mode in ('single','double','explore','double_explore'):
            with self.subTest(mode=mode):
                fixture = RoutingTests()
                fixture.setUp()
                try:
                    fixture.legacy.side_effect = None
                    fixture.legacy.return_value = json.dumps(dict(next_params=PARAMS))
                    with patch.object(loop, 'LLM_AL_SEARCH_MODE', mode):
                        fixture.run_pipeline()
                    fixture.legacy.assert_called_once()
                    fixture.factory.assert_not_called()
                    fixture.robot.assert_called_once()
                finally:
                    fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
