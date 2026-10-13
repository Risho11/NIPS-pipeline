"""HTTP submission with durable, at-most-once dispatch (no hardware imports)."""
import hashlib
import json
import os
from pathlib import Path
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler


class RequestJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.failed = False
        self.session = str(uuid.uuid4())
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            # Fail closed on invalid journals: never silently forget dispatched work.
            uuid.UUID(self.data['journal_id'])
            if not isinstance(self.data['requests'], dict):
                raise ValueError('Invalid request journal')
        else:
            self.data = {'journal_id': str(uuid.uuid4()), 'requests': {}}
            self._save()

    def _save(self):
        try:
            self._write_journal()
        except Exception:
            self.failed = True
            raise

    def _write_journal(self):
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as handle:
            json.dump(self.data, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        if os.name != 'nt':
            directory = os.open(str(self.path.parent), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def submit(self, request_id, parameters, run):
        digest = hashlib.sha256(json.dumps(parameters, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self.lock:
            if self.failed:
                raise RuntimeError('Journal persistence failed; manual inspection required')
            existing = self.data['requests'].get(request_id)
            if existing:
                if existing['digest'] != digest:
                    return 409, {'error': 'Request ID reused with different parameters; inspect checkpoint.'}
                if existing['status'] == 'failed' or (
                    existing['status'] != 'completed' and existing['session'] != self.session
                ):
                    return 409, {'error': 'Previous run failed or robot restarted mid-request. Inspect robot state; do not create a new ID automatically.'}
                return 200, {'request_id': request_id, 'status': existing['status'], 'duplicate': True}
            self.data['requests'][request_id] = {
                'digest': digest, 'status': 'accepted', 'session': self.session,
            }
            self._save()  # Must reach disk before any physical action.
            try:
                threading.Thread(target=self._execute, args=(request_id, parameters, run)).start()
            except Exception:
                self.data['requests'][request_id]['status'] = 'failed'
                self._save()
                raise
            print(f'[robot] request_id={request_id} stage=accepted', flush=True)
            return 202, {'request_id': request_id, 'status': 'accepted', 'duplicate': False}

    def _execute(self, request_id, parameters, run):
        status = 'completed'
        try:
            run(parameters)
        except BaseException:
            status = 'failed'
            traceback.print_exc()
        finally:
            with self.lock:
                self.data['requests'][request_id]['status'] = status
                self._save()
            print(f'[robot] request_id={request_id} stage={status}', flush=True)


def make_handler(journal, run):
    class RequestHandler(BaseHTTPRequestHandler):
        def _reply(self, code, body):
            payload = json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except OSError:
                # Acceptance was persisted and worker dispatched before replying.
                print('[robot] reply lost; retry with the same request ID.', flush=True)

        def do_GET(self):
            if self.path != '/health':
                self._reply(404, {'error': 'Unknown endpoint'})
                return
            if journal.failed:
                self._reply(503, {'error': 'Journal persistence failed; inspect robot logs.'})
                return
            self._reply(200, {'service': 'membrane-robot', 'idempotency_version': 1,
                              'journal_id': journal.data['journal_id']})

        def do_POST(self):
            if self.path != '/run':
                self._reply(404, {'error': 'Unknown endpoint'})
                return
            try:
                self.connection.settimeout(10)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError('Invalid payload length')
                request_id = self.headers.get('X-Request-ID', '')
                uuid.UUID(request_id)
                if self.headers.get('X-Journal-ID') != journal.data['journal_id']:
                    self._reply(409, {'error': 'Journal identity changed. Inspect robot state before resuming.'})
                    return
                parameters = json.loads(self.rfile.read(length))
                if not isinstance(parameters, dict):
                    raise ValueError('Parameters must be an object')
                json.dumps(parameters, allow_nan=False)
            except (ValueError, OSError) as exc:
                self._reply(400, {'error': str(exc)})
                return
            try:
                code, body = journal.submit(request_id, parameters, run)
            except Exception:
                traceback.print_exc()
                self._reply(500, {'error': 'Dispatch/journal error; inspect robot logs. Preserve request ID.'})
                return
            self._reply(code, body)
    return RequestHandler
