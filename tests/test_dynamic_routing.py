"""Real campaign/runtime/checkpoint consumers; native SDK and robot transports mocked."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import csv
import importlib.util
import io
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
from test_mas_workspace import project
from test_mas_runtime import FakeCodex

MATERIALS = CONTEXT['materials']


class Crash(BaseException):
    pass


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = project(self.base / 'pipeline')
        self.csv = self.root / 'data/results/begins_test/llm.csv'
        self.csv.parent.mkdir(parents=True)
        self.csv.write_text('name,E,F,other\ncondition-A,1.234567890123,0.5,unchanged\n')
        self.checkpoint = self.root / 'raw/condition-A/.pipeline_state.json'
        self.checkpoint.parent.mkdir(parents=True)
        self.checkpoint.write_text(json.dumps(dict(params={**PARAMS, **MATERIALS},
            completed_stages=['files_saved', 'branches_processed', 'results_attached'], branch_results={})))
        (self.checkpoint.parent / 'params.json').write_text(json.dumps({**PARAMS, **MATERIALS}))
        self.workspace = self.root
        self.sdk = FakeCodex(Workspace(self.root, 'begins_test', 'synthetic'))
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(loop,
            LLM_AL_SEARCH_MODE='dynamic', ITERATE_ADDITIVES=False, ITERATE_POLYMER=False,
            LOCK_ADDITIVE_WT=True, LOCK_ADDITIVE_WT_VALUE=0, LLM_AL_WARM_START_CSV=None,
            CSV_AGG_LLM=self.csv, CSV_REPS=self.csv.parent/'reps.csv', CSV_AGG=self.csv.parent/'agg.csv',
            JSON_RESULTS_DIR=self.root/'out', DATA_ROOT=self.root,
            _REPO_ROOT=self.root, MAS_MATERIAL_KEY='synthetic'))
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

    def test_dynamic_inputs_preflight_precedes_fingerprint_and_copy_after_env_change(self):
        workspace=self.sdk.w;area=workspace.path(workspace.area)
        original=self.csv.read_bytes();checkpoint=self.checkpoint.read_bytes();head=workspace.head()
        index=Path(workspace.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip());raw=index.read_bytes()
        for variable in ('CODEX_HOME','CODEX_SQLITE_HOME'):
            for home in (area,area/'.inputs',area/'.inputs/request',area/'.native/sqlite',area/'rounds/op/attempt-0/.codex'):
                environment={'CODEX_HOME':str(self.base/'external-home'),'CODEX_SQLITE_HOME':str(self.base/'external-sqlite'),variable:str(home)}
                with (self.subTest(variable=variable,home=str(home)),patch('pathlib.Path.home',return_value=self.base/'user-home'),
                      patch.dict(os.environ,environment),patch.object(loop,'_dynamic_workspace',return_value=workspace),
                      patch.object(loop,'_measurement_digest',side_effect=AssertionError('Fingerprint before preflight')) as digest,
                      patch.object(loop,'_save_json',side_effect=AssertionError('Write before preflight')) as save):
                    with self.assertRaisesRegex(ValueError,'overlap'):loop._dynamic_inputs(self.csv,False,{'id':'request'})
                    digest.assert_not_called();save.assert_not_called()
        self.assertEqual(self.csv.read_bytes(),original);self.assertEqual(self.checkpoint.read_bytes(),checkpoint)
        self.assertEqual(workspace.head(),head);self.assertEqual(index.read_bytes(),raw)
        self.assertFalse((area/'.inputs').exists());self.assertFalse(workspace.state_path.exists())
        self.factory.assert_not_called();self.robot.assert_not_called()

    def test_dynamic_input_exclusion_precedes_fingerprint_and_optional_tables_stay_optional(self):
        forbidden=self.root/'data/results/other/mas/.native/table.csv'
        forbidden.parent.mkdir(parents=True);forbidden.write_text('name,E,F\nSYNTHETIC,1,0.5\n')
        with patch.object(loop,'_measurement_digest',side_effect=AssertionError('Forbidden fingerprint')) as digest:
            with self.assertRaisesRegex(ValueError,'host/native'):loop._dynamic_inputs(forbidden,False,{'id':'bad-input'})
            digest.assert_not_called()
        empty=self.root/'data/empty.csv';empty.write_text('');missing=self.root/'data/missing.csv'
        before=self.csv.read_bytes()
        with patch.object(loop,'CSV_AGG',missing),patch.object(loop,'CSV_REPS',empty):
            inputs,sources=loop._dynamic_inputs(self.csv,False,{'id':'valid-input'})
        self.assertEqual(set(inputs),{'selected','provenance'});self.assertEqual(set(sources),{'selected'})
        self.assertEqual(inputs['selected'].read_bytes(),before);self.assertEqual(self.csv.read_bytes(),before)
        self.assertFalse(Path(sources['selected']['path']).is_absolute())
        with patch.object(loop,'LLM_AL_WARM_START_CSV',missing),self.assertRaises(FileNotFoundError):
            loop._dynamic_inputs(self.csv,True,{'id':'missing-warm'})

    def test_public_dynamic_callback_rejects_overlap_before_checkpoint_io(self):
        area=self.sdk.w.path(self.sdk.w.area);before=self.checkpoint.read_bytes();csv=self.csv.read_bytes()
        canary=self.root/'nested-native/canary.txt';canary.parent.mkdir();canary.write_bytes(b'SYNTHETIC_NONSECRET_CANARY')
        for variable in ('CODEX_HOME','CODEX_SQLITE_HOME'):
            for home in (area/'.inputs',canary.parent):
                environment={'CODEX_HOME':str(self.base/'external-home'),'CODEX_SQLITE_HOME':str(self.base/'external-sqlite'),variable:str(home)}
                with (self.subTest(variable=variable,home=str(home)),patch('pathlib.Path.home',return_value=self.base/'user-home'),
                      patch.dict(os.environ,environment),patch.object(loop,'_checkpoint_path',side_effect=AssertionError('Checkpoint before preflight')) as checkpoint,
                      patch.object(loop,'_save_json',side_effect=AssertionError('Write before preflight')) as save):
                    with self.assertRaisesRegex(ValueError,'overlap'):self.run_pipeline()
                    checkpoint.assert_not_called();save.assert_not_called()
        self.assertEqual(self.checkpoint.read_bytes(),before);self.assertEqual(self.csv.read_bytes(),csv)
        self.assertEqual(canary.read_bytes(),b'SYNTHETIC_NONSECRET_CANARY')
        self.factory.assert_not_called();self.robot.assert_not_called()

    def test_initial_progress_distinguishes_connected_request_validated_cache_and_error(self):
        self.csv.unlink()
        output, progress = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(progress):
            params = loop._new_campaign_params()
        self.assertEqual(params, {**PARAMS, **MATERIALS})
        self.assertIn('Requesting initial campaign decision', output.getvalue())
        self.assertIn('Saved RUN decision', output.getvalue())
        self.assertIn('Connecting SDK', progress.getvalue())
        calls, turns = self.factory.call_count, len(self.sdk.prompts)
        self.factory.side_effect = AssertionError('Cache must not construct a runtime client')
        output, progress = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(progress):
            self.assertEqual(loop._new_campaign_params(), params)
        self.assertIn('Reusing validated cached RUN', output.getvalue())
        self.assertNotIn('Connecting SDK', progress.getvalue())
        self.assertEqual((self.factory.call_count, len(self.sdk.prompts)), (calls, turns))
        path = self.csv.parent/'initial_suggestion.json'
        state = json.loads(path.read_text())
        state['next_params']['bath_temp'] = 8.0
        path.write_text(json.dumps(state))
        before = path.read_bytes()
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(ValueError):
            loop._new_campaign_params()
        self.assertIn('Initial decision request failed (ValueError)', output.getvalue())
        self.assertEqual(path.read_bytes(), before)
        self.robot.assert_not_called()
        self.health.assert_not_called()

    def test_continuing_progress_shows_request_then_cached_resume_without_new_sdk(self):
        self.health.side_effect = TimeoutError('Synthetic health interruption before submission')
        output, progress = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(progress), self.assertRaises(TimeoutError):
            self.run_pipeline()
        self.assertIn('[4/5] requesting MAS decision', output.getvalue())
        self.assertIn('Saved RUN decision', output.getvalue())
        self.assertIn('[ERROR]', output.getvalue())
        self.assertIn('Connecting SDK', progress.getvalue())
        calls, turns = self.factory.call_count, len(self.sdk.prompts)
        self.factory.side_effect = AssertionError('Restart must reuse the accepted decision')
        self.health.side_effect = None
        output, progress = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(progress):
            self.run_pipeline()
        self.assertIn('[4/5] requesting MAS decision', output.getvalue())
        self.assertIn('Reusing validated cached RUN', output.getvalue())
        self.assertNotIn('Connecting SDK', progress.getvalue())
        self.assertEqual((self.factory.call_count, len(self.sdk.prompts)), (calls, turns))
        self.robot.assert_called_once()
        self.assertEqual({k:v for k,v in self.robot.call_args.args[0].items() if k!='stock_metadata'},
                         self.state()['mas_decision']['next_params'])

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
        self.assertTrue((self.root/saved['mas_decision']['report_path']).is_file())
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
        warm = self.root/'data/warm.csv'
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
        pending = json.loads((self.workspace/'data/results/begins_test/mas/.mas-runtime.json').read_text())['active']
        self.sdk.action = 'run'
        self.run_pipeline()
        self.assertEqual(len(self.sdk.threads['main'].data.turns), native_count)
        self.assertEqual(self.state()['mas_decision']['runtime_operation_id'], pending)
        self.robot.assert_called_once()

    def test_new_measured_input_requires_explicit_review_and_preserves_old_snapshot(self):
        self.sdk.action = 'hold'
        self.run_pipeline()
        prior = self.state()['mas_decision']
        old = self.root/prior['inputs']['selected']['path']
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
        report = self.root/self.state()['mas_decision']['report_path']
        self.assertTrue(report.is_file())
        self.assertIn('Campaign decision: run', report.read_text())
        self.assertIn(report.relative_to(self.root).as_posix(), rows[0]['final_report'])
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
        with patch.object(loop, 'MAS_MATERIAL_KEY', None), self.assertRaisesRegex(ValueError, 'MAS_MATERIAL_KEY'):
            self.run_pipeline()
        with patch.object(loop, 'ITERATE_ADDITIVES', True), self.assertRaisesRegex(ValueError, 'fixed iteration'):
            self.run_pipeline()
        with patch.object(loop.master_processing, 'BRANCH_CONFIG', {}), self.assertRaisesRegex(ValueError, 'performance'):
            self.run_pipeline()
        self.factory.assert_not_called()
        self.robot.assert_not_called()

    def test_dynamic_repository_and_campaign_binding_is_independent_of_cwd(self):
        previous=Path.cwd();head=self.sdk.w.head()
        index=Path(self.sdk.w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
        before=index.read_bytes()
        try:
            for cwd in (self.root,self.base):
                os.chdir(cwd)
                workspace=loop._dynamic_workspace()
                self.assertEqual(workspace.root,self.root.resolve())
                self.assertEqual(workspace.campaign,self.csv.parent.name)
                self.assertEqual(workspace.material,'synthetic')
                self.assertEqual(workspace.area,f'data/results/{self.csv.parent.name}/mas')
            with patch.object(loop,'CSV_AGG_LLM',self.base/'foreign-campaign/llm.csv'),self.assertRaisesRegex(ValueError,'campaign'):
                loop._dynamic_workspace()
            with patch.object(loop,'MAS_MATERIAL_KEY','../invalid'),self.assertRaisesRegex(ValueError,'identifier'):
                loop._dynamic_workspace()
        finally:os.chdir(previous)
        self.assertEqual(self.sdk.w.head(),head);self.assertEqual(index.read_bytes(),before)
        self.factory.assert_not_called();self.robot.assert_not_called()

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

    def test_publication_conflict_blocks_initial_and_callback_dispatch_and_replay(self):
        native=Workspace.git
        for entry in ('initial','callback'):
            for phase in ('write-tree','update-ref'):
                with self.subTest(entry=entry,phase=phase):
                    case=RoutingTests('test_initial_campaign_without_history_uses_reviewed_theory_design');case.setUp()
                    try:
                        once=[True];original_csv=case.csv.read_bytes()
                        def intercepted(workspace,*args,**kwargs):
                            value=native(workspace,*args,**kwargs)
                            if args[0]==phase and once[0]:
                                once[0]=False;(workspace.root/'data/knowledge/synthetic/concentration.md').write_bytes(b'FOREIGN_CALLER_EDIT\n')
                            return value
                        call=loop._new_campaign_params if entry=='initial' else case.run_pipeline
                        with patch.object(Workspace,'git',intercepted),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(ValueError):call()
                        self.assertFalse(once[0]);case.robot.assert_not_called();case.health.assert_not_called()
                        self.assertEqual(case.csv.read_bytes(),original_csv);self.assertNotIn('mas_decision',case.state())
                        turns=len(case.sdk.prompts);starts=len(case.sdk.starts)
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(ValueError):call()
                        self.assertEqual(len(case.sdk.prompts),turns);self.assertEqual(len(case.sdk.starts),starts)
                        case.robot.assert_not_called();case.health.assert_not_called()
                        self.assertEqual(case.csv.read_bytes(),original_csv)
                    finally:case.doCleanups()

    def test_cached_run_waits_for_later_public_runtime_publication(self):
        for route in ('initial','callback'):
            for pending_kind in ('none','clean','foreign'):
                with self.subTest(route=route,pending=pending_kind):
                    case=RoutingTests('test_initial_campaign_without_history_uses_reviewed_theory_design');case.setUp()
                    try:
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                            if route=='initial':
                                case.csv.unlink();params=loop._new_campaign_params();caller=case.csv.parent/'initial_suggestion.json'
                            else:
                                case.health.side_effect=TimeoutError('Synthetic pause before submission')
                                with self.assertRaises(TimeoutError):case.run_pipeline()
                                params=case.state()['mas_decision']['next_params'];caller=case.checkpoint;case.health.side_effect=None
                        case.robot.assert_not_called()
                        original=json.loads(caller.read_text());request=original['mas_request'];decision=original['mas_decision']
                        self.assertEqual(decision['action'],'run');self.assertEqual(decision['next_params'],params)
                        w=Workspace(case.root,'begins_test','synthetic');head=w.head();sdk_factory=Mock(return_value=case.sdk)
                        conflict=None;expected=None
                        if pending_kind!='none':
                            case.sdk.w=w
                            runtime=CampaignRuntime(w,loop._dynamic_context(None if route=='initial' else 'condition-A'),sdk_factory=sdk_factory)
                            native=w.git
                            def interrupted(*args,**kwargs):
                                if args[0]=='commit-tree':raise RuntimeError('Synthetic interrupted later publication')
                                return native(*args,**kwargs)
                            with patch.object(w,'git',side_effect=interrupted),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaisesRegex(RuntimeError,'interrupted later publication'):
                                runtime.run(reconsideration='Later standalone approved inquiry',revision_id='later-standalone-review')
                            self.assertIsNotNone(w.state['pending']);self.assertEqual(w.head(),head)
                            later=w.state['operations'][runtime.last_operation_id]
                            self.assertEqual(later['revision_id'],'later-standalone-review');self.assertNotEqual(later['status'],'completed')
                            if pending_kind=='foreign':
                                relative=w.round_path(later)+'/decision.md';conflict=w.root/relative
                                expected=w.path(w.state['pending']['prepared'][relative]['snapshot']).read_bytes()
                                conflict.write_bytes(b'SYNTHETIC_FOREIGN_LATER_DECISION\n')
                                with w.lock(),self.assertRaisesRegex(ValueError,'Installed publication file changed'):w.recover_publication()
                        else:
                            with w.lock():self.assertIsNone(w.state['pending'])
                        journal=w.state_path.read_bytes();calls=case.factory.call_count;turns=len(case.sdk.prompts);sdk_calls=sdk_factory.call_count
                        case.factory.side_effect=AssertionError('Cached caller must not construct Runtime')
                        sdk_factory.side_effect=AssertionError('Receipt verification must not connect SDK')
                        case.robot.reset_mock();case.health.reset_mock()
                        def call():
                            if route=='initial':
                                self.assertEqual(loop._new_campaign_params(),params);loop._submit_dynamic_initial(params)
                            else:case.run_pipeline()
                        output,error=io.StringIO(),io.StringIO()
                        if pending_kind!='none':
                            try:
                                with redirect_stdout(output),redirect_stderr(error),self.assertRaisesRegex(ValueError,'pending publication'):call()
                            finally:
                                print('SYNTHETIC_CACHED_PENDING',json.dumps(dict(route=route,pending=pending_kind,
                                    health=case.health.call_count,device=case.robot.call_count,
                                    factory_delta=case.factory.call_count-calls,prompt_delta=len(case.sdk.prompts)-turns,
                                    validated_cache='Reusing validated cached RUN' in output.getvalue())))
                            case.health.assert_not_called();case.robot.assert_not_called()
                            self.assertNotIn('Reusing validated cached RUN',output.getvalue());self.assertNotIn('Saved RUN decision',output.getvalue())
                            if route=='initial':
                                with redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'pending publication'):loop._submit_dynamic_initial(params)
                            self.assertEqual(w.head(),head);self.assertEqual(w.state_path.read_bytes(),journal)
                            after=json.loads(caller.read_text());self.assertEqual(after['mas_request'],request);self.assertEqual(after['mas_decision'],decision)
                            self.assertEqual(after.get('submission'),original.get('submission'))
                            self.assertEqual(after.get('submission_request_id'),original.get('submission_request_id'))
                            self.assertEqual(case.factory.call_count,calls);self.assertEqual(sdk_factory.call_count,sdk_calls);self.assertEqual(len(case.sdk.prompts),turns)
                            if conflict is not None:self.assertEqual(conflict.read_bytes(),b'SYNTHETIC_FOREIGN_LATER_DECISION\n')
                            # Explicit operator resolution/recovery, separate from receipt verification.
                            with w.lock():
                                if conflict is not None:conflict.write_bytes(expected)
                                recovered=w.recover_publication();self.assertIsNotNone(recovered);self.assertIsNone(w.state['pending'])
                            self.assertEqual(sdk_factory.call_count,sdk_calls)
                            output,error=io.StringIO(),io.StringIO()
                        with redirect_stdout(output),redirect_stderr(error):call()
                        self.assertIn('Reusing validated cached RUN',output.getvalue());case.health.assert_called_once();case.robot.assert_called_once()
                        submitted=case.robot.call_args.kwargs['request_id'];self.assertTrue(submitted)
                        after=json.loads(caller.read_text());self.assertEqual(after['mas_request'],request);self.assertEqual(after['mas_decision'],decision)
                        self.assertEqual(case.factory.call_count,calls);self.assertEqual(sdk_factory.call_count,sdk_calls);self.assertEqual(len(case.sdk.prompts),turns)
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):call()
                        case.robot.assert_called_once();self.assertEqual(case.robot.call_args.kwargs['request_id'],submitted)
                    finally:case.doCleanups()

    def test_public_cold_closing_recovery_keeps_current_local_identity(self):
        for mode in ('first-publication','later-direct','knowledge-continuation','initial-first','callback-first'):
            with self.subTest(mode=mode):
                case=RoutingTests('test_initial_campaign_without_history_uses_reviewed_theory_design');case.setUp()
                try:
                    caller=None;params=None
                    w=Workspace(case.root,'begins_test','synthetic');case.sdk.w=w
                    factory=Mock(return_value=case.sdk)
                    context=loop._dynamic_context('condition-A' if mode=='callback-first' else None)
                    runtime=CampaignRuntime(w,context,sdk_factory=factory)
                    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                        if mode=='initial-first':
                            case.csv.unlink();params=loop._new_campaign_params();caller=case.csv.parent/'initial_suggestion.json'
                        elif mode=='callback-first':
                            case.health.side_effect=TimeoutError('Synthetic pause before submission')
                            with self.assertRaises(TimeoutError):case.run_pipeline()
                            case.health.side_effect=None;params=case.state()['mas_decision']['next_params'];caller=case.checkpoint
                        elif mode!='first-publication':self.assertIsNone(runtime.run())
                    if caller is not None:
                        caller_before=json.loads(caller.read_text());w=Workspace(case.root,'begins_test','synthetic');case.sdk.w=w
                        runtime=CampaignRuntime(w,context,sdk_factory=factory)
                        with w.lock():pass
                    if mode=='knowledge-continuation':
                        case.sdk.publish_next=True
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                            self.assertIsNone(runtime.run(observation_id='synthetic-continuation',inputs={'selected':case.csv}))
                        same_operation=runtime.last_operation_id
                    elif mode!='first-publication':
                        # Produce a real retained failure through the public mocked transport.
                        case.sdk.interrupt_once=True
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(TimeoutError):
                            runtime.run(reconsideration='Later public inquiry',revision_id='later-public-close')
                    old=w.state['publication_id'] if w.state is not None else None
                    before_ref=w.head();save=w.save;hit=[False]
                    def crash():
                        save()
                        if not hit[0] and w.state['pending'] is None and w.state['publication_id']!=old:
                            hit[0]=True;raise KeyboardInterrupt('Synthetic prospective journal stop')
                    with patch.object(w,'save',side_effect=crash),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(KeyboardInterrupt):runtime.run()
                    self.assertTrue(hit[0]);prospective=json.loads(w.state_path.read_text());self.assertIsNone(prospective['pending'])
                    active=json.loads((w.root/w.area/'.transactions/active.json').read_text());token=active['token'];self.assertNotEqual(token,old)
                    self.assertEqual(prospective['local_publication'],token);known=w.head();self.assertNotEqual(known,before_ref)
                    tx_path=w.root/w.area/'.transactions'/token/'transaction.json';tx=json.loads(tx_path.read_text())
                    intent=(tx_path.parent/'intent.json').read_bytes();scientific_before=json.loads(json.dumps(tx['before_state']))
                    self.assertEqual(scientific_before.get('local_publication'),old)
                    failures=prospective['failures'];old_history={k:v for k,v in scientific_before['operations'].items() if k!=tx['operation']}
                    if mode not in ('first-publication','knowledge-continuation'):self.assertTrue(failures)
                    index=Path(w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip());index_bytes=index.read_bytes()
                    self.assertEqual(w._entries(),w._entries('HEAD'))
                    calls=case.factory.call_count;sdk_calls=factory.call_count;turns=len(case.sdk.prompts)
                    case.factory.side_effect=AssertionError('No cached caller Runtime construction')
                    factory.side_effect=AssertionError('No SDK during known publication closure')
                    case.robot.reset_mock();case.health.reset_mock()
                    def coherent(cold):
                        self.assertEqual(cold.state['local_publication'],token)
                        self.assertEqual(cold.state['pending']['token'],token)
                        self.assertEqual(cold.state['publication_id'],scientific_before['publication_id'])
                        self.assertEqual(cold.state['failures'],failures)
                        self.assertEqual(cold.state['pending']['before_state'],scientific_before)
                        for identifier,value in old_history.items():self.assertEqual(cold.state['operations'][identifier],value)
                    if caller is not None:
                        call=loop._new_campaign_params if mode=='initial-first' else case.run_pipeline
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaisesRegex(ValueError,'pending publication'):call()
                        persisted=json.loads(w.state_path.read_text())
                        self.assertEqual(persisted['local_publication'],token);self.assertEqual(persisted['pending']['token'],token)
                        for repeat in range(2):
                            with Workspace(w.root,w.campaign,w.material).lock() as opened:coherent(opened)
                        after=json.loads(caller.read_text());self.assertEqual(after['mas_request'],caller_before['mas_request']);self.assertEqual(after['mas_decision'],caller_before['mas_decision'])
                    cold=Workspace(w.root,w.campaign,w.material);case.sdk.w=cold
                    if mode=='knowledge-continuation':self.assertEqual(tx['operation'],same_operation)
                    with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                        result=CampaignRuntime(cold,context,sdk_factory=factory).run()
                    self.assertEqual(cold.head(),known);self.assertEqual(index.read_bytes(),index_bytes)
                    self.assertIsNone(cold.state['pending']);self.assertEqual(cold.state['local_publication'],token)
                    self.assertEqual(cold.state['failures'],failures);self.assertEqual((tx_path.parent/'intent.json').read_bytes(),intent)
                    self.assertEqual(json.loads(tx_path.read_text())['before_state'],scientific_before)
                    self.assertEqual(cold.git('rev-list','--count',before_ref+'..HEAD').stdout.strip(),b'1')
                    for identifier,value in old_history.items():self.assertEqual(cold.state['operations'][identifier],value)
                    self.assertEqual(case.factory.call_count,calls);self.assertEqual(factory.call_count,sdk_calls);self.assertEqual(len(case.sdk.prompts),turns)
                    case.health.assert_not_called();case.robot.assert_not_called()
                    for repeat in range(2):
                        reopened=Workspace(w.root,w.campaign,w.material);case.sdk.w=reopened
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                            self.assertEqual(CampaignRuntime(reopened,context,sdk_factory=factory).run(),result)
                        self.assertIsNone(reopened.state['pending']);self.assertEqual(reopened.state['local_publication'],token)
                    self.assertEqual(factory.call_count,sdk_calls);self.assertEqual(len(case.sdk.prompts),turns)
                    if caller is not None:
                        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
                            if mode=='initial-first':self.assertEqual(loop._new_campaign_params(),params);loop._submit_dynamic_initial(params)
                            else:case.run_pipeline()
                        case.robot.assert_called_once();case.health.assert_called_once()
                        after=json.loads(caller.read_text());self.assertEqual(after['mas_request'],caller_before['mas_request']);self.assertEqual(after['mas_decision'],caller_before['mas_decision'])
                    print('SYNTHETIC_COLD_LOCAL_IDENTITY',json.dumps(dict(mode=mode,old=old,current=token,ref_preserved=cold.head()==known,index_preserved=index.read_bytes()==index_bytes,sdk_delta=factory.call_count-sdk_calls,prompt_delta=len(case.sdk.prompts)-turns)))
                finally:case.doCleanups()

    def test_public_cold_closing_rejects_foreign_local_pointer_unchanged(self):
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):params=loop._new_campaign_params()
        caller=self.csv.parent/'initial_suggestion.json';caller_before=json.loads(caller.read_text())
        w=Workspace(self.root,'begins_test','synthetic');self.sdk.w=w;factory=Mock(return_value=self.sdk)
        runtime=CampaignRuntime(w,loop._dynamic_context(None),sdk_factory=factory)
        with w.lock():old=w.state['publication_id']
        save=w.save;hit=[False]
        def substituted_writer():
            if not hit[0] and w.state['pending'] is None and w.state['publication_id']!=old:
                # Deliberate wrong-producer fault, never a repair of the reproduction journal.
                hit[0]=True;w.state['local_publication']='synthetic-foreign-pointer';save()
                raise KeyboardInterrupt('Synthetic foreign local identity')
            return save()
        with patch.object(w,'save',side_effect=substituted_writer),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaises(KeyboardInterrupt):
            runtime.run(reconsideration='Later identity rejection control',revision_id='foreign-pointer-control')
        self.assertTrue(hit[0]);journal=w.state_path.read_bytes();head=w.head()
        index=Path(w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip());raw=index.read_bytes()
        calls=self.factory.call_count;sdk_calls=factory.call_count;turns=len(self.sdk.prompts)
        factory.side_effect=AssertionError('No SDK on foreign identity');self.factory.side_effect=AssertionError('No Runtime cache replacement')
        self.health.reset_mock();self.robot.reset_mock()
        for repeat in range(2):
            with self.assertRaisesRegex(ValueError,'Local publication pointer differs'):
                with Workspace(self.root,'begins_test','synthetic').lock():self.fail('Foreign pointer accepted')
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),self.assertRaisesRegex(ValueError,'Local publication pointer differs'):
            CampaignRuntime(Workspace(self.root,'begins_test','synthetic'),loop._dynamic_context(None),sdk_factory=factory).run()
        with redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'Local publication pointer differs'):loop._submit_dynamic_initial(params)
        self.assertEqual(w.state_path.read_bytes(),journal);self.assertEqual(index.read_bytes(),raw);self.assertEqual(w.head(),head)
        self.assertEqual(json.loads(caller.read_text()),caller_before);self.assertEqual(self.factory.call_count,calls)
        self.assertEqual(factory.call_count,sdk_calls);self.assertEqual(len(self.sdk.prompts),turns);self.health.assert_not_called();self.robot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
