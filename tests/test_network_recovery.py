"""Hardware/API-free recovery tests; loopback HTTP only."""
import ast
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = load('recovery_client', 'src/pipeline/url_29.py')
robot = load('recovery_robot', 'OT2_Server_2026-06-11/lib/request_server.py')


@contextmanager
def serving(journal, run):
    server = HTTPServer(('127.0.0.1', 0), robot.make_handler(journal, run))
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with patch.object(client, 'BASE_URL', f'http://127.0.0.1:{server.server_port}'):
            yield
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class RobotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'requests.json'
        self.journal = robot.RequestJournal(self.path)
        self.request_id = str(uuid.uuid4())

    def test_health_is_read_only_and_lost_ack_does_not_repeat_action(self):
        called = Mock()
        real_open = urllib.request.urlopen
        lost = [False]
        def open_with_lost_reply(request, **kwargs):
            response = real_open(request, **kwargs)
            if isinstance(request, urllib.request.Request) and not lost[0]:
                lost[0] = True
                response.read()
                response.close()
                raise TimeoutError('reply lost after acceptance')
            return response
        with serving(self.journal, called), patch.object(client.time, 'sleep'):
            before = self.path.read_bytes()
            health = client.check_health()
            self.assertEqual(self.path.read_bytes(), before)
            called.assert_not_called()
            with patch.object(client.urllib.request, 'urlopen', side_effect=open_with_lost_reply):
                reply = json.loads(client.run_test({'bath_temp': 20}, request_id=self.request_id,
                                                  journal_id=health['journal_id']))
            self.assertTrue(reply['duplicate'])
        called.assert_called_once_with({'bath_temp': 20})

    def test_pending_restart_and_parameter_conflict_never_dispatch(self):
        # Simulate crash after durable acceptance but before worker execution.
        with patch.object(robot.threading, 'Thread') as worker:
            self.journal.submit(self.request_id, {'x': 1}, Mock())
            worker.return_value.start.assert_called_once()
        restarted = robot.RequestJournal(self.path)
        run = Mock()
        self.assertEqual(restarted.submit(self.request_id, {'x': 1}, run)[0], 409)
        self.assertEqual(restarted.submit(self.request_id, {'x': 2}, run)[0], 409)
        run.assert_not_called()

    def test_completed_request_survives_restart(self):
        with patch.object(robot.threading, 'Thread'):
            self.journal.submit(self.request_id, {'x': 1}, Mock())
        self.journal._execute(self.request_id, {'x': 1}, Mock())
        restarted = robot.RequestJournal(self.path)
        run = Mock()
        self.assertEqual(restarted.submit(self.request_id, {'x': 1}, run)[0], 200)
        run.assert_not_called()

    def test_simultaneous_duplicates_dispatch_once(self):
        run = Mock()
        results = []
        # Keep the physical worker mocked, while using real caller threads.
        thread_class = threading.Thread
        with patch.object(robot.threading, 'Thread') as worker:
            callers = [thread_class(target=lambda: results.append(
                self.journal.submit(self.request_id, {'x': 1}, run))) for _ in range(5)]
            for caller in callers:
                caller.start()
            for caller in callers:
                caller.join()
            worker.return_value.start.assert_called_once()
        self.assertEqual(len(results), 5)
        self.assertEqual(sum(code == 202 for code, _ in results), 1)

    def test_failed_worker_is_not_replayed(self):
        with patch.object(robot.threading, 'Thread'):
            self.journal.submit(self.request_id, {}, Mock())
        with patch.object(robot.traceback, 'print_exc'):
            self.journal._execute(self.request_id, {}, Mock(side_effect=RuntimeError('hardware failure')))
        run = Mock()
        self.assertEqual(self.journal.submit(self.request_id, {}, run)[0], 409)
        run.assert_not_called()

    def test_persistence_failure_blocks_dispatch_and_future_acceptance(self):
        run = Mock()
        with patch.object(robot.os, 'replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.journal.submit(self.request_id, {'x': 1}, run)
        with self.assertRaises(RuntimeError):
            self.journal.submit(self.request_id, {'x': 1}, run)
        run.assert_not_called()

    def test_bad_routes_and_missing_id_do_not_start_robot(self):
        run = Mock()
        with serving(self.journal, run):
            for path, headers, code in [('/wrong', {}, 404), ('/run', {}, 400),
                    ('/run', {'X-Request-ID': self.request_id, 'X-Journal-ID': 'wrong'}, 409)]:
                req = urllib.request.Request(client.BASE_URL + path, data=b'{}', headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(req)
                self.assertEqual(error.exception.code, code)
                error.exception.close()
        run.assert_not_called()

    def test_deleted_journal_blocks_old_client(self):
        old_id = self.journal.data['journal_id']
        self.path.unlink()
        replacement = robot.RequestJournal(self.path)
        run = Mock()
        with serving(replacement, run):
            with self.assertRaisesRegex(RuntimeError, 'journal changed'):
                client.run_test({}, request_id=self.request_id, journal_id=old_id)
        run.assert_not_called()


class ClientTests(unittest.TestCase):
    def test_preflight_exhaustion_never_posts(self):
        with patch.object(client.urllib.request, 'urlopen', side_effect=urllib.error.URLError(socket.gaierror('DNS'))) as send, patch.object(client.time, 'sleep') as wait:
            with self.assertRaisesRegex(RuntimeError, 'no POST sent'):
                client.run_test({})
        self.assertEqual(send.call_count, 5)
        self.assertEqual([call.kwargs['timeout'] for call in send.call_args_list], [60] * 5)
        self.assertEqual([call.args[0] for call in wait.call_args_list], [375] * 4)
        self.assertTrue(all(isinstance(c.args[0], str) and c.args[0].endswith('/health') for c in send.call_args_list))

    def test_ambiguous_retries_reuse_id_and_are_bounded(self):
        health = {'journal_id': str(uuid.uuid4())}
        with patch.object(client, 'check_health', return_value=health), patch.object(client.time, 'sleep'), patch.object(client.urllib.request, 'urlopen', side_effect=TimeoutError('unknown outcome')) as send:
            with self.assertRaisesRegex(RuntimeError, 'outcome-unknown'):
                client.run_test({})
        self.assertEqual(send.call_count, 3)
        ids = [c.args[0].get_header('X-request-id') for c in send.call_args_list]
        self.assertEqual(len(set(ids)), 1)
        self.assertFalse(client._proven_before_send(TimeoutError()))
        self.assertTrue(client._proven_before_send(urllib.error.URLError(ConnectionRefusedError())))

    def test_legacy_health_rejected_without_post(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock()
        response.read.return_value = b'{}'
        with patch.object(client.urllib.request, 'urlopen', return_value=response) as send:
            with self.assertRaisesRegex(RuntimeError, 'duplicate protection'):
                client.run_test({})
        self.assertEqual(send.call_count, 1)

    def test_http_rejection_is_not_retried(self):
        from io import BytesIO
        rejection = urllib.error.HTTPError('http://robot/run', 409, 'conflict', {}, BytesIO(b'Inspect robot state'))
        with patch.object(client, 'check_health', return_value={'journal_id': str(uuid.uuid4())}), patch.object(client.urllib.request, 'urlopen', side_effect=rejection) as send:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 409'):
                client.run_test({})
        self.assertEqual(send.call_count, 1)

    def test_checkpoint_resume_reuses_saved_id_and_blocks_legacy_unknown(self):
        tree = ast.parse((ROOT / 'src/pipeline/run_loop.py').read_text(encoding='utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_run_pipeline_and_trigger_next')
        body = next(n for n in fn.body if isinstance(n, ast.Try)).body
        start = next(i for i, n in enumerate(body) if isinstance(n, ast.If) and 'submission_started' in ast.unparse(n.test))
        end = next(i for i, n in enumerate(body) if isinstance(n, ast.Expr) and '"next_run_submitted"' in ast.unparse(n).replace("'", '"'))
        code = compile(ast.Module(body=body[start:end + 1], type_ignores=[]), '<checkpoint submission>', 'exec')
        state = {'completed_stages': []}
        api = Mock()
        api.check_health.return_value = {'journal_id': str(uuid.uuid4())}
        snapshots = []
        def complete(condition, data, stage):
            if stage not in data['completed_stages']:
                data['completed_stages'].append(stage)
            snapshots.append(json.loads(json.dumps(data)))
        env = dict(state=state, completed=state['completed_stages'], url=api, uuid=uuid,
                   condition_name='test', new_params={}, _complete_stage=complete)
        api.check_health.side_effect = RuntimeError('offline')
        with self.assertRaisesRegex(RuntimeError, 'offline'):
            exec(code, env)
        self.assertEqual(snapshots, [])
        api.run_test.assert_not_called()
        api.check_health.side_effect = None
        api.run_test.side_effect = TimeoutError('lost reply')
        with self.assertRaises(TimeoutError):
            exec(code, env)
        first_id = snapshots[0]['submission_request_id']
        api.run_test.side_effect = None
        exec(code, env)
        self.assertEqual(api.run_test.call_args.kwargs['request_id'], first_id)
        self.assertIn('next_run_submitted', state['completed_stages'])
        state.pop('submission_request_id')
        with self.assertRaisesRegex(RuntimeError, 'unknown outcome'):
            exec(code, env)


class QualityTests(unittest.TestCase):
    def test_connection_retries_only_and_bounded(self):
        class ConnectionErrorForTest(Exception):
            pass
        sdk = types.ModuleType('openai')
        sdk.OpenAI = Mock()
        sdk.APIConnectionError = ConnectionErrorForTest
        prompt = types.ModuleType('system_prompt')
        prompt.QUALITY_CHECKER_PROMPT = 'test'
        with patch.dict(sys.modules, openai=sdk, system_prompt=prompt):
            quality = load('quality_under_test', 'src/pipeline/membrane_quality_llm.py')
        response = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='ok'))])
        for errors, count, succeeds in [([ConnectionErrorForTest(), response], 2, True),
                                       ([ConnectionErrorForTest()] * 3, 3, False),
                                       ([ValueError('invalid API request')], 1, False)]:
            fake = Mock()
            fake.__enter__ = Mock(return_value=fake)
            fake.__exit__ = Mock(return_value=False)
            fake.chat.completions.create.side_effect = errors
            with patch.object(quality, '_client', return_value=fake), patch.object(quality, '_encode_image', return_value='image'), patch.object(quality.time, 'sleep'):
                if succeeds:
                    self.assertEqual(quality.Generate_quality_report('unused'), 'ok')
                else:
                    with self.assertRaises((ConnectionErrorForTest, ValueError)):
                        quality.Generate_quality_report('unused')
            self.assertEqual(fake.chat.completions.create.call_count, count)


if __name__ == '__main__':
    unittest.main()
