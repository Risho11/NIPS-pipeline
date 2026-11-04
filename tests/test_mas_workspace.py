"""Real independent Git and filesystem failures, using fresh temporary roots."""
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/pipeline'))
from mas_contract import TOPICS
from mas_workspace import Workspace, key


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.w = Workspace(self.base / 'output', self.source, 'synthetic')

    def operation(self, kind='bootstrap'):
        record = dict(id='op1', campaign='campaign', kind=kind, status='running',
                      turn_id='turn1', turns=[], decision=None)
        self.w.state['operations']['op1'] = record
        self.w.state['active'] = 'op1'
        self.w.save()
        return record

    def files(self, record):
        return {**{f'data/knowledge/synthetic/{t}': 'Synthetic theory; no observation.\n' for t in TOPICS},
                self.w.round_path(record) + '/adoption.json': '{"synthetic":true}\n'}

    def test_explicit_separate_paths_and_escape_rejection(self):
        with self.assertRaises(ValueError):
            Workspace(self.source / 'output', self.source, 'synthetic')
        with self.assertRaises(ValueError):
            Workspace(self.base, self.source, 'synthetic')
        with self.assertRaises(ValueError):
            Workspace(self.base / 'output', self.source, 'synthetic', protected_roots=[self.base])
        for name in ['../bad', '/absolute', '']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.w.path(name)
        for name in ['../escape', 'NUL', 'x/y', '']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                key(name)

    def test_lock_excludes_second_writer_and_releases_after_error(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
            with self.w.lock():
                other = Workspace(self.w.root, self.source, 'synthetic')
                with self.assertRaisesRegex(RuntimeError, 'locked'):
                    with other.lock():
                        self.fail('Second writer acquired lock')
                raise RuntimeError('synthetic failure')
        with Workspace(self.w.root, self.source, 'synthetic').lock() as cold:
            self.assertIsNone(cold.state['thread_id'])

    def test_caller_lock_serializes_journal_without_rewriting_native_state(self):
        with self.w.lock():
            original = self.w.state_path.read_bytes()
        with self.w.file_lock('.pipeline.lock'):
            other = Workspace(self.w.root, self.source, 'synthetic')
            with self.assertRaisesRegex(RuntimeError, 'locked'):
                with other.file_lock('.pipeline.lock'):
                    self.fail('Concurrent caller journal owner')
            with other.lock():
                self.assertEqual(other.state_path.read_bytes(), original)
        self.assertEqual(self.w.state_path.read_bytes(), original)

    def test_git_root_is_compared_by_normalized_path_identity(self):
        original_git = self.w.git
        def normalized_git(*args, **kwargs):
            result = original_git(*args, **kwargs)
            if args == ('rev-parse', '--show-toplevel') and result.returncode == 0:
                return subprocess.CompletedProcess([], 0, (str(self.w.root) + '/.\n').encode(), b'')
            return result
        with patch.object(self.w, 'git', side_effect=normalized_git):
            with self.w.lock():
                self.assertEqual(self.w.state['source'], str(self.source))

    def test_ambient_git_environment_cannot_redirect_publication_to_source(self):
        with patch.dict(os.environ, {'GIT_DIR': str(self.source / '.git'),
                                    'GIT_WORK_TREE': str(self.source),
                                    'GIT_INDEX_FILE': str(self.source / 'index')}):
            with self.w.lock():
                record = self.operation()
                self.w.publish(record, self.files(record), knowledge=True)
        self.assertEqual(list(self.source.iterdir()), [])

    def test_nested_repository_rejected_before_output_mutation(self):
        foreign = self.base / 'foreign'
        (foreign / '.git').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'another repository'):
            Workspace(foreign / 'output', self.source, 'synthetic')
        self.assertFalse((foreign / 'output').exists())

    def test_missing_git_history_is_not_reinitialized(self):
        with self.w.lock():
            record = self.operation()
            self.w.publish(record, self.files(record), knowledge=True)
        (self.w.root / '.git').rename(self.w.root / 'preserved-git')
        with self.assertRaisesRegex(ValueError, 'history missing'):
            with Workspace(self.w.root, self.source, 'synthetic').lock():
                self.fail('Missing history was silently reinitialized')
        self.assertFalse((self.w.root / '.git').exists())

    def test_atomic_publication_commit_format_and_main_only_paths(self):
        with self.w.lock():
            record = self.operation()
            original_source = list(self.source.iterdir())
            head = self.w.publish(record, self.files(record), knowledge=True)
            self.assertEqual(head, self.w.head())
            self.assertEqual(self.w.state['knowledge_commit'], head)
            self.assertEqual(record['status'], 'completed')
            self.assertEqual(record['turns'], ['turn1'])
            self.assertIsNone(record['turn_id'])
            subject = self.w.git('log', '-1', '--format=%s').stdout.decode().strip()
            self.assertRegex(subject, r'^\d{6}-\d{2}-\d{2} docs adopt MAS knowledge [a-f0-9]+$')
            tracked = set(self.w.git('ls-files').stdout.decode().splitlines())
            self.assertEqual(tracked, set(self.files(record)))
            self.assertEqual(list(self.source.iterdir()), original_source)
            self.assertFalse(self.w.git('status', '--porcelain', '--untracked-files=no').stdout)
            with self.assertRaises(ValueError):
                self.w.publish(record, {'raw/measurements.csv': 'private'}, knowledge=True)

    def test_relevant_native_markdown_records_are_in_the_same_history(self):
        with self.w.lock():
            record = self.operation()
            report = self.w.round_path(record) + '/review/assessment.md'
            self.w.write(report, 'Actual synthetic review reasoning.\n')
            files = dict(self.files(record), **{report: self.w.proposal(record, report).read_text()})
            head = self.w.publish(record, files, knowledge=True)
            self.assertEqual(self.w.git('show', f'{head}:{report}').stdout.decode(), files[report])
            bad = self.w.round_path(record) + '/inputs/secret.md'
            self.w.write(bad, 'Excluded original input.\n')
            with self.assertRaises(ValueError):
                self.w.proposal(record, bad)

    def test_precommit_failure_retains_pending_and_cold_recovery(self):
        with self.w.lock():
            record = self.operation()
            native_git = self.w.git
            def fail_commit(*args, **kwargs):
                if args[0] == 'commit':
                    raise RuntimeError('simulated commit failure')
                return native_git(*args, **kwargs)
            with patch.object(self.w, 'git', side_effect=fail_commit):
                with self.assertRaisesRegex(RuntimeError, 'commit failure'):
                    self.w.publish(record, self.files(record), knowledge=True)
            pending = json.loads(self.w.state_path.read_text())['pending']
            self.assertIsNotNone(pending)
            self.assertIsNone(self.w.head())
        with Workspace(self.w.root, self.source, 'synthetic').lock() as cold:
            head = cold.recover_publication()
            self.assertEqual(cold.state['knowledge_commit'], head)
            self.assertIsNone(cold.state['pending'])
            self.assertEqual(cold.git('log', '-1', '--format=%s').stdout.decode().strip(), pending['message'])

    def test_lost_commit_ack_recovers_without_duplicate_commit(self):
        with self.w.lock():
            record = self.operation()
            native_git = self.w.git
            def lose_ack(*args, **kwargs):
                result = native_git(*args, **kwargs)
                if args[0] == 'commit':
                    raise RuntimeError('lost commit acknowledgement')
                return result
            with patch.object(self.w, 'git', side_effect=lose_ack):
                with self.assertRaisesRegex(RuntimeError, 'lost commit'):
                    self.w.publish(record, self.files(record), knowledge=True)
            committed = self.w.head()
        with Workspace(self.w.root, self.source, 'synthetic').lock() as cold:
            self.assertEqual(cold.recover_publication(), committed)
            self.assertEqual(cold.git('rev-list', '--count', 'HEAD').stdout.strip(), b'1')

    def test_lost_ack_rejects_same_subject_commit_with_changed_accepted_bytes(self):
        with self.w.lock():
            record = self.operation()
            native_git = self.w.git
            def fail_commit(*args, **kwargs):
                if args[0] == 'commit':
                    raise RuntimeError('synthetic precommit failure')
                return native_git(*args, **kwargs)
            with patch.object(self.w, 'git', side_effect=fail_commit):
                with self.assertRaisesRegex(RuntimeError, 'precommit'):
                    self.w.publish(record, self.files(record), knowledge=True)
            pending = json.loads(self.w.state_path.read_text())['pending']
            target = 'data/knowledge/synthetic/' + TOPICS[0]
            self.w.write(target, 'Foreign unreviewed replacement.\n')
            self.w.git('add', '--', target)
            self.w.git('commit', '-m', pending['message'])
            with self.assertRaises(ValueError):
                self.w.recover_publication()
            self.assertEqual(self.w.state['pending'], pending)
            self.assertIsNone(self.w.state['knowledge_commit'])
            self.assertEqual(record['status'], 'running')
            self.assertEqual(self.w.path(target).read_text(), 'Foreign unreviewed replacement.\n')

    def pending_publication(self, workspace):
        self.w = workspace
        record = self.operation()
        native_git = workspace.git
        def fail_commit(*args, **kwargs):
            if args[0] == 'commit':
                raise RuntimeError('synthetic precommit failure')
            return native_git(*args, **kwargs)
        with patch.object(workspace, 'git', side_effect=fail_commit):
            with self.assertRaisesRegex(RuntimeError, 'precommit'):
                workspace.publish(record, self.files(record), knowledge=True)
        return record, json.loads(workspace.state_path.read_text())['pending']

    def test_lost_ack_requires_every_expected_blob_mode_and_path(self):
        for defect in ['missing-topic', 'missing-adoption', 'changed-adoption', 'mode', 'extra-path']:
            with self.subTest(defect=defect):
                w = Workspace(self.base / defect, self.source, 'synthetic')
                with w.lock():
                    record, pending = self.pending_publication(w)
                    topic = 'data/knowledge/synthetic/' + TOPICS[0]
                    adoption = w.round_path(record) + '/adoption.json'
                    if defect.startswith('missing'):
                        w.git('update-index', '--force-remove', '--', topic if defect == 'missing-topic' else adoption)
                    elif defect == 'changed-adoption':
                        w.write(adoption, '{"foreign":true}\n')
                        w.git('add', '--', adoption)
                    elif defect == 'mode':
                        w.git('update-index', '--chmod=+x', '--', topic)
                    else:
                        w.write('foreign.md', 'Not adopted.\n')
                        w.git('add', '--', 'foreign.md')
                    w.git('commit', '-m', pending['message'])
                    head = w.head()
                with Workspace(w.root, self.source, 'synthetic').lock() as cold:
                    with self.assertRaisesRegex(ValueError, 'payload'):
                        cold.recover_publication()
                    self.assertEqual(cold.head(), head)
                    self.assertEqual(cold.state['pending'], pending)
                    self.assertIsNone(cold.state['knowledge_commit'])
                    self.assertEqual(cold.state['operations'][record['id']]['status'], 'running')

    def test_precommit_conflicting_working_or_index_entries_are_preserved(self):
        for defect in ['working-bytes', 'working-mode', 'index-bytes', 'snapshot']:
            with self.subTest(defect=defect):
                w = Workspace(self.base / defect, self.source, 'synthetic')
                with w.lock():
                    record, pending = self.pending_publication(w)
                    topic = 'data/knowledge/synthetic/' + TOPICS[0]
                    if defect == 'snapshot':
                        w.write(pending['prepared'][topic]['snapshot'], 'Changed journal payload.\n')
                    elif defect == 'working-mode':
                        w.path(topic).chmod(0o700)
                    else:
                        w.write(topic, 'Conflicting external edit.\n')
                        if defect == 'index-bytes':
                            w.git('add', '--', topic)
                            w.write(topic, self.files(record)[topic])
                    before = {str(p.relative_to(w.root)): p.read_bytes() for p in w.root.rglob('*')
                              if p.is_file() and '.git' not in p.relative_to(w.root).parts}
                    with self.assertRaisesRegex(ValueError, 'changed|Conflicting'):
                        w.recover_publication()
                    self.assertEqual(w.state['pending'], pending)
                    self.assertIsNone(w.head())
                    self.assertEqual({name: w.path(name).read_bytes() for name in before}, before)

    def test_interrupted_writes_recover_original_and_accepted_mixed_paths(self):
        with self.w.lock():
            record = self.operation()
            report = self.w.round_path(record) + '/author.md'
            self.w.write(report, 'Original accepted report.\n')
            files = dict(self.files(record), **{report: 'Original accepted report.\n'})
            native_write = self.w.write
            def interrupted(relative, text):
                if relative == 'data/knowledge/synthetic/' + TOPICS[1]:
                    raise OSError('synthetic interrupted write')
                return native_write(relative, text)
            with patch.object(self.w, 'write', side_effect=interrupted):
                with self.assertRaisesRegex(OSError, 'interrupted'):
                    self.w.publish(record, files, knowledge=True)
        with Workspace(self.w.root, self.source, 'synthetic').lock() as cold:
            self.assertIsNotNone(cold.recover_publication())
            self.assertEqual(cold.state['operations'][record['id']]['status'], 'completed')
            self.assertEqual(cold.path(report).read_text(), files[report])

    def test_missing_preexisting_report_conflicts_instead_of_being_recreated(self):
        with self.w.lock():
            record = self.operation()
            report = self.w.round_path(record) + '/author.md'
            self.w.write(report, 'Accepted report.\n')
            native_git = self.w.git
            def fail_commit(*args, **kwargs):
                if args[0] == 'commit':
                    raise RuntimeError('synthetic precommit failure')
                return native_git(*args, **kwargs)
            with patch.object(self.w, 'git', side_effect=fail_commit):
                with self.assertRaisesRegex(RuntimeError, 'precommit'):
                    self.w.publish(record, dict(self.files(record), **{report: 'Accepted report.\n'}), knowledge=True)
            self.w.path(report).unlink()
            pending = json.loads(self.w.state_path.read_text())['pending']
            with self.assertRaises(ValueError):
                self.w.recover_publication()
            self.assertFalse(self.w.path(report).exists())
            self.assertEqual(self.w.state['pending'], pending)

    def test_unknown_stage_existing_repository_and_retired_state_are_rejected(self):
        with self.w.lock():
            self.w.write('unrelated.md', 'Not adopted\n')
            self.w.git('add', '--', 'unrelated.md')
        with self.assertRaisesRegex(ValueError, 'staged'):
            with Workspace(self.w.root, self.source, 'synthetic').lock():
                self.fail('Unknown staged input was adopted')
        fresh = Workspace(self.base / 'retired', self.source, 'synthetic')
        fresh.root.mkdir()
        fresh.write('mas/state.json', '{"stages":{}}')
        with self.assertRaisesRegex(ValueError, 'Retired'):
            with fresh.lock():
                self.fail('Retired state was accepted')
        self.assertEqual(fresh.path('mas/state.json').read_text(), '{"stages":{}}')

    def test_symlink_outputs_and_hardlinks_are_rejected_before_read(self):
        self.w.root.mkdir()
        outside = self.base / 'outside.md'
        outside.write_text('original')
        # Exercise actual links where this platform permits creating them.
        if os.name == 'posix':
            (self.w.root / 'alias.md').symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                self.w.path('alias.md')
        else:
            with patch.object(Path, 'is_symlink', return_value=True):
                with self.assertRaisesRegex(ValueError, 'Symlink'):
                    self.w.path('alias.md')
        os.link(outside, self.w.root / 'hard.md')
        with self.assertRaisesRegex(ValueError, 'Hard-linked'):
            self.w.path('hard.md')
        self.assertEqual(outside.read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
