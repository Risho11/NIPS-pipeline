"""Synthetic native SDK-shaped collaboration; never construct a real SDK client."""
from dataclasses import dataclass
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from jinja2 import Template, UndefinedError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
from openai_codex._run import TurnResult
from openai_codex import MethodNotFoundError
from openai_codex.generated.v2_all import Thread, ThreadReadResponse, Turn
from mas_contract import Adoption, Context, Contribution, Decision, MainReply, Review, TOPICS
from mas_runtime import CampaignRuntime, isolated_sdk, main
from mas_workspace import Workspace
from test_mas_contract import CONTEXT, PARAMS
from test_mas_workspace import project


def profile_denies(filesystem, path):
    """Flat braces/full-path globs; only literal directory rules inherit to children.

    This declaration oracle follows the separately calibrated distinction. Actual
    pinned sandbox checks remain required; glob ancestors are never treated as proof.
    """
    for rule, mode in filesystem.items():
        if mode != 'deny':continue
        prefix, brace, rest = rule.partition('{')
        if brace:
            choices, tail = rest.split('}', 1)
            patterns = [prefix + choice + tail for choice in choices.split(',')]
        else:patterns = [rule]
        for pattern in patterns:
            pattern_path = Path(pattern)
            if pattern_path.name == '**':
                prefix = pattern_path.parent
                prefix_size = len(prefix.parts)
                if len(path.parts) > prefix_size and Path(*path.parts[:prefix_size]).match(str(prefix)):
                    return True
            elif path.match(pattern):
                return True
            if not any(c in pattern for c in '*?[') and Path(pattern) in path.parents:return True
    return False


@dataclass
class FakeThread:
    sdk: 'FakeCodex'
    data: Thread

    @property
    def id(self):
        return self.data.id

    def read(self, *, include_turns=False):
        self.sdk.reads.append((self.id, include_turns))
        if include_turns and not self.data.turns:
            self.sdk.empty_reads.append((self.id, include_turns))
        if self.sdk.reject_empty_history and include_turns and not self.data.turns:
            raise MethodNotFoundError(-32601, 'list_turns is not supported yet')
        return ThreadReadResponse(thread=self.data)

    def turn(self, prompt, *, output_schema):
        self.sdk.prompts.append(prompt)
        self.sdk.schemas.append(output_schema)
        if self.data.turns and self.data.turns[-1].status.value == 'inProgress':
            pending = self.data.turns[-1]
        else:
            pending = Turn.model_validate(dict(id=f'turn-{len(self.data.turns)}', status='inProgress',
                items=[dict(type='userMessage', id='input', content=[dict(type='text', text=prompt)])]))
            self.data.turns.append(pending)
        return FakeHandle(self, pending)


@dataclass
class FakeHandle:
    thread: FakeThread
    pending: Turn

    @property
    def id(self):
        return self.pending.id

    def run(self):
        sdk = self.thread.sdk
        if sdk.interrupt_once:
            sdk.interrupt_once = False
            raise TimeoutError('synthetic transport interruption')
        if sdk.failed_once:
            sdk.failed_once = False
            self.pending.status = type(self.pending.status)('failed')
            return sdk.result(self.pending, None)
        reply, event = sdk.reply()
        text = json.dumps(reply)
        items = [i.model_dump(mode='json', by_alias=True) for i in self.pending.items]
        if event:
            items.extend(event if isinstance(event, list) else [event])
        items.append(dict(type='agentMessage', id='main-final', phase='final_answer', text=text))
        finished = Turn.model_validate(dict(id=self.id, status='completed', items=items))
        self.thread.data.turns[-1] = finished
        if sdk.hook:
            sdk.hook()
        if sdk.lose_completion_once:
            sdk.lose_completion_once = False
            raise TimeoutError('synthetic lost completion')
        return sdk.result(finished, text)


