"""Synthetic native SDK-shaped collaboration; never construct a real SDK client."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
from openai_codex._run import TurnResult
from openai_codex import MethodNotFoundError
from openai_codex.generated.v2_all import Thread, ThreadReadResponse, Turn
from mas_contract import Adoption, Context, Contribution, Decision, MainReply, Review, TOPICS
from mas_runtime import CampaignRuntime, isolated_sdk, main
from mas_workspace import Workspace
from test_mas_contract import CONTEXT, PARAMS


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
            cliVersion='0.163.0', createdAt=0, updatedAt=0, cwd=str(self.w.root),
            ephemeral=False, modelProvider='openai', sessionId='synthetic', source='exec',
            status={'type': 'idle'}, preview='', turns=[]))
        fake = FakeThread(self, data)
        self.threads[identifier] = fake
        return fake

    def thread_start(self, **kwargs):
        self.starts.append(kwargs)
        return self.native_thread('main')

    def thread_resume(self, identifier, **kwargs):
        self.resumes.append((identifier, kwargs))
        return self.threads[identifier]

    @staticmethod
    def identifier(kind, role):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, 'synthetic-native:' + kind + ':' + role))

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
            child = self.threads.get(identifier) or self.native_thread(identifier, role, 'main')
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
            senderThreadId='main', receiverThreadIds=[] if self.modern else list(native_messages),
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
        source = Path(__file__).resolve().parents[1]
        self.w = Workspace(self.base / 'output', source, 'synthetic')
        self.sdk = FakeCodex(self.w)
        self.factory = unittest.mock.Mock(return_value=self.sdk)
        self.runtime = CampaignRuntime(self.w, Context.model_validate(CONTEXT), sdk_factory=self.factory)
        self.input = self.base / 'synthetic.csv'
        self.input.write_text('name,E,F\nSYNTHETIC,1,0.5\n')

    def bootstrap(self):
        self.assertIsNone(self.runtime.run())
        return self.w.state['knowledge_commit']

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
        self.assertIsNone(self.w.head())
        self.sdk.legacy_message_drift = False
        self.assertIsNone(self.runtime.run(retry=True))

    def test_native_participant_ambiguity_and_nonindependent_records_block_publication(self):
        for flag in ('remap_alias', 'duplicate_alias', 'unobserved_ref',
                     'interrupted_activity', 'shared_report'):
            with self.subTest(flag=flag):
                setattr(self.sdk, flag, True)
                with self.assertRaises(ValueError):
                    self.runtime.run(retry=True)
                self.assertIsNone(self.w.head())
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
                self.assertIsNone(self.w.head())
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
        bad = [str(self.input), str(self.w.source / 'README.md'),
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
        self.assertIsNone(self.w.head())
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
        self.assertIsNone(self.w.head())

    def observe(self):
        return self.runtime.run(observation_id='synthetic1', inputs={'table': self.input})

    def cold(self):
        self.w = Workspace(self.w.root, self.w.source, 'synthetic')
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
        self.assertIn(str(self.input), self.sdk.prompts[-1])
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
        main_thread = self.sdk.native_thread('main')
        with self.w.lock():
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
        self.assertIsNone(self.w.head())

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
        self.cold()
        decision = self.runtime.run()
        self.assertEqual(decision.knowledge_commit, adopted)
        self.assertEqual(len(self.sdk.starts), 1)
        self.assertIn(adopted, self.sdk.prompts[-1])

    def test_lost_knowledge_commit_ack_does_not_replay_adoption_or_native_turn(self):
        self.bootstrap()
        self.sdk.publish_next = True
        native_git = self.w.git
        def lose_ack(*args, **kwargs):
            result = native_git(*args, **kwargs)
            if args[0] == 'commit':
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
        self.assertEqual(self.w.git('rev-list', '--count', 'HEAD').stdout.strip(), b'3')

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
        changed = self.base / 'new.csv'
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
                new = fixture.base / 'new.csv'
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

    def test_second_named_campaign_reuses_bank_and_main_with_explicit_input_identity(self):
        bank = self.bootstrap()
        self.observe()
        original = json.loads(self.w.state_path.read_text())
        context = Context.model_validate(dict(CONTEXT, campaign='synthetic-second'))
        second = CampaignRuntime(self.w, context, sdk_factory=self.factory)
        new = self.base / 'second.csv'
        new.write_text('name,E,F\nSYNTHETIC-second,2,0.6\n')
        with self.assertRaises(ValueError):
            second.run(inputs={'table': new})
        decision = second.run(observation_id='second1', inputs={'table': new})
        self.assertEqual(decision.knowledge_commit, bank)
        self.assertEqual(self.w.state['thread_id'], original['thread_id'])
        self.assertEqual(len(self.sdk.starts), 1)
        active = self.w.state['operations'][self.w.state['active']]
        self.assertEqual(active['campaign'], 'synthetic-second')
        self.assertEqual(active['kind'], 'observation')
        self.assertEqual(active['inputs']['table']['path'], str(new))
        self.assertIn('data/results/synthetic-second/mas/rounds/', self.w.git('ls-files').stdout.decode())
        self.factory.reset_mock()
        self.assertEqual(second.run(inputs={'table': new}), decision)
        self.factory.assert_not_called()
        for identifier, record in original['operations'].items():
            self.assertEqual(self.w.state['operations'][identifier], record)

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

    def test_analysis_uv_uses_prepared_interpreter_and_output_cache(self):
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
        print('SYNTHETIC_ANALYSIS_ENV_CHECK', json.dumps(dict(argv=command, cwd=str(self.w.root),
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
                self.assertIsNone(self.w.head())
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
            main(['--workspace', str(self.w.root), '--source', str(self.w.source),
                  '--material', 'synthetic', '--context', str(context)])
            client.assert_not_called()
        self.assertFalse(self.w.root.exists())

    def test_cli_reconsideration_requires_and_passes_stable_revision_identity(self):
        path = self.base/'context.json'
        path.write_text(json.dumps(CONTEXT))
        arguments = ['--workspace', str(self.w.root), '--source', str(self.w.source),
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
        self.assertFalse(self.w.root.exists())

    def test_runbook_synthetic_json_and_standalone_preparation(self):
        document = (self.w.source / 'docs/mas/python-runtime.md').read_text(encoding='utf-8')
        example = re.search(r'```json\n(.*?)\n```', document, re.S)
        self.assertIsNotNone(example)
        context = Context.model_validate_json(example.group(1))
        self.assertIn('SIMULATED', context.objective)
        self.assertTrue(all('synthetic' in value for name, value in context.materials.model_dump().items()
                            if name != 'nips_bath_solvent_wt_percent'))
        path = self.base / 'runbook-context.json'
        path.write_text(example.group(1), encoding='utf-8')
        result = subprocess.run(['uv', 'run', '--locked', '--no-sync', 'python',
            str(self.w.source / 'src/pipeline/mas_runtime.py'), '--workspace', str(self.w.root),
            '--source', str(self.w.source), '--material', 'synthetic', '--context', str(path)],
            cwd=self.w.source, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'NOT_RUN')
        self.assertFalse(self.w.root.exists())

    def test_effective_mcp_is_disabled_by_name_and_policies_have_no_model_override(self):
        replies = [subprocess.CompletedProcess([], 0, '[{"name":"inherited.server","enabled":true}]', ''),
                   subprocess.CompletedProcess([], 0, '[{"name":"inherited.server","enabled":false}]', '')]
        with self.w.lock(), patch('mas_runtime.subprocess.run', side_effect=replies) as inspect_mcp:
            with patch('openai_codex.Codex') as client:
                isolated_sdk(self.w)
            config = client.call_args.args[0]
            self.assertIn('"inherited.server"={enabled=false}', config.config_overrides[-1])
            self.assertIn('sandbox_workspace_write.network_access=false', config.config_overrides)
            self.assertIn('features.memories=false', config.config_overrides)
            self.assertEqual(inspect_mcp.call_count, 2)
            self.assertEqual(config.cwd, str(self.w.root))
            self.assertEqual(config.env['MAS_SOURCE_ROOT'], str(self.w.source))
            self.assertNotIn('PILOT_ROOT', config.env)

    def test_unknown_still_enabled_mcp_aborts_before_client_without_leaking_output(self):
        response = subprocess.CompletedProcess([], 0, '[{"name":"private-name","enabled":true}]', '')
        with self.w.lock(), patch('mas_runtime.subprocess.run', return_value=response):
            with patch('openai_codex.Codex') as client:
                with self.assertRaisesRegex(RuntimeError, 'not verified') as error:
                    isolated_sdk(self.w)
                client.assert_not_called()
                self.assertNotIn('private-name', str(error.exception))


if __name__ == '__main__':
    unittest.main()