class FakeCodex:
    """Fake transport; actual generated Thread/Turn/ThreadItem validate all fixtures."""
    def __init__(self, workspace):
        self.w = workspace
        self.threads = {}
        self.starts, self.resumes, self.prompts, self.schemas = [], [], [], []
        self.reads = []
        self.empty_reads = []
        self.modern = True
        self.absolute_paths = True
        self.stream_activity = False
        self.uuid_refs = self.mixed_paths = False
        self.remap_alias = self.duplicate_alias = self.unobserved_ref = False
        self.interrupted_activity = self.shared_report = False
        self.legacy_message_drift = False
        self.reject_empty_history = False
        self.action = 'run'
        self.publish_next = False
        self.interrupt_once = self.lose_completion_once = self.failed_once = False
        self.bad_role = self.bad_parent = self.same_actor = self.no_event = False
        self.reject_review = self.drift_conditions = self.bad_boolean = self.stale_receipt = False
        self.incomplete_review = self.failed_review_turn = False
        self.escape_record = False
        self.bootstrap_hold = False
        self.bootstrap_action = 'hold'
        self.close_reviewers = False
        self.hook = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def native_thread(self, identifier, role=None, parent=None):
        data = Thread.model_validate(dict(id=identifier, agentRole=role, parentThreadId=parent,
            cliVersion='0.163.0', createdAt=0, updatedAt=0, cwd=str(self.w.path(self.w.attempt_path(self.w.state['operations'][self.w.state['active']]))),
            ephemeral=False, modelProvider='openai', sessionId='synthetic', source='exec',
            status={'type': 'idle'}, preview='', turns=[]))
        fake = FakeThread(self, data)
        self.threads[identifier] = fake
        return fake

    def thread_start(self, **kwargs):
        self.starts.append(kwargs)
        return self.native_thread('main' if len(self.starts)==1 else 'main-'+str(len(self.starts)))

    def thread_resume(self, identifier, **kwargs):
        self.resumes.append((identifier, kwargs))
        if 'cwd' in kwargs:self.threads[identifier].data.cwd=kwargs['cwd']
        return self.threads[identifier]

    def identifier(self, kind, role):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, 'synthetic-native:' + self.w.campaign + ':' + kind + ':' + role))

    def result(self, turn, text):
        # Public collector uses item-completed events; hydrated Turn.items can
        # additionally contain native activity not present in that live stream.
        items = turn.items
        if self.modern and not self.stream_activity:
            items = [i for i in items if i.root.type != 'subAgentActivity']
        return TurnResult(id=turn.id, status=turn.status, error=None, started_at=0,
            completed_at=1, duration_ms=1000, final_response=text, items=items, usage=None)

    def reply(self):
        state = self.w.state
        record = state['operations'][state['active']]
        knowledge = record['kind'] == 'bootstrap' or self.publish_next
        kind = 'knowledge' if knowledge else 'design'
        base = self.w.round_path(record) + '/attempt-' + str(len(record['turns']))
        if (not knowledge and self.action != 'run') or (knowledge and self.bootstrap_hold):
            decision = Decision(action=self.bootstrap_action if self.bootstrap_hold else self.action,
                reason='Synthetic bounded decision', next_params=None, knowledge_commit=state['knowledge_commit'])
            return MainReply(knowledge=None, design=None, decision=decision, records=[]).model_dump(mode='json'), None
        self.publish_next = False
        def artifact(relative):
            return str(self.w.path(relative)) if self.absolute_paths else relative
        files = {topic: f'{base}/author/{topic}' for topic in TOPICS} if knowledge else {}
        for topic, relative in files.items():
            self.w.write(relative, f'Synthetic {topic} physical reasoning and honest limits.\n')
        report, review_path = f'{base}/author/{kind}.md', f'{base}/review/{kind}.md'
        self.w.write(report, 'Synthetic authored reasoning; no real measurements.\n')
        self.w.write(review_path, 'Synthetic independent review and actual limits.\n')
        author_id, qa_id = self.identifier(kind, 'author'), self.identifier(kind, 'qa')
        author_path, qa_path = f'/root/{kind}_author', f'/root/{kind}_qa'
        author_ref = author_id if self.uuid_refs or not self.modern else author_path
        qa_ref = qa_id if self.uuid_refs or not self.modern else qa_path
        operation_id = 'stale' if self.stale_receipt else record['id']
        author = Contribution(operation_id=operation_id, kind=kind,
            files={t:artifact(p) for t,p in files.items()}, conditions=None if knowledge else PARAMS,
            knowledge_commit=None if knowledge else state['knowledge_commit'], report_path=artifact(report))
        review = Review(**author.model_dump(), verdict='fail' if self.reject_review else 'pass',
                        author_thread_id=author_ref).model_copy(update={'report_path':artifact(review_path)})
        author_payload, review_payload = author.model_dump(mode='json'), review.model_dump(mode='json')
        if self.mixed_paths:
            review_payload['files'] = files
            review_payload['report_path'] = review_path
        if self.shared_report:
            review_payload['report_path'] = report
        if self.drift_conditions and not knowledge:
            review_payload['conditions']['bath_temp'] = 8
        if self.bad_boolean and not knowledge:
            review_payload['conditions']['pullcast_speed'] = True
        native_messages, activities = {}, []
        for identifier, path, role, payload in [
            (author_id, author_path, 'hypothesis-updater' if knowledge else 'experiment-designer', author_payload),
            (qa_id, qa_path, 'hypothesis-qa' if knowledge else 'experiment-design-qa', review_payload)]:
            reused = identifier in self.threads
            child = self.threads.get(identifier) or self.native_thread(identifier, role, self.w.state['thread_id'])
            if identifier == qa_id and self.bad_role:
                child.data.agent_role = 'hypothesis-updater'
            if identifier == qa_id and self.bad_parent:
                child.data.parent_thread_id = 'unrelated-main'
            text = json.dumps(payload)
            child.data.turns.append(Turn.model_validate(dict(id=f'child-{len(child.data.turns)}', status='completed',
                items=[dict(type='agentMessage', id='final', phase='final_answer', text=text)])))
            native_messages[identifier] = dict(status='completed', message=text)
            initial = dict(type='subAgentActivity', id='opaque-initial-' + identifier,
                           agentPath=path, agentThreadId=identifier, kind='interacted' if reused else 'started')
            activities.append(initial)
            if not (identifier == qa_id and self.incomplete_review):
                activities.append(dict(initial, id='opaque-completion-' + identifier,
                    kind='interrupted' if self.interrupted_activity else 'completed'))
        if self.incomplete_review:
            native_messages[qa_id]['status'] = 'running'
        if self.failed_review_turn:
            child = self.threads[qa_id]
            child.data.turns[-1].status = type(child.data.turns[-1].status)('failed')
        if self.remap_alias:
            activities.append(dict(activities[0], agentThreadId=self.identifier('foreign', 'author')))
        if self.duplicate_alias:
            activities.append(dict(activities[0], agentPath='/root/alias_of_author'))
        adoption = Adoption(author_thread_id='/root/unobserved' if self.unobserved_ref else author_ref,
                            reviewer_thread_id=author_ref if self.same_actor else qa_ref)
        decision = None if knowledge else Decision(action='run', next_params=PARAMS,
            reason='Synthetic question, not an optimum', knowledge_commit=state['knowledge_commit'])
        main_record = f'{base}/main.md'
        self.w.write(main_record, 'Synthetic Main adoption reasoning and records.\n')
        records = [artifact(main_record)]
        if self.escape_record:
            raw = f'{base}/inputs/raw.md'
            self.w.write(raw, 'Must never be tracked.\n')
            records = [artifact(raw)]
        reply = MainReply(knowledge=adoption if knowledge else None,
                         design=None if knowledge else adoption, decision=decision, records=records)
        if self.legacy_message_drift:
            native_messages[qa_id]['message'] = json.dumps(dict(review_payload, operation_id='foreign'))
        event = dict(type='collabAgentToolCall', id='observed', tool='wait', status='completed',
            senderThreadId=state['thread_id'], receiverThreadIds=[] if self.modern else list(native_messages),
            agentsStates={} if self.modern else native_messages)
        events = [*activities, event] if self.modern else [event]
        if self.close_reviewers:
            events.append(dict(event, id='close', tool='closeAgent',
                agentsStates={k:dict(status='shutdown',message=v['message']) for k,v in native_messages.items()}))
        return reply.model_dump(mode='json'), None if self.no_event else events


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        source = project(self.base / 'project with spaces 한글')
        self.w = Workspace(source, CONTEXT['campaign'], 'synthetic')
        self.baseline_head = self.w.head()
        self.sdk = FakeCodex(self.w)
        self.factory = unittest.mock.Mock(return_value=self.sdk)
        self.runtime = CampaignRuntime(self.w, Context.model_validate(CONTEXT), sdk_factory=self.factory)
        self.input = self.w.root / 'data/raw/synthetic.csv'
        self.input.parent.mkdir(parents=True, exist_ok=True)
        self.input.write_text('name,E,F\nSYNTHETIC,1,0.5\n')

    def prepare_sdk(self):
        with self.w.lock():
            self.runtime._operation(None, None, None)
            self.runtime._bindings()

    def bootstrap(self):
        self.assertIsNone(self.runtime.run())
        return self.w.state['knowledge_commit']

    def test_main_template_is_plaintext_module_relative_and_separates_observations(self):
        self.w.state = {'knowledge_commit': None}
        record = dict(id='synthetic-render', campaign='synthetic', turns=['prior'], kind='bootstrap',
            reason='한글 {braces} "quotes" <&>', context=CONTEXT, inputs={'selected': {'path':'/data with spaces/한글.csv'}})
        before = self.runtime._prompt(record)
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            self.assertEqual(self.runtime._prompt(record), before)
        finally:
            os.chdir(previous)
        self.assertTrue(before.endswith('\n'))
        self.assertIn('reason: 한글 {braces} "quotes" <&>', before)
        self.assertIn('attempt-1', before)
        self.assertIn('BOOTSTRAP: theory/provenance only before outcomes', before)
        self.assertNotIn('/data with spaces/', before)
        record['kind'] = 'observation'
        observed = self.runtime._prompt(record)
        self.assertIn('Authorized observations (do not modify): ' + json.dumps(record['inputs']), observed)
        self.assertNotIn('BOOTSTRAP:', observed)
        self.assertIn('"properties"', observed)
        self.factory.assert_not_called()

    def test_actual_template_rejects_missing_render_variables(self):
        self.w.state = {'knowledge_commit': None}
        record = dict(id='synthetic-render', campaign='synthetic', turns=[], kind='bootstrap',
                      reason=None, context=CONTEXT, inputs={})
        render = Template.render
        def missing_identifier(template, *args, **values):
            values.pop('operation_id')
            return render(template, *args, **values)
        with patch.object(Template, 'render', new=missing_identifier):
            with self.assertRaises(UndefinedError):
                self.runtime._prompt(record)
        self.factory.assert_not_called()

    def test_progress_reports_knowledge_only_after_actual_git_publication(self):
        output, progress = io.StringIO(), io.StringIO()
        publish = self.w.publish
        def publish_checked(*args, **kwargs):
            self.assertNotIn('Knowledge published', progress.getvalue())
            result = publish(*args, **kwargs)
            self.assertEqual(self.w.head(), self.w.state['knowledge_commit'])
            return result
        with redirect_stdout(output), redirect_stderr(progress), patch.object(self.w, 'publish', side_effect=publish_checked):
            commit = self.bootstrap()
        self.assertEqual(output.getvalue(), '')
        self.assertIn('Connecting SDK', progress.getvalue())
        self.assertIn('Starting Main session', progress.getvalue())
        self.assertIn('Knowledge published at ' + commit, progress.getvalue())
        self.assertNotIn(self.sdk.prompts[0], progress.getvalue())

    def test_progress_final_actions_and_validated_cache_do_not_claim_sdk_work(self):
        self.bootstrap()
        for action in ('run', 'hold', 'stop'):
            with self.subTest(action=action):
                self.sdk.action = action
                progress = io.StringIO()
                with redirect_stderr(progress):
                    decision = self.runtime.run(reconsideration='Synthetic ' + action + ' review', revision_id='review-' + action)
                self.assertEqual(decision.action, action)
                record = self.w.state['operations'][self.w.state['active']]
                self.assertEqual(record['status'], 'completed')
                self.assertEqual(record['commit'], self.w.head())
                self.assertIn('Resuming Main session', progress.getvalue())
                self.assertIn('Accepted final action: ' + action.upper(), progress.getvalue())
                calls, turns = self.factory.call_count, len(self.sdk.prompts)
                progress = io.StringIO()
                with redirect_stderr(progress):
                    self.assertEqual(self.runtime.run(), decision)
                self.assertIn('Reusing validated cached ' + action.upper(), progress.getvalue())
                self.assertNotIn('Connecting SDK', progress.getvalue())
                self.assertNotIn('Resuming Main', progress.getvalue())
                self.assertEqual((self.factory.call_count, len(self.sdk.prompts)), (calls, turns))

    def test_failed_adoption_and_git_publication_never_log_success_and_recovery_avoids_sdk(self):
        self.sdk.no_event = True
        progress = io.StringIO()
        with redirect_stderr(progress), self.assertRaises(ValueError):
            self.runtime.run()
        self.assertIn('Request failed', progress.getvalue())
        self.assertNotIn('Knowledge published', progress.getvalue())
        self.assertNotIn('Accepted final action', progress.getvalue())
        self.sdk.no_event = False
        git = self.w.git
        def fail_commit(*args, **kwargs):
            if args[0] == 'commit-tree':
                raise RuntimeError('Synthetic private error detail that must not be printed')
            return git(*args, **kwargs)
        progress = io.StringIO()
        with redirect_stderr(progress), patch.object(self.w, 'git', side_effect=fail_commit):
            with self.assertRaises(RuntimeError):
                self.runtime.run(retry=True)
        self.assertEqual(self.w.head(), self.baseline_head)
        self.assertIsNotNone(self.w.state['pending'])
        self.assertIn('Request failed', progress.getvalue())
        self.assertNotIn('Knowledge published', progress.getvalue())
        self.assertNotIn('private error detail', progress.getvalue())
        calls = self.factory.call_count
        self.factory.side_effect = AssertionError('No SDK during accepted publication recovery')
        progress = io.StringIO()
        with redirect_stderr(progress):
            self.assertIsNone(self.runtime.run())
        self.assertIsNone(self.w.state['pending'])
        self.assertIsNotNone(self.w.state['knowledge_commit'])
        self.assertIn('Recovered knowledge publication at ' + self.w.head(), progress.getvalue())
        self.assertNotIn('Connecting SDK', progress.getvalue())
        self.assertEqual(self.factory.call_count, calls)

    def test_cli_real_mocked_runtime_keeps_terminal_json_on_stdout_and_progress_on_stderr(self):
        context = self.base/'context.json'
        context.write_text(json.dumps(CONTEXT))
        args = ['--repo',str(self.w.root),
                '--material','synthetic','--context',str(context),'--live']
        def client(workspace):
            self.sdk.w = workspace
            return self.sdk
        with patch('mas_runtime.isolated_sdk', side_effect=client) as factory:
            output, progress = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(progress):
                main(args)
            self.assertEqual(json.loads(output.getvalue()), {'status':'knowledge_published'})
            self.assertIn('Knowledge published', progress.getvalue())
            observed = args + ['--observation-id','synthetic-cli','--input','table=' + str(self.input)]
            output, progress = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(progress):
                main(observed)
            decision = json.loads(output.getvalue())
            self.assertEqual(decision['action'], 'run')
            self.assertEqual(decision['next_params'], PARAMS)
            self.assertIn('Accepted final action: RUN', progress.getvalue())
            calls, turns = factory.call_count, len(self.sdk.prompts)
            factory.side_effect = AssertionError('Cached CLI must not connect')
            output, progress = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(progress):
                main(observed)
            self.assertEqual(json.loads(output.getvalue()), decision)
            self.assertIn('Reusing validated cached RUN', progress.getvalue())
            self.assertNotIn('Connecting SDK', progress.getvalue())
            self.assertEqual((factory.call_count, len(self.sdk.prompts)), (calls, turns))

    def test_modern_absolute_receipts_publish_canonical_paths_and_resolved_native_ids(self):
        self.sdk.mixed_paths = True
        self.bootstrap()
        state = self.w.state
        record = state['operations'][state['active']]
        receipt = json.loads(self.w.git('show', f"HEAD:{self.w.round_path(record)}/adoption.json").stdout)
        adoption = receipt['adoption']['knowledge']
        self.assertEqual(adoption['author_thread_id'], self.sdk.identifier('knowledge','author'))
        self.assertEqual(receipt['review']['author_thread_id'], adoption['author_thread_id'])
        for path in [*receipt['author']['files'].values(), receipt['author']['report_path'],
                     receipt['review']['report_path'], *receipt['adoption']['records']]:
            self.assertFalse(Path(path).is_absolute())
            self.assertTrue(path.startswith(self.w.round_path(record) + '/attempt-0/'))
        self.assertEqual(receipt['native_review']['author']['thread_id'], adoption['author_thread_id'])

    def test_modern_relative_receipts_reuse_observed_sessions_without_new_started_event(self):
        self.sdk.absolute_paths = False
        self.bootstrap()
        self.sdk.publish_next = True
        self.assertIsNone(self.observe())
        turn = self.sdk.threads['main'].data.turns[-1]
        kinds = [item.root.kind.value for item in turn.items if item.root.type=='subAgentActivity']
        self.assertNotIn('started', kinds)
        self.assertIn('completed', kinds)
        self.assertEqual(self.runtime.run().action, 'run')

    def test_observed_uuid_refs_and_legacy_completed_messages_remain_supported(self):
        self.sdk.uuid_refs = True
        self.bootstrap()
        self.sdk.modern = False
        self.assertEqual(self.observe().action, 'run')

    def test_legacy_message_drift_cannot_be_hidden_by_public_child_completion(self):
        self.sdk.modern = False
        self.sdk.legacy_message_drift = True
        with self.assertRaisesRegex(ValueError, 'changed after Main'):
            self.runtime.run()
        self.assertEqual(self.w.head(), self.baseline_head)
        self.sdk.legacy_message_drift = False
        self.assertIsNone(self.runtime.run(retry=True))

    def test_native_participant_ambiguity_and_nonindependent_records_block_publication(self):
        for flag in ('remap_alias', 'duplicate_alias', 'unobserved_ref',
                     'interrupted_activity', 'shared_report'):
            with self.subTest(flag=flag):
                setattr(self.sdk, flag, True)
                with self.assertRaises(ValueError):
                    self.runtime.run(retry=True)
                self.assertEqual(self.w.head(), self.baseline_head)
                self.assertIsNone(self.w.state['knowledge_commit'])
                setattr(self.sdk, flag, False)
        self.assertIsNone(self.runtime.run(retry=True))

    def test_modern_latest_child_and_operational_receipt_must_match(self):
        reply = self.sdk.reply
        for defect in ('main_uuid', 'active_child', 'later_incomplete_turn', 'wrong_kind',
                       'wrong_author', 'wrong_knowledge', 'wrong_mapping'):
            with self.subTest(defect=defect):
                def corrupt():
                    value, events = reply()
                    qa = self.sdk.threads[self.sdk.identifier('knowledge', 'qa')].data
                    item = qa.turns[-1].items[-1].root
                    receipt = json.loads(item.text)
                    if defect == 'main_uuid':
                        value['knowledge']['author_thread_id'] = 'main'
                        events.append(dict(type='subAgentActivity', id='opaque-self',
                            agentPath='/root/self', agentThreadId='main', kind='completed'))
                    elif defect == 'active_child':
                        qa.status = type(qa.status).model_validate(dict(type='active', activeFlags=[]))
                    elif defect == 'later_incomplete_turn':
                        qa.turns.append(Turn.model_validate(dict(id='unknown-latest', status='interrupted', items=[])))
                    elif defect == 'wrong_kind':
                        receipt['kind'] = 'design'
                    elif defect == 'wrong_author':
                        receipt['author_thread_id'] = '/root/knowledge_qa'
                    elif defect == 'wrong_knowledge':
                        receipt['knowledge_commit'] = 'unobserved-knowledge'
                    else:
                        receipt['files'][TOPICS[0]] = receipt['files'][TOPICS[1]]
                    item.text = json.dumps(receipt)
                    return value, events
                with patch.object(self.sdk, 'reply', side_effect=corrupt):
                    with self.assertRaises(ValueError):
                        self.runtime.run(retry=True)
                self.assertEqual(self.w.head(), self.baseline_head)
                qa = self.sdk.threads[self.sdk.identifier('knowledge', 'qa')].data
                qa.status = type(qa.status).model_validate(dict(type='idle'))
        self.assertIsNone(self.runtime.run(retry=True))

    def test_artifact_normalization_keeps_attempt_escape_and_regular_file_guards(self):
        record = dict(id='synthetic-paths', campaign='synthetic', turns=['previous'])
        base = self.w.round_path(record)
        good = base + '/attempt-1/report.md'
        self.w.write(good, 'Synthetic current-attempt report.\n')
        for reference in (good, str(self.w.path(good))):
            self.assertEqual(self.runtime._artifact(record, reference), good)
        bad = [str(self.input), str(self.w.root / 'README.md'),
               base + '/attempt-1/../attempt-1/report.md']
        for relative in (base + '/attempt-0/old.md', base + '/attempt-1/raw/report.md',
                         base + '/attempt-1/cache/report.md'):
            self.w.write(relative, 'Preserved excluded report.\n')
            bad.extend((relative, str(self.w.path(relative))))
        symlink, hardlink = self.w.root / base / 'attempt-1/symlink.md', self.w.root / base / 'attempt-1/hardlink.md'
        symlink.symlink_to(self.input)
        os.link(self.input, hardlink)
        bad.extend((str(symlink), str(hardlink)))
        for reference in bad:
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                self.runtime._artifact(record, reference)
        self.assertEqual(self.input.read_text(), 'name,E,F\nSYNTHETIC,1,0.5\n')

    def test_parent_history_is_hydrated_before_child_reads_and_detects_stream_drift(self):
        native_read = FakeThread.read
        def read(thread, *, include_turns=False):
            if thread.id != 'main':
                self.assertIn(('main', True), self.sdk.reads)
            result = native_read(thread, include_turns=include_turns)
            if thread.id == 'main' and thread.data.turns:
                result = result.model_copy(deep=True)
                result.thread.turns[-1].items[-1].root.text = '{}'
            return result
        with patch.object(FakeThread, 'read', new=read):
            with self.assertRaisesRegex(ValueError, 'between stream and history'):
                self.runtime.run()
        self.assertEqual(self.w.head(), self.baseline_head)
        self.assertEqual(self.sdk.reads, [('main', True)])
        self.assertIsNone(self.runtime.run())

    def test_main_records_cannot_publish_another_attempt(self):
        reply = self.sdk.reply
        def wrong_record():
            value, events = reply()
            record = self.w.state['operations'][self.w.state['active']]
            other = self.w.round_path(record) + '/attempt-99/main.md'
            self.w.write(other, 'Synthetic report from another attempt.\n')
            value['records'] = [str(self.w.path(other))]
            return value, events
        with patch.object(self.sdk, 'reply', side_effect=wrong_record):
            with self.assertRaisesRegex(ValueError, 'Current attempt'):
                self.runtime.run()
        self.assertEqual(self.w.head(), self.baseline_head)

    def observe(self):
        return self.runtime.run(observation_id='synthetic1', inputs={'table': self.input})

    def cold(self):
        self.w = Workspace(self.w.root, self.w.campaign, 'synthetic')
        self.sdk.w = self.w
        self.runtime = CampaignRuntime(self.w, CONTEXT, sdk_factory=self.factory)

    def test_bootstrap_gates_reveal_and_commits_native_reviewed_knowledge(self):
        with self.assertRaisesRegex(ValueError, 'bootstrap'):
            self.observe()
        self.factory.assert_not_called()
        initial = self.input.read_bytes()
        commit = self.bootstrap()
        self.assertNotIn(str(self.input), self.sdk.prompts[0])
        self.assertIn('BOOTSTRAP', self.sdk.prompts[0])
        self.assertEqual(len(self.sdk.starts), 1)
        self.assertFalse(any('model' in options for options in self.sdk.starts))
        decision = self.observe()
        self.assertEqual(decision.action, 'run')
        self.assertEqual(decision.next_params.model_dump(), PARAMS)
        self.assertEqual(decision.knowledge_commit, commit)
        self.assertIn(self.w.relative(self.input), self.sdk.prompts[-1])
        self.assertNotIn(str(self.input), self.sdk.prompts[-1])
        self.assertEqual(self.input.read_bytes(), initial)
        native_files = self.w.git('ls-files').stdout.decode()
        self.assertIn('/review/design.md', native_files)
        self.assertIn('/author/knowledge.md', native_files)
        self.assertNotIn('synthetic.csv', native_files)

    def test_observed_completion_remains_valid_after_native_close(self):
        self.sdk.close_reviewers = True
        self.bootstrap()
        self.assertEqual(self.observe().action, 'run')

    def test_fresh_empty_main_skips_unsupported_history_without_weakening_native_review(self):
        self.sdk.reject_empty_history = True
        native_turn, native_run = FakeThread.turn, FakeHandle.run
        def turn(thread, prompt, *, output_schema):
            saved = json.loads(self.w.state_path.read_text())
            self.assertEqual(saved['thread_id'], thread.id)
            return native_turn(thread, prompt, output_schema=output_schema)
        def run(handle):
            saved = json.loads(self.w.state_path.read_text())
            operation = saved['operations'][saved['active']]
            self.assertEqual(saved['thread_id'], handle.thread.id)
            self.assertEqual(operation['turn_id'], handle.id)
            return native_run(handle)
        with patch.object(FakeThread, 'turn', new=turn), patch.object(FakeHandle, 'run', new=run):
            self.bootstrap()
        self.assertNotIn(('main', True), self.sdk.empty_reads)
        self.assertIn((self.sdk.identifier('knowledge', 'author'), True), self.sdk.reads)
        self.assertIn((self.sdk.identifier('knowledge', 'qa'), True), self.sdk.reads)
        self.assertEqual(len(self.sdk.starts), 1)
        self.assertIsNotNone(self.w.state['knowledge_commit'])
        # A later call must read the existing, now nonempty native Main history.
        self.assertEqual(self.observe().action, 'run')
        self.assertIn(('main', True), self.sdk.reads)
        self.assertIn((self.sdk.identifier('design', 'author'), True), self.sdk.reads)
        self.assertIn((self.sdk.identifier('design', 'qa'), True), self.sdk.reads)

    def test_known_empty_main_read_failure_is_preserved_without_fresh_thread_fallback(self):
        self.sdk.reject_empty_history = True
        with self.w.lock():
            self.runtime._operation(None, None, None)
            main_thread = self.sdk.native_thread('main')
            self.w.state['thread_id'] = main_thread.id
            self.w.save()
        for retry in (False, True):
            with self.subTest(retry=retry), self.assertRaises(MethodNotFoundError) as error:
                self.runtime.run(retry=retry)
            self.assertEqual(error.exception.code, -32601)
            self.assertEqual(self.w.state['thread_id'], 'main')
            self.assertIsNone(self.w.state['operations'][self.w.state['active']]['turn_id'])
        self.assertEqual(len(self.sdk.starts), 0)
        self.assertEqual(len(self.sdk.prompts), 0)
        self.assertEqual(len(main_thread.data.turns), 0)
        self.assertEqual(len(self.w.state['failures']), 2)
        self.assertTrue(all(options['include_turns'] is False for identifier, options in self.sdk.resumes
                            if identifier == 'main'))

    def test_missing_main_identity_with_durable_turn_cannot_start_replacement(self):
        with self.w.lock():
            record = self.runtime._operation(None, None, None)
            record['turn_id'] = 'previous-native-turn'
            self.w.save()
        with self.assertRaises(ValueError):
            self.runtime.run(retry=True)
        self.assertEqual(len(self.sdk.starts), 0)
        self.assertEqual(len(self.sdk.prompts), 0)
        self.assertEqual(self.w.state['operations'][self.w.state['active']]['turn_id'], 'previous-native-turn')

    def test_existing_nonempty_main_history_error_cannot_replay_uncertain_completion(self):
        self.bootstrap()
        self.sdk.lose_completion_once = True
        with self.assertRaises(TimeoutError):
            self.observe()
        saved = json.loads(self.w.state_path.read_text())
        active, turns = saved['active'], len(self.sdk.prompts)
        old_read = FakeThread.read
        def read(thread, *, include_turns=False):
            if thread.id == 'main' and include_turns:
                raise MethodNotFoundError(-32601, 'list_turns is not supported yet')
            return old_read(thread, include_turns=include_turns)
        self.cold()
        with patch.object(FakeThread, 'read', new=read):
            for retry in (False, True):
                with self.subTest(retry=retry), self.assertRaises(MethodNotFoundError):
                    self.runtime.run(retry=retry)
        self.assertEqual(len(self.sdk.starts), 1)
        self.assertEqual(len(self.sdk.prompts), turns)
        self.assertEqual(self.w.state['active'], active)
        self.assertEqual(self.w.state['operations'][active]['turn_id'], saved['operations'][active]['turn_id'])

    def test_unknown_running_native_main_cannot_be_treated_as_fresh(self):
        self.bootstrap()
        self.sdk.threads['main'].data.status = type(self.sdk.threads['main'].data.status).model_validate(
            dict(type='active', activeFlags=[]))
        turns = len(self.sdk.prompts)
        with self.assertRaisesRegex(ValueError, 'Unknown running'):
            self.observe()
        self.assertEqual(len(self.sdk.starts), 1)
        self.assertEqual(len(self.sdk.prompts), turns)

    def test_retry_cannot_join_unknown_work_after_a_known_completed_turn(self):
        self.sdk.lose_completion_once = True
        with self.assertRaises(TimeoutError):
            self.runtime.run()
        parent = self.sdk.threads['main'].data
        parent.turns.append(Turn.model_validate(dict(id='foreign-running', status='inProgress',
            items=[dict(type='userMessage', id='foreign-input', content=[dict(type='text', text='Unrelated operation')])])))
        prompts = len(self.sdk.prompts)
        with self.assertRaisesRegex(ValueError, 'Unknown running'):
            self.runtime.run(retry=True)
        self.assertEqual(len(self.sdk.prompts), prompts)
        self.assertEqual(self.w.head(), self.baseline_head)

    def test_hold_stop_restart_and_explicit_reconsideration_preserve_history(self):
        self.bootstrap()
        self.sdk.action = 'hold'
        decision = self.observe()
        previous = json.loads(self.w.state_path.read_text())
        self.assertIsNone(decision.next_params)
        self.factory.reset_mock()
        self.cold()
        self.assertEqual(self.runtime.run().action, 'hold')
        self.factory.assert_not_called()
        self.sdk.action = 'stop'
        updated = self.runtime.run(reconsideration='New synthetic context requires another judgment')
        self.assertEqual(updated.action, 'stop')
        self.assertEqual(len(self.sdk.starts), 1)
        for identifier, record in previous['operations'].items():
            self.assertEqual(self.w.state['operations'][identifier], record)
        with self.assertRaises(ValueError):
            self.runtime.run(reconsideration=' ')

    def test_hold_without_knowledge_is_not_initialization_and_survives_restart(self):
        self.sdk.bootstrap_hold = True
        self.assertEqual(self.runtime.run().action, 'hold')
        self.assertIsNone(self.w.state['knowledge_commit'])
        self.factory.reset_mock()
        self.cold()
        self.assertIsNone(self.runtime.run().knowledge_commit)
        self.factory.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'bootstrap'):
            self.observe()
        self.sdk.bootstrap_hold = False
        self.assertIsNone(self.runtime.run(reconsideration='Initial theory can now be reviewed'))
        self.assertIsNotNone(self.w.state['knowledge_commit'])

    def test_new_knowledge_publication_continues_arbitrary_question_with_commit(self):
        self.bootstrap()
        self.sdk.publish_next = True
        self.assertIsNone(self.observe())
        adopted = self.w.state['knowledge_commit']
        operation = self.w.state['active']
        path = self.w.round_path(self.w.state['operations'][operation])+'/adoption.json'
        original = self.w.git('show',adopted+':'+path).stdout
        self.cold()
        decision = self.runtime.run()
        self.assertEqual(decision.knowledge_commit, adopted)
        self.assertEqual(len(self.sdk.starts), 1)
        self.assertIn(adopted, self.sdk.prompts[-1])
        self.assertEqual(self.w.state['active'],operation)
        tx=json.loads(self.w.path(self.w._transaction_path({'token':self.w.state['local_publication']},'transaction.json')).read_text())
        self.assertEqual(tx['prepared'][path]['action'],'REPLACE')
        self.assertEqual((self.w.root/tx['prepared'][path]['slot']/'capture').read_bytes(),original)

    def test_lost_knowledge_commit_ack_does_not_replay_adoption_or_native_turn(self):
        self.bootstrap()
        self.sdk.publish_next = True
        native_git = self.w.git
        def lose_ack(*args, **kwargs):
            result = native_git(*args, **kwargs)
            if args[0] == 'update-ref':
                raise RuntimeError('synthetic lost publication ack')
            return result
        with patch.object(self.w, 'git', side_effect=lose_ack):
            with self.assertRaisesRegex(RuntimeError, 'lost publication'):
                self.observe()
        adopted = self.w.head()
        self.cold()
        decision = self.runtime.run()
        self.assertEqual(decision.knowledge_commit, adopted)
        self.assertEqual(len(self.sdk.threads['main'].data.turns), 3)
        self.assertEqual(self.w.git('rev-list', '--count', self.baseline_head+'..HEAD').stdout.strip(), b'3')

    def test_ordinary_restart_cannot_silently_use_changed_completed_inputs(self):
        self.bootstrap()
        self.sdk.action = 'hold'
        self.observe()
        original_id = self.w.state['active']
        self.input.write_text('name,E,F\nSYNTHETIC-corrected,2,0.4\n')
        with self.assertRaisesRegex(ValueError, 'observation changed'):
            self.runtime.run()
        self.assertEqual(self.w.state['active'], original_id)
        self.assertEqual(self.runtime.run(reconsideration='Corrected supplied observations').action, 'hold')

    def test_no_id_cached_restart_rejects_new_bindings(self):
        self.bootstrap()
        previous = self.observe()
        active = self.w.state['active']
        changed = self.w.root / 'data/raw/new.csv'
        changed.write_text('name,E,F\nSYNTHETIC-new,2,0.3\n')
        self.factory.reset_mock()
        with self.assertRaises(ValueError):
            self.runtime.run(inputs={'new': changed})
        self.assertEqual(self.w.state['active'], active)
        self.assertEqual(self.runtime.run(), previous)
        self.factory.assert_not_called()

    def test_cached_bootstrap_run_hold_stop_validate_all_supplied_bindings(self):
        for phase in ['bootstrap', 'bootstrap-hold', 'bootstrap-stop', 'run', 'hold', 'stop']:
            with self.subTest(phase=phase):
                fixture = RuntimeTests()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                if phase.startswith('bootstrap-'):
                    fixture.sdk.bootstrap_hold = True
                    fixture.sdk.bootstrap_action = phase.removeprefix('bootstrap-')
                result = fixture.runtime.run()
                if not phase.startswith('bootstrap'):
                    fixture.sdk.action = phase
                    result = fixture.observe()
                original = json.loads(fixture.w.state_path.read_text())
                binding = {} if phase.startswith('bootstrap') else {'table': fixture.input}
                fixture.factory.reset_mock()
                fixture.cold()
                self.assertEqual(fixture.runtime.run(inputs=binding), result)
                self.assertEqual(fixture.runtime.run(), result)
                new = fixture.w.root / 'data/raw/new.csv'
                new.write_text('name,E,F\nSYNTHETIC-new,3,0.4\n')
                invalid = [{'new': new}, {'table': new}]
                if binding:
                    invalid.append({})
                for supplied in invalid:
                    with self.subTest(supplied=supplied), self.assertRaises(ValueError):
                        fixture.runtime.run(inputs=supplied)
                fixture.factory.assert_not_called()
                self.assertEqual(fixture.w.state['operations'], original['operations'])
                # New bindings are reachable through deliberate reconsideration.
                fixture.sdk.bootstrap_hold = False
                if phase.startswith('bootstrap-'):
                    self.assertIsNone(fixture.runtime.run(reconsideration='Theory initialization can now proceed'))
                else:
                    fixture.sdk.action = 'hold'
                    self.assertEqual(fixture.runtime.run(inputs={'new': new},
                        reconsideration='New synthetic evidence explicitly changes the question').action, 'hold')
                for identifier, record in original['operations'].items():
                    self.assertEqual(fixture.w.state['operations'][identifier], record)

    def test_second_named_campaign_reuses_approved_bank_but_has_its_own_main(self):
        bank = self.bootstrap()
        self.observe()
        original = self.w.state_path.read_bytes()
        context = Context.model_validate(dict(CONTEXT, campaign='synthetic-second'))
        with self.assertRaisesRegex(ValueError, 'binding'):
            CampaignRuntime(self.w, context, sdk_factory=self.factory)
        workspace = Workspace(self.w.root, context.campaign, self.w.material)
        self.sdk.w = workspace
        second = CampaignRuntime(workspace, context, sdk_factory=self.factory)
        new = self.w.root / 'data/raw/second.csv'
        new.write_text('name,E,F\nSYNTHETIC-second,2,0.6\n')
        decision = second.run(observation_id='second1', inputs={'table': new})
        self.assertEqual(decision.knowledge_commit, bank)
        self.assertNotEqual(workspace.state['thread_id'], self.w.state['thread_id'])
        self.assertEqual(len(self.sdk.starts), 2)
        active = workspace.state['operations'][workspace.state['active']]
        self.assertEqual(active['campaign'], context.campaign)
        self.assertEqual(active['kind'], 'observation')
        self.assertEqual(active['inputs']['table']['path'], workspace.relative(new))
        self.assertIn('data/results/synthetic-second/mas/rounds/', workspace.git('ls-files').stdout.decode())
        self.factory.reset_mock()
        self.assertEqual(second.run(inputs={'table': new}), decision)
        self.factory.assert_not_called()
        self.assertEqual(self.w.state_path.read_bytes(), original)

    def test_revision_identity_survives_lost_caller_ack_without_new_reasoning(self):
        self.bootstrap()
        self.sdk.action = 'hold'
        self.observe()
        previous = json.loads(self.w.state_path.read_text())
        first = self.runtime.run(reconsideration='New synthetic evidence warrants review', revision_id='revision-1')
        active = self.w.state['active']
        turns = len(self.sdk.prompts)
        self.cold()
        self.factory.reset_mock()
        again = self.runtime.run(reconsideration='New synthetic evidence warrants review', revision_id='revision-1')
        self.assertEqual(first, again)
        self.assertEqual(self.runtime.last_operation_id, active)
        self.assertEqual(len(self.sdk.prompts), turns)
        self.factory.assert_not_called()
        for identifier, record in previous['operations'].items():
            self.assertEqual(self.w.state['operations'][identifier], record)
        with self.assertRaises(ValueError):
            self.runtime.run(reconsideration='Different reason', revision_id='revision-1')
        with self.assertRaises(ValueError):
            self.runtime.run(revision_id='revision-1')

    def test_pinned_cli_parses_repo_home_profile_without_sdk_or_model(self):
        self.prepare_sdk()
        home=self.base/'nonsecret user home'
        with (self.w.lock(), patch('pathlib.Path.home',return_value=home), patch.dict(os.environ,
                CODEX_HOME=str(self.base/'nonsecret external home'),CODEX_SQLITE_HOME=str(self.base/'nonsecret sqlite home')),
                patch('openai_codex.Codex') as client):
            isolated_sdk(self.w)  # Actual pinned `mcp list` only; constructor stays mocked.
        client.assert_called_once()
        config = client.call_args.args[0]
        self.assertEqual(config.env['CODEX_HOME'], str(self.w.root))
        self.assertIn('default_permissions="mas"', config.config_overrides)
        self.assertTrue(Path(config.cwd).is_relative_to(self.w.path(self.w.area)))

    def test_attempt_profile_denies_native_thread_locks_databases_and_auth(self):
        self.prepare_sdk()
        from mas_runtime import _attempt_config
        record = self.w.state['operations'][self.w.state['active']]
        config = _attempt_config(self.w, record)
        filesystem = config['permissions']['mas']['filesystem']
        self.assertEqual(filesystem[str(self.w.path(self.w.attempt_path(record)))], 'write')
        self.assertNotEqual(filesystem.get(str(self.w.root)), 'write')
        for name in ('thread-writer-locks', 'auth.json*', 'state_*.sqlite*', 'logs_*.sqlite*'):
            with self.subTest(name=name):
                self.assertEqual(filesystem.get(str(self.w.root/name)), 'deny')
        self.assertEqual(config['project_doc_max_bytes'], 0)
        self.assertNotIn('sandbox_mode', config)
        for name in ('thread-writer-locks/private.json', 'state_5.sqlite-wal', 'auth.json.lock'):
            path = self.w.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic native metadata; no secret.')
            with self.subTest(input=name), self.assertRaises(ValueError):
                self.w.input_path(path)
        ordinary = self.w.root/'data/raw/thread-writer-locks/measurement.sqlite'
        ordinary.parent.mkdir(parents=True,exist_ok=True);ordinary.write_text('Synthetic measurement.')
        self.assertEqual(self.w.input_path(ordinary), ordinary)

    def test_profile_covers_other_campaign_host_state_and_external_native_homes(self):
        self.prepare_sdk()
        from mas_runtime import _attempt_config
        record=self.w.state['operations'][self.w.state['active']]
        home=self.base/'nonsecret user home';external=self.base/'external native home'
        sqlite=self.base/'nonsecret sqlite home'
        with patch('pathlib.Path.home',return_value=home),patch.dict(os.environ,CODEX_HOME=str(external),CODEX_SQLITE_HOME=str(sqlite)):
            filesystem=_attempt_config(self.w,record)['permissions']['mas']['filesystem']
            for path in (home/'.codex',external,sqlite):
                with self.subTest(native_home=str(path)):self.assertEqual(filesystem.get(str(path)),'deny')
            for suffix in ('.native/sqlite/state_5.sqlite','.mas-runtime.json','.transactions/token/0','.inputs/request/provenance.json'):
                path=self.w.root/'data/results/other/mas'/suffix
                with self.subTest(cross_campaign=suffix):self.assertTrue(profile_denies(filesystem,path))
            canary=external/'state_5.sqlite';canary.parent.mkdir(parents=True);canary.write_text('SYNTHETIC_NONSECRET_CANARY')
            with self.assertRaises(ValueError):self.w.input_path(canary)
            self.assertEqual(filesystem[str(self.w.path(self.w.attempt_path(record)))],'write')
            self.assertEqual(filesystem[str(self.w.path(self.w.area+'/.inputs'))],'read')
            self.assertEqual([p for p,mode in filesystem.items() if mode=='write'],[str(self.w.path(self.w.attempt_path(record)))])

    def test_host_directory_rules_match_full_descendant_paths(self):
        self.prepare_sdk()
        from mas_runtime import _attempt_config
        record=self.w.state['operations'][self.w.state['active']]
        filesystem=_attempt_config(self.w,record)['permissions']['mas']['filesystem']
        for campaign in (self.w.campaign,'other','future-campaign'):
            for suffix in ('.native/known.txt','.native/deeper/known.txt',
                           '.transactions/known.txt','.transactions/token/deeper/known.txt',
                           '.mas-runtime.json','.mas-state.json','.mas.lock','.pipeline.lock'):
                with self.subTest(campaign=campaign,suffix=suffix):
                    self.assertTrue(profile_denies(filesystem,self.w.root/f'data/results/{campaign}/mas'/suffix))
        for suffix in ('auth.json.synthetic/known.txt','state_5.sqlite.synthetic/deeper/known.txt',
                       'logs_5.sqlite.synthetic/deeper/known.txt','.codex-global-state.json.synthetic/known.txt'):
            with self.subTest(root_native=suffix):self.assertTrue(profile_denies(filesystem,self.w.root/suffix))
        for relative in ('data/raw/.native/known.txt','data/raw/.transactions/deep/known.txt',
                         'data/results/other/mas/rounds/reviewed/analysis.md','src/pipeline/mas_contract.py'):
            with self.subTest(scientific=relative):self.assertFalse(profile_denies(filesystem,self.w.root/relative))
        attempt=self.w.path(self.w.attempt_path(record))
        self.assertEqual(filesystem[str(attempt)],'write')
        self.assertEqual(filesystem[str(attempt/'.codex')],'read')
        self.assertFalse(profile_denies(filesystem,attempt/'artifacts/code/analysis.py'))

    def test_input_complement_preserves_only_validated_current_campaign(self):
        self.prepare_sdk()
        from mas_runtime import _attempt_config
        record=self.w.state['operations'][self.w.state['active']]
        for current in ('c','cam-p_a','X'*100):
            workspace=Workspace(self.w.root,current,'synthetic')
            filesystem=_attempt_config(workspace,{**record,'campaign':current})['permissions']['mas']['filesystem']
            opponents={current,'c','cam','cam-p_','cam-p_ab','other','cam-p_b','cam_p_a','cam-pa','-','_',
                       'future-campaign','X'*99,'X'*99+'Y','Y'+'X'*99}
            opponents.update(current[:i] for i in range(1,len(current)))
            opponents.update(current[:i]+('Y' if c!='Y' else 'X')+current[i+1:] for i,c in enumerate(current))
            if len(current)<100:opponents.add(current+'Z')
            for candidate in opponents:
                for suffix in ('','.known.txt','/direct.txt','/deeper/known.txt'):
                    path=workspace.root/f'data/results/{candidate}/mas/.inputs{suffix}'
                    # A similarly prefixed sibling is ordinary scientific data.
                    expected=candidate!=current and suffix!='.known.txt'
                    with self.subTest(current=current,candidate=candidate,suffix=suffix):
                        self.assertEqual(profile_denies(filesystem,path),expected)
            self.assertEqual(filesystem[str(workspace.path(workspace.area+'/.inputs'))],'read')

    def test_complement_rules_keep_native_groups_bounded_and_flat(self):
        self.prepare_sdk()
        from mas_runtime import _attempt_config
        record=self.w.state['operations'][self.w.state['active']]
        for current in ('c','cam-p_a','X'*100):
            workspace=Workspace(self.w.root,current,'synthetic')
            filesystem=_attempt_config(workspace,{**record,'campaign':current})['permissions']['mas']['filesystem']
            rules=[rule for rule,mode in filesystem.items() if mode=='deny' and '/mas/.inputs' in rule]
            self.assertTrue(rules)
            # Bound both the native expression and rule count; do not trade the
            # monolithic regex for the known failing one-alternative expansion.
            self.assertLessEqual(len(rules),len(current)+2)
            for rule in rules:
                with self.subTest(current=current,rule=rule):
                    self.assertEqual(rule.count('{'),1);self.assertEqual(rule.count('}'),1)
                    choices=rule.split('{',1)[1].split('}',1)[0].split(',')
                    self.assertLessEqual(len(choices),4)
                    self.assertTrue(all(choices))

    def test_native_home_ancestor_overlap_fails_without_broadening_permissions(self):
        self.prepare_sdk()
        from mas_runtime import _attempt_config
        record=self.w.state['operations'][self.w.state['active']]
        attempt=self.w.path(self.w.attempt_path(record))
        for ancestor in (self.w.root.parent,attempt.parent):
            with self.subTest(ancestor=str(ancestor)),patch.dict(os.environ,CODEX_HOME=str(ancestor)),self.assertRaisesRegex(ValueError,'overlap'):
                _attempt_config(self.w,record)
        external=self.base/'native with prepared interpreter'
        with (patch.dict(os.environ,CODEX_HOME=str(external)),patch('sys.prefix',str(external/'env')),
                self.assertRaisesRegex(ValueError,'overlap')):
            _attempt_config(self.w,record)

    def test_native_home_cannot_be_replaced_by_exact_role_or_input_read_grants(self):
        from mas_runtime import _attempt_config
        with self.w.lock():record=self.runtime._operation(None,None,None)
        attempt=self.w.path(self.w.attempt_path(record))
        for variable in ('CODEX_HOME','CODEX_SQLITE_HOME'):
            for home in (attempt/'.codex',self.w.path(self.w.area+'/.inputs')):
                environment={'CODEX_HOME':str(self.base/'external-home'),'CODEX_SQLITE_HOME':str(self.base/'external-sqlite'),variable:str(home)}
                with self.subTest(variable=variable,home=str(home)),patch('pathlib.Path.home',return_value=self.base/'user-home'),patch.dict(os.environ,environment):
                    try:config=_attempt_config(self.w,record)
                    except ValueError:rejected=True;mode=None
                    else:rejected=False;mode=config['permissions']['mas']['filesystem'].get(str(home))
                    print('SYNTHETIC_EXACT_HOME_OVERLAP',json.dumps(dict(variable=variable,rejected=rejected,requested_mode=mode)))
                    self.assertTrue(rejected)

    def test_native_preflight_precedes_runtime_producers_after_environment_change(self):
        from mas_runtime import _attempt_config,_analysis_env
        with self.w.lock():record=self.runtime._operation(None,None,None)
        attempt=self.w.path(self.w.attempt_path(record));area=self.w.path(self.w.area)
        canary=self.w.root/'nested-native/canary.txt';canary.parent.mkdir();canary.write_bytes(b'SYNTHETIC_NONSECRET_CANARY')
        journal=self.w.state_path.read_bytes();source=(self.w.root/'AGENTS.md').read_bytes()
        index=Path(self.w.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
        raw=index.read_bytes();head=self.w.head()
        calls=[self.runtime._bindings,lambda:_attempt_config(self.w,record),lambda:_analysis_env(self.w,record),
               lambda:isolated_sdk(self.w),self.runtime.run]
        homes=[attempt.parent,attempt,attempt/'.codex',attempt/'.codex/agents',attempt/'.scratch',attempt/'.scratch/nested',
               area,area/'.native',area/'.native/sqlite',area/'.inputs',area/'.inputs/request',area/'.mas-runtime.json',canary.parent]
        for variable in ('CODEX_HOME','CODEX_SQLITE_HOME'):
            for home in homes:
                environment={'CODEX_HOME':str(self.base/'external-home'),'CODEX_SQLITE_HOME':str(self.base/'external-sqlite'),variable:str(home)}
                with (patch('pathlib.Path.home',return_value=self.base/'user-home'),patch.dict(os.environ,environment),
                      patch('mas_runtime.subprocess.run',side_effect=AssertionError('Subprocess before preflight')) as process,
                      patch('openai_codex.Codex') as client):
                    for number,call in enumerate(calls):
                        with self.subTest(variable=variable,home=str(home),producer=number),self.assertRaisesRegex(ValueError,'overlap'):
                            call()
                    process.assert_not_called();client.assert_not_called()
        self.factory.assert_not_called()
        self.assertFalse((attempt/'.codex').exists());self.assertFalse((attempt/'.scratch').exists());self.assertFalse((area/'.native').exists())
        self.assertEqual(self.w.state_path.read_bytes(),journal);self.assertEqual((self.w.root/'AGENTS.md').read_bytes(),source)
        self.assertEqual(index.read_bytes(),raw);self.assertEqual(self.w.head(),head)
        self.assertEqual(canary.read_bytes(),b'SYNTHETIC_NONSECRET_CANARY')

    def test_exact_repository_and_disjoint_native_homes_keep_valid_runtime_paths(self):
        from mas_runtime import _attempt_config
        for selected in (False,True):
            environment={'CODEX_HOME':str(self.w.root if selected else self.base/'external-home'),
                         'CODEX_SQLITE_HOME':str(self.w.root if selected else self.base/'external-sqlite')}
            with patch('pathlib.Path.home',return_value=self.base/'user-home'),patch.dict(os.environ,environment):
                with self.w.lock():
                    record=self.runtime._operation(None,None,None)
                    config=_attempt_config(self.w,record)
                    self.runtime._bindings()
                filesystem=config['permissions']['mas']['filesystem']
                self.assertEqual(filesystem[str(self.w.path(self.w.attempt_path(record)))],'write')
                for home in self.w.native_homes():self.assertEqual(filesystem[str(home)],'deny')
        self.assertIsNone(self.runtime.run())
        self.factory.assert_called_once()

    def test_analysis_uv_uses_prepared_interpreter_and_output_cache(self):
        self.prepare_sdk()
        replies = [subprocess.CompletedProcess([], 0, '[]', '')] * 2
        with self.w.lock(), patch('mas_runtime.subprocess.run', side_effect=replies):
            with patch('openai_codex.Codex') as client:
                isolated_sdk(self.w)
            config = client.call_args.args[0]
        outside = self.base / 'unwritable-cache'
        outside.mkdir()
        outside.chmod(0o500)
        self.addCleanup(outside.chmod, 0o700)
        env = dict(os.environ, UV_CACHE_DIR=str(outside), UV_OFFLINE='1', VIRTUAL_ENV=sys.prefix)
        env.pop('UV_NO_CACHE', None)  # The Writer's helper must not mask the real boundary.
        env.update(config.env)
        command = ['uv', 'run', '--no-sync', 'python', '-c',
                   'import pandas, scipy, sys; print("analysis_ready", sys.prefix)']
        result = subprocess.run(command, cwd=self.w.root, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('analysis_ready ' + sys.prefix, result.stdout)
        self.assertEqual(list(outside.iterdir()), [])
        for variable in ['TMPDIR', 'TMP', 'TEMP', 'UV_CACHE_DIR', 'XDG_CACHE_HOME', 'MPLCONFIGDIR']:
            self.assertTrue(Path(config.env[variable]).is_relative_to(self.w.root), variable)
        self.assertEqual(config.env['UV_NO_SYNC'], '1')
        self.assertEqual(config.env['UV_PYTHON_DOWNLOADS'], 'never')
        # Opposite control: only the cache binding changes; real uv must fail
        # rather than write to the unavailable external cache.
        opposite = subprocess.run(command, cwd=self.w.root,
            env=dict(env, UV_CACHE_DIR=str(outside)), capture_output=True, text=True)
        self.assertNotEqual(opposite.returncode, 0)
        self.assertIn(str(outside), opposite.stderr)
        self.assertEqual(list(outside.iterdir()), [])
        print('SYNTHETIC_ANALYSIS_ENV_CHECK', json.dumps(dict(argv=command, cwd=str(self.w.path(self.w.attempt_path(self.w.state['operations'][self.w.state['active']]))),
            bound_environment=config.env, positive=dict(exit=result.returncode, stdout=result.stdout,
                                                        stderr=result.stderr),
            opposite_cache=str(outside), negative=dict(exit=opposite.returncode, stdout=opposite.stdout,
                                                       stderr=opposite.stderr))))

    def test_pending_turn_and_lost_completion_recover_on_same_main(self):
        self.sdk.interrupt_once = True
        with self.assertRaises(TimeoutError):
            self.runtime.run()
        pending = json.loads(self.w.state_path.read_text())
        operation = pending['operations'][pending['active']]
        self.assertEqual(operation['turn_id'], 'turn-0')
        self.assertEqual(pending['failures'][0]['type'], 'TimeoutError')
        self.cold()
        self.bootstrap()
        self.assertEqual(len(self.sdk.threads['main'].data.turns), 1)
        self.sdk.lose_completion_once = True
        with self.assertRaises(TimeoutError):
            self.observe()
        turns = len(self.sdk.threads['main'].data.turns)
        self.cold()
        self.assertEqual(self.runtime.run().action, 'run')
        self.assertEqual(len(self.sdk.threads['main'].data.turns), turns)

    def test_failed_native_turn_requires_explicit_retry(self):
        self.sdk.failed_once = True
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            self.runtime.run()
        with self.assertRaisesRegex(RuntimeError, 'retry'):
            self.runtime.run()
        self.assertIsNone(self.runtime.run(retry=True))
        self.assertEqual(len(self.sdk.threads['main'].data.turns), 2)
        self.assertTrue(self.w.state['failures'])

    def test_raw_failure_diagnostic_stays_local_after_retry_publication(self):
        sentinel = 'SYNTHETIC_PRIVATE_DIAGNOSTIC_7615'
        def fail(handle):
            raise TimeoutError(sentinel)
        with patch.object(FakeHandle, 'run', new=fail), self.assertRaisesRegex(TimeoutError, sentinel):
            self.runtime.run()
        failure = self.w.state['failures'][0].copy()
        self.assertEqual(failure['message'], sentinel)
        self.assertEqual(failure['turn_id'], 'turn-0')
        self.cold()
        self.assertIsNone(self.runtime.run(retry=True))
        self.assertEqual(self.w.state['failures'][0], failure)
        self.assertIn(sentinel, self.w.state_path.read_text())
        checkpoint = json.loads(self.w.path(self.w.checkpoint).read_text())
        self.assertEqual(checkpoint['failures'][0], {k:failure[k] for k in ('operation','turn_id','type')})
        paths = self.w.git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').stdout.decode().splitlines()
        self.assertIn(self.w.checkpoint, paths)
        for path in paths:
            self.assertNotIn(sentinel.encode(), self.w.git('show', 'HEAD:' + path).stdout, path)

    def test_actual_derived_artifacts_publish_with_native_and_input_provenance(self):
        self.bootstrap()
        original = self.sdk.reply
        selected = {}
        def reply():
            value, events = original()
            record = self.w.state['operations'][self.w.state['active']]
            base = self.w.attempt_path(record) + '/artifacts/'
            for name, data in {'code/analysis.py':b'print("Synthetic analysis")\n',
                               'tables/result.csv':b'input,value\nSYNTHETIC,1\n',
                               'figures/result.svg':b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L1 1"/></svg>'}.items():
                selected[base + name] = data
                self.w.write(base + name, data)
            value['records'].extend(selected)
            return value, events
        with patch.object(self.sdk, 'reply', side_effect=reply):
            self.assertEqual(self.observe().action, 'run')
        record = self.w.state['operations'][self.w.state['active']]
        receipt = json.loads(self.w.git('show','HEAD:'+self.w.round_path(record)+'/adoption.json').stdout)
        manifest = {a['path']:a for a in receipt['artifacts']}
        for path, data in selected.items():
            self.assertEqual(self.w.git('show','HEAD:'+path).stdout,data)
            self.assertEqual(manifest[path]['operation_id'],record['id'])
            self.assertEqual(manifest[path]['inputs'],record['inputs'])
            self.assertEqual(manifest[path]['native_review'],receipt['native_review'])
            self.assertTrue(all(not Path(v['path']).is_absolute() for v in manifest[path]['inputs'].values()))

    def test_derived_artifact_without_native_review_cannot_publish_hold(self):
        self.bootstrap();self.sdk.action='hold'
        head=self.w.head();original=self.sdk.reply
        def reply():
            value,events=original()
            record=self.w.state['operations'][self.w.state['active']]
            path=self.w.attempt_path(record)+'/artifacts/tables/result.json'
            self.w.write(path,'{"synthetic":1}')
            value['records']=[path]
            return value,events
        with patch.object(self.sdk,'reply',side_effect=reply),self.assertRaisesRegex(ValueError,'native author/reviewer'):
            self.observe()
        self.assertEqual(self.w.head(),head)

    def test_relocated_checkpoint_cache_works_but_missing_native_history_never_replaces_main(self):
        self.bootstrap();self.sdk.action='hold';decision=self.observe()
        original_thread=self.w.state['thread_id']
        relocated=self.base/'relocated project 한글'
        shutil.copytree(self.w.root,relocated)
        (relocated/self.w.area/'.mas-runtime.json').unlink()
        workspace=Workspace(relocated,'synthetic','synthetic')
        absent=FakeCodex(workspace)
        with patch('mas_runtime.isolated_sdk',return_value=absent) as factory:
            runtime=CampaignRuntime(workspace,CONTEXT)
            self.assertEqual(runtime.run(),decision)
            factory.assert_not_called()
            with self.assertRaises(KeyError):
                runtime.run(observation_id='new-relocated-observation',inputs={'selected':'data/raw/synthetic.csv'})
        self.assertEqual(absent.starts,[])
        self.assertEqual(workspace.state['thread_id'],original_thread)
        self.assertEqual(workspace.state['failures'][-1]['type'],'KeyError')

    def test_retry_during_running_turn_can_still_recover_after_another_interruption(self):
        self.sdk.interrupt_once = True
        with self.assertRaises(TimeoutError):
            self.runtime.run()
        self.sdk.interrupt_once = True
        with self.assertRaises(TimeoutError):
            self.runtime.run(retry=True)
        self.cold()
        self.assertIsNone(self.runtime.run())
        self.assertEqual(len(self.sdk.threads['main'].data.turns), 1)

    def test_changed_failed_observation_can_be_explicitly_reconsidered_after_native_completion(self):
        self.bootstrap()
        self.sdk.failed_once = True
        with self.assertRaises(RuntimeError):
            self.observe()
        old_id = self.w.state['active']
        old_inputs = self.w.state['operations'][old_id]['inputs'].copy()
        self.input.write_text('name,E,F\nSYNTHETIC-corrected,2,0.4\n')
        self.cold()
        decision = self.runtime.run(observation_id='corrected', inputs={'table': self.input},
                                    reconsideration='Authorized corrected evidence after failed analysis')
        self.assertEqual(decision.action, 'run')
        previous = self.w.state['operations'][old_id]
        self.assertEqual(previous['status'], 'superseded')
        self.assertEqual(previous['inputs'], old_inputs)
        self.assertNotEqual(self.w.state['active'], old_id)

    def test_reconsideration_cannot_abandon_a_genuinely_running_turn(self):
        self.bootstrap()
        self.sdk.interrupt_once = True
        with self.assertRaises(TimeoutError):
            self.observe()
        old_id = self.w.state['active']
        with self.assertRaisesRegex(ValueError, 'running'):
            self.runtime.run(reconsideration='A new question while old turn is still active')
        self.assertEqual(self.w.state['active'], old_id)
        self.assertEqual(self.w.state['operations'][old_id]['status'], 'running')

    def test_wrong_native_role_parent_self_review_prose_and_stale_receipts_block_bootstrap(self):
        for flag in ['bad_role', 'bad_parent', 'same_actor', 'no_event', 'reject_review',
                     'stale_receipt', 'escape_record', 'incomplete_review', 'failed_review_turn']:
            with self.subTest(flag=flag):
                setattr(self.sdk, flag, True)
                with self.assertRaises(ValueError):
                    self.runtime.run(retry=True)
                self.assertIsNone(self.w.state['knowledge_commit'])
                self.assertEqual(self.w.head(), self.baseline_head)
                setattr(self.sdk, flag, False)
                # A fresh repair uses actual new native completions, not a forged PASS.
                if self.sdk.identifier('knowledge', 'qa') in self.sdk.threads:
                    self.sdk.threads[self.sdk.identifier('knowledge', 'qa')].data.agent_role = 'hypothesis-qa'
                    self.sdk.threads[self.sdk.identifier('knowledge', 'qa')].data.parent_thread_id = 'main'
        self.assertIsNone(self.runtime.run(retry=True))

    def test_exact_design_conditions_and_strict_native_types(self):
        self.bootstrap()
        for flag in ['drift_conditions', 'bad_boolean']:
            with self.subTest(flag=flag):
                setattr(self.sdk, flag, True)
                with self.assertRaises(ValueError):
                    self.runtime.run(observation_id='synthetic1', inputs={'table': self.input}, retry=True)
                self.assertIsNone(self.w.state['pending'])
                setattr(self.sdk, flag, False)
        self.assertEqual(self.runtime.run(retry=True).action, 'run')

    def test_original_input_change_during_work_blocks_adoption_and_is_not_rolled_back(self):
        self.bootstrap()
        head = self.w.head()
        self.sdk.hook = lambda: self.input.write_text('changed original fixture')
        with self.assertRaisesRegex(ValueError, 'observation changed'):
            self.observe()
        self.assertEqual(self.w.head(), head)
        self.assertEqual(self.input.read_text(), 'changed original fixture')
        self.assertIsNone(self.w.state['operations'][self.w.state['active']]['decision'])

    def test_context_mutation_during_work_does_not_change_reviewed_execution(self):
        self.bootstrap()
        head = self.w.head()
        self.sdk.hook = lambda: self.runtime.context.stock_metadata.update(polymer_stock_wt_percent=25.0)
        with self.assertRaisesRegex(ValueError, 'context changed'):
            self.observe()
        self.assertEqual(self.w.head(), head)

    def test_cli_import_help_and_mcp_failure_do_not_start_a_client(self):
        self.prepare_sdk()
        with patch('openai_codex.Codex') as client:
            with self.assertRaises(SystemExit) as exited:
                main(['--help'])
            self.assertEqual(exited.exception.code, 0)
            with self.w.lock(), patch('mas_runtime.subprocess.run', side_effect=OSError('synthetic inspection failure')):
                with self.assertRaisesRegex(RuntimeError, 'SDK not started'):
                    isolated_sdk(self.w)
            client.assert_not_called()

    def test_cli_defaults_to_not_run_without_creating_workspace(self):
        context = self.base / 'context.json'
        context.write_text(json.dumps(CONTEXT))
        with patch('openai_codex.Codex') as client:
            main(['--repo', str(self.w.root),
                  '--material', 'synthetic', '--context', str(context)])
            client.assert_not_called()
        self.assertFalse(self.w.state_path.exists())

    def test_cli_overlap_preflight_precedes_operator_context_read(self):
        context=self.base/'approved-context.json';context.write_text(json.dumps(CONTEXT))
        inside=self.w.root/'nested-native/context.json';inside.parent.mkdir();inside.write_text(json.dumps(CONTEXT))
        original=Path.read_text
        for variable in ('CODEX_HOME','CODEX_SQLITE_HOME'):
            for home,path in ((self.w.root.parent,context),(inside.parent,inside)):
                environment={'CODEX_HOME':str(self.base/'external-home'),'CODEX_SQLITE_HOME':str(self.base/'external-sqlite'),variable:str(home)}
                with (self.subTest(variable=variable,home=str(home)),patch('pathlib.Path.home',return_value=self.base/'user-home'),
                      patch.dict(os.environ,environment),patch.object(Path,'read_text',autospec=True,side_effect=original) as read,
                      patch('openai_codex.Codex') as client):
                    with self.assertRaisesRegex(ValueError,'overlap'):
                        main(['--repo',str(self.w.root),'--material','synthetic','--context',str(path)])
                    print('SYNTHETIC_CLI_READ_ORDER',json.dumps(dict(variable=variable,context_reads=read.call_count)))
                    read.assert_not_called();client.assert_not_called()
        self.assertFalse(self.w.state_path.exists())

    def test_cli_context_excludes_native_homes_and_host_metadata_before_read(self):
        home=self.base/'user-home';external=self.base/'external-home';sqlite=self.base/'external-sqlite'
        paths=[home/'.codex/context.json',external/'context.json',sqlite/'context.json',
               self.w.root/'auth.json',self.w.root/'state_5.sqlite',self.w.root/'.codex/context.json',
               self.w.root/self.w.area/'.mas-runtime.json',self.w.root/self.w.area/'.inputs/provenance.json',
               self.w.root/self.w.area/'.native/sqlite/context.json',self.w.root/self.w.area/'.transactions/token/0']
        for path in paths:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(CONTEXT))
        alias=self.base/'context-alias.json';alias.symlink_to(paths[1])
        linked=self.base/'context-linked.json';os.link(paths[1],linked)
        paths.extend([alias,linked])
        original=Path.read_text
        for path in paths:
            with (self.subTest(context=str(path)),patch('pathlib.Path.home',return_value=home),
                  patch.dict(os.environ,CODEX_HOME=str(external),CODEX_SQLITE_HOME=str(sqlite)),
                  patch.object(Path,'read_text',autospec=True,side_effect=original) as read,
                  patch('openai_codex.Codex') as client):
                with self.assertRaisesRegex(ValueError,'native|host|metadata|unlinked'):
                    main(['--repo',str(self.w.root),'--material','synthetic','--context',str(path)])
                read.assert_not_called();client.assert_not_called()
        for path in paths:self.assertEqual(json.loads(path.read_text()),CONTEXT)

    def test_cli_preserves_approved_external_and_nested_context_bindings(self):
        original=Path.read_text
        for path in (self.base/'approved-context.json',self.w.root/'data/raw/auth.json'):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(CONTEXT))
            with (patch('pathlib.Path.home',return_value=self.base/'user-home'),patch.dict(os.environ,
                  CODEX_HOME=str(self.base/'external-home'),CODEX_SQLITE_HOME=str(self.base/'external-sqlite')),
                  patch.object(Path,'read_text',autospec=True,side_effect=original) as read,
                  patch('openai_codex.Codex') as client,patch('mas_runtime.CampaignRuntime.run') as run,
                  redirect_stdout(io.StringIO()) as output):
                main(['--repo',str(self.w.root),'--material','synthetic','--context',str(path)])
                read.assert_called_once_with(path,encoding='utf-8')
                self.assertEqual(json.loads(output.getvalue())['status'],'NOT_RUN')
                client.assert_not_called();run.assert_not_called()
        self.assertFalse(self.w.state_path.exists())

    def test_cli_reconsideration_requires_and_passes_stable_revision_identity(self):
        path = self.base/'context.json'
        path.write_text(json.dumps(CONTEXT))
        arguments = ['--repo', str(self.w.root),
                     '--material', 'synthetic', '--context', str(path)]
        with patch('mas_runtime.CampaignRuntime.run', return_value=None) as run:
            for suffix in [['--reconsider', 'New evidence'], ['--revision-id', 'revision-1']]:
                with self.subTest(suffix=suffix), self.assertRaises(SystemExit) as error:
                    main(arguments + suffix)
                self.assertEqual(error.exception.code, 2)
            run.assert_not_called()
            main(arguments + ['--live', '--reconsider', 'New evidence', '--revision-id', 'revision-1'])
            self.assertEqual(run.call_args.kwargs['revision_id'], 'revision-1')
            self.assertEqual(run.call_args.kwargs['reconsideration'], 'New evidence')
        self.assertFalse(self.w.state_path.exists())

    def test_runbook_synthetic_json_and_standalone_preparation(self):
        document = (self.w.root / 'docs/mas/python-runtime.md').read_text(encoding='utf-8')
        example = re.search(r'```json\n(.*?)\n```', document, re.S)
        self.assertIsNotNone(example)
        context = Context.model_validate_json(example.group(1))
        self.assertIn('SIMULATED', context.objective)
        self.assertTrue(all('synthetic' in value for name, value in context.materials.model_dump().items()
                            if name != 'nips_bath_solvent_wt_percent'))
        path = self.base / 'runbook-context.json'
        path.write_text(example.group(1), encoding='utf-8')
        result = subprocess.run(['uv', 'run', '--locked', '--no-sync', 'python',
            str(self.w.root / 'src/pipeline/mas_runtime.py'), '--repo', str(self.w.root), '--material', 'synthetic', '--context', str(path)],
            cwd=self.w.root, env={**os.environ,'UV_PROJECT_ENVIRONMENT':sys.prefix}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'NOT_RUN')
        self.assertFalse(self.w.state_path.exists())

    def test_effective_mcp_is_disabled_by_name_and_policies_have_no_model_override(self):
        self.prepare_sdk()
        replies = [subprocess.CompletedProcess([], 0, '[{"name":"inherited.server","enabled":true}]', ''),
                   subprocess.CompletedProcess([], 0, '[{"name":"inherited.server","enabled":false}]', '')]
        with self.w.lock(), patch('mas_runtime.subprocess.run', side_effect=replies) as inspect_mcp:
            with patch('openai_codex.Codex') as client:
                isolated_sdk(self.w)
            config = client.call_args.args[0]
            self.assertIn('"inherited.server"={enabled=false}', config.config_overrides[-1])
            self.assertIn('permissions.mas.network.enabled=false', config.config_overrides)
            self.assertNotIn('sandbox_mode="workspace-write"', config.config_overrides)
            self.assertEqual(config.env['CODEX_HOME'], str(self.w.root))
            self.assertIn('features.memories=false', config.config_overrides)
            self.assertEqual(inspect_mcp.call_count, 2)
            self.assertEqual(config.cwd, str(self.w.path(self.w.attempt_path(self.w.state['operations'][self.w.state['active']]))))
            self.assertEqual(config.env['MAS_SOURCE_ROOT'], str(self.w.root))
            self.assertNotIn('PILOT_ROOT', config.env)

    def test_unknown_still_enabled_mcp_aborts_before_client_without_leaking_output(self):
        self.prepare_sdk()
        response = subprocess.CompletedProcess([], 0, '[{"name":"private-name","enabled":true}]', '')
        with self.w.lock(), patch('mas_runtime.subprocess.run', return_value=response):
            with patch('openai_codex.Codex') as client:
                with self.assertRaisesRegex(RuntimeError, 'not verified') as error:
                    isolated_sdk(self.w)
                client.assert_not_called()
                self.assertNotIn('private-name', str(error.exception))

    def test_publication_conflicts_block_success_and_sdk_until_exact_resolution(self):
        for phase in ('write-tree','update-ref'):
            with self.subTest(phase=phase):
                self.w=Workspace(project(self.base/('race-'+phase)),CONTEXT['campaign'],'synthetic')
                self.sdk=FakeCodex(self.w);self.factory=unittest.mock.Mock(return_value=self.sdk)
                runtime=CampaignRuntime(self.w,Context.model_validate(CONTEXT),sdk_factory=self.factory)
                native=self.w.git;once=[True];target=self.w.root/'data/knowledge/synthetic'/TOPICS[0]
                def intercepted(*args,**kwargs):
                    value=native(*args,**kwargs)
                    if args[0]==phase and once[0]:once[0]=False;target.write_bytes(b'FOREIGN_RUNTIME_EDIT\n')
                    return value
                progress=io.StringIO()
                with redirect_stderr(progress),patch.object(self.w,'git',side_effect=intercepted),self.assertRaises(ValueError):runtime.run()
                self.assertNotIn('Knowledge published',progress.getvalue());self.assertNotIn('Accepted final action',progress.getvalue())
                self.assertIsNotNone(self.w.state['pending']);calls=self.factory.call_count;turns=len(self.sdk.prompts)
                self.factory.side_effect=AssertionError('Unresolved publication must precede SDK construction')
                with redirect_stderr(io.StringIO()),self.assertRaises(ValueError):runtime.run()
                self.assertEqual(self.factory.call_count,calls);self.assertEqual(len(self.sdk.prompts),turns)
                self.assertEqual(target.read_bytes(),b'FOREIGN_RUNTIME_EDIT\n')
                with self.w.lock():
                    entry=self.w.state['pending']['prepared']['data/knowledge/synthetic/'+TOPICS[0]]
                    target.write_bytes(self.w.path(entry['snapshot']).read_bytes())
                with redirect_stderr(io.StringIO()):self.assertIsNone(runtime.run())
                self.assertEqual(self.factory.call_count,calls);self.assertEqual(len(self.sdk.prompts),turns)
                self.assertIsNone(self.w.state['pending']);self.w._verify_frontier()

    def test_host_decision_collision_is_not_written_before_publication(self):
        self.bootstrap();before=self.w.head();self.sdk.action='hold';targets=[]
        def collision():
            record=self.w.state['operations'][self.w.state['active']]
            target=self.w.path(self.w.round_path(record)+'/decision.md');target.write_bytes(b'FOREIGN_HOST_RECORD\n');targets.append(target)
        self.sdk.hook=collision;progress=io.StringIO()
        with redirect_stderr(progress),self.assertRaisesRegex(ValueError,'host-generated'):self.observe()
        self.assertEqual(len(targets),1);self.assertEqual(targets[0].read_bytes(),b'FOREIGN_HOST_RECORD\n')
        self.assertEqual(self.w.head(),before);self.assertIsNone(self.w.state['pending'])
        self.assertNotIn('Accepted final action',progress.getvalue())

    def test_once_selected_sources_survive_preparation_retry_without_rewriting(self):
        native=self.w.publish;selected={};once=[True]
        def interrupted(record,files,**kwargs):
            observations=kwargs['observations'];self.assertTrue(observations)
            for path in observations:
                selected.setdefault(path,(files[path],self.w.path(path).stat().st_ino))
            canonical='data/knowledge/synthetic/'+TOPICS[0]
            matches=[p for p in observations if p.endswith('/author/'+TOPICS[0])]
            self.assertEqual(len(matches),1);self.assertIs(files[canonical],files[matches[0]])
            if once[0]:
                once[0]=False;self.w.path(next(iter(observations))).write_bytes(b'FOREIGN_SELECTED_SOURCE\n')
            write=self.w.write
            def no_rewrite(path,data):
                self.assertNotIn(path,observations,'Already authored files must remain KEEP')
                return write(path,data)
            with patch.object(self.w,'write',side_effect=no_rewrite):return native(record,files,**kwargs)
        with patch.object(self.w,'publish',side_effect=interrupted),redirect_stderr(io.StringIO()),self.assertRaises(ValueError):self.runtime.run()
        turns=len(self.sdk.prompts);calls=self.factory.call_count;self.factory.side_effect=AssertionError('Selection conflict before SDK')
        with redirect_stderr(io.StringIO()),self.assertRaisesRegex(ValueError,'Selected authored'):self.runtime.run(retry=True)
        self.assertEqual(self.factory.call_count,calls);self.assertEqual(len(self.sdk.prompts),turns)
        for path,(data,ino) in selected.items():
            self.assertEqual(self.w.path(path).stat().st_ino,ino);self.w.path(path).write_bytes(data)
        self.factory.side_effect=None
        with patch.object(self.w,'publish',side_effect=interrupted),redirect_stderr(io.StringIO()):self.assertIsNone(self.runtime.run())
        self.assertEqual(len(self.sdk.prompts),turns)
        for path,(data,ino) in selected.items():
            self.assertEqual(self.w.path(path).read_bytes(),data);self.assertEqual(self.w.path(path).stat().st_ino,ino)


if __name__ == '__main__':
    unittest.main()
