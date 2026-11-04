"""Explicit independent campaign workspace, portable locking and durable publication."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

from mas_contract import TOPICS


def key(value):
    if (not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value)
            or value.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                                *(f"LPT{i}" for i in range(10))}):
        raise ValueError("Invalid portable material/campaign identifier")
    return value


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


class Workspace:
    """One material's knowledge and persistent Main, across caller-named campaigns.

    Construction is read-only. Mutation requires lock(); kernel locks release on
    process exit on Windows and POSIX. No stale lock deletion or Git rollback.
    """
    def __init__(self, root, source, material, *, protected_roots=()):
        root, source = Path(root), Path(source)
        if root.is_symlink() or not source.is_dir():
            raise ValueError("Regular output root and existing source required")
        self.root, self.source = root.resolve(), source.resolve()
        self.material = key(material)
        for protected in (self.source, *(Path(p).resolve() for p in protected_roots)):
            if self.root.is_relative_to(protected) or protected.is_relative_to(self.root):
                raise ValueError("Output must be separate from source and protected data")
        if any((parent / '.git').exists() for parent in self.root.parents):
            raise ValueError("Output is inside another repository")
        if (self.root / '.git').exists() and not (self.root / '.mas-state.json').is_file():
            raise ValueError("Unrecognized existing repository; preserve and inspect")
        self.state_path = self.root / '.mas-state.json'
        self.state = None

    def path(self, relative):
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts or not p.parts:
            raise ValueError("Workspace-relative path required")
        target = self.root / p
        for part in (target, *target.parents):
            if part == self.root:
                break
            if part.is_symlink():
                raise ValueError("Symlink output forbidden")
        if not target.resolve().is_relative_to(self.root):
            raise ValueError("Escaping output path")
        if target.is_file() and target.stat().st_nlink != 1:
            raise ValueError("Hard-linked output forbidden")
        return target

    def write(self, relative, text):
        p = self.path(relative)
        p.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=p.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text.encode('utf-8') if isinstance(text, str) else text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, p)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self):
        self.write('.mas-state.json', json.dumps(self.state, indent=2, allow_nan=False) + '\n')

    @contextmanager
    def lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.path('.mas.lock')
        with lock_path.open('a+b') as stream:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                if not lock_path.stat().st_size:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                def acquire():
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                def release():
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            elif os.name == 'posix':
                import fcntl
                acquire = lambda: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                release = lambda: fcntl.flock(stream, fcntl.LOCK_UN)
            else:
                raise RuntimeError("Workspace locking supports Windows and POSIX only")
            try:
                acquire()
            except OSError as exc:
                raise RuntimeError("Campaign workspace is already locked") from exc
            try:
                self._open()
                yield self
            finally:
                release()

    def git(self, *args, check=True, input=None):
        # Never inherit GIT_DIR, GIT_WORK_TREE, external index or global hooks.
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
        command = ['git', '-c', f'core.hooksPath={self.root / ".git/disabled-hooks"}',
                   '-c', 'commit.gpgsign=false', '-c', 'core.fsmonitor=false',
                   '-c', 'core.autocrlf=false', '-c', 'core.filemode=true',
                   '-c', 'user.name=MAS Main', '-c', 'user.email=mas@localhost',
                   '-c', 'init.templateDir=', *args]
        p = subprocess.run(command, cwd=self.root, env=env, input=input, capture_output=True, timeout=60)
        if check and p.returncode:
            raise RuntimeError(f"Workspace Git failed: {args[0]}")
        return p

    def head(self):
        p = self.git('rev-parse', '--verify', 'HEAD', check=False)
        return p.stdout.decode().strip() if p.returncode == 0 else None

    def _open(self):
        if self.path('data/results').exists():
            # Retired per-campaign checkpoints are never silently accepted.
            if any(self.path('data/results').glob('*/mas/state.json')):
                raise ValueError("Retired MAS state must be preserved and explicitly reviewed")
        if self.path('mas/state.json').exists() or self.path('state.json').exists():
            raise ValueError("Retired MAS state")
        if self.state_path.exists():
            self.state = json.loads(self.path('.mas-state.json').read_text())
            if (self.state.get('version') != 1 or self.state.get('source') != str(self.source)
                    or self.state.get('material') != self.material):
                raise ValueError("Unsupported state or workspace binding changed")
        else:
            self.state = dict(version=1, source=str(self.source), material=self.material,
                              thread_id=None, head=None, knowledge_commit=None,
                              active=None, operations={}, pending=None, failures=[])
        dotgit = self.path('.git')
        if not dotgit.exists():
            if self.state['head'] is not None:
                raise ValueError("Existing Git history missing; preserve and inspect")
            parent = self.git('rev-parse', '--show-toplevel', check=False)
            if parent.returncode == 0:
                raise ValueError("Output is inside another repository")
            self.git('init')
        if (not dotgit.is_dir()
                or Path(self.git('rev-parse', '--show-toplevel').stdout.decode().strip()).resolve() != self.root):
            raise ValueError("Independent output repository required")
        if self.git('remote').stdout.strip():
            raise ValueError("Workspace remotes forbidden")
        if self.state.get('pending') is None:
            self.check_clean()
            if self.head() != self.state['head']:
                raise ValueError("Unrecognized workspace commit; no automatic adoption")
        self.save()

    def check_clean(self):
        if self.git('diff', '--cached', '--name-only').stdout.strip():
            raise ValueError("Unknown staged files; preserve and inspect")
        if self.git('diff', '--name-only').stdout.strip():
            raise ValueError("Unpublished tracked changes; preserve and inspect")
        if self.head() is None and any(self.path(f'data/knowledge/{self.material}/{t}').exists() for t in TOPICS):
            raise ValueError("Unreviewed initial canonical knowledge; preserve and inspect")

    def round_path(self, record):
        return f'data/results/{key(record["campaign"])}/mas/rounds/{key(record["id"])}'

    def proposal(self, record, relative):
        p = self.path(relative)
        base = self.path(self.round_path(record))
        if (not p.is_relative_to(base) or not p.is_file()
                or {s.casefold() for s in p.relative_to(base).parts}
                & {'input', 'inputs', 'raw', 'media', 'cache', 'caches', '.cache', '.git', 'secrets'}):
            raise ValueError("Current round regular proposal/review file required")
        if p.suffix != '.md' or not p.read_text(encoding='utf-8').strip():
            raise ValueError("Nonempty Markdown record required")
        return p

    def _blob(self, data):
        return self.git('hash-object', '--stdin', input=data).stdout.decode().strip()

    def _working_entry(self, relative):
        p = self.path(relative)
        if not p.exists():
            return None
        if not p.is_file():
            raise ValueError("Regular publication file required")
        return dict(mode='100755' if p.stat().st_mode & 0o111 else '100644',
                    oid=self._blob(p.read_bytes()))

    def _entries(self, ref=None):
        """Exact Git file modes/blob IDs; NUL paths also cover quoted filenames."""
        if ref:
            output = self.git('ls-tree', '-r', '-z', ref).stdout
        else:
            output = self.git('ls-files', '--stage', '-z').stdout
        result = {}
        for entry in output.split(b'\0'):
            if not entry:
                continue
            metadata, path = entry.split(b'\t', 1)
            fields = metadata.decode().split()
            if not ref and fields[2] != '0':
                raise ValueError("Unmerged publication index")
            result[path.decode()] = dict(mode=fields[0], oid=fields[2] if ref else fields[1])
        return result

    def publish(self, record, files, *, knowledge=False):
        """Publish only host-validated Main adoptions; recover a partial Git transaction."""
        if self.state['pending'] is not None:
            raise ValueError("Recover pending publication first")
        self.check_clean()
        if self.head() != self.state['head']:
            raise ValueError("Knowledge changed outside publication")
        token = uuid.uuid4().hex
        prepared = {}
        prefix = f'data/knowledge/{self.material}/'
        for target, text in files.items():
            if not (target in {prefix + name for name in TOPICS}
                    or target == self.round_path(record) + '/adoption.json'
                    or (target.startswith(self.round_path(record) + '/')
                        and self.proposal(record, target))):
                raise ValueError("Publication path is not an accepted topic/receipt")
            if not text.strip():
                raise ValueError("Empty adopted record")
            snapshot = f'.transactions/{token}/{len(prepared)}'
            before = self._working_entry(target)
            self.write(snapshot, text)
            prepared[target] = dict(snapshot=snapshot, mode='100644',
                                    oid=self._blob(self.path(snapshot).read_bytes()), before=before)
        stamp = datetime.now(timezone.utc).strftime('%y%m%d-%H-%M')
        subject = 'knowledge' if knowledge else 'decision'
        self.state['pending'] = dict(base=self.state['head'], prepared=prepared,
                                     message=f'{stamp} docs adopt MAS {subject} {token}', operation=record['id'],
                                     knowledge=knowledge)
        self.save()
        return self.recover_publication()

    def recover_publication(self):
        transaction = self.state['pending']
        if transaction is None:
            return None
        current, expected = self.head(), transaction['base']
        paths = set(transaction['prepared'])
        record = self.state['operations'][transaction['operation']]
        prefix = f'data/knowledge/{self.material}/'
        for relative in paths:
            if relative in {prefix + t for t in TOPICS} or relative == self.round_path(record) + '/adoption.json':
                self.path(relative)
            else:
                self.proposal(record, relative)
        staged = set(self.git('diff', '--cached', '--name-only', '-z').stdout.decode().split('\0')) - {''}
        if staged - paths:
            raise ValueError("Unknown staged files during publication recovery")
        payload = {}
        for target, entry in transaction['prepared'].items():
            data = self.path(entry['snapshot']).read_bytes()
            if self._blob(data) != entry['oid'] or entry['mode'] != '100644':
                raise ValueError("Pending publication payload changed")
            payload[target] = data
        accepted = {p: {k: e[k] for k in ('mode', 'oid')}
                    for p, e in transaction['prepared'].items()}
        if current == expected:
            changed = set(self.git('diff', '--name-only', '-z').stdout.decode().split('\0')) - {''}
            if changed - paths:
                raise ValueError("Unrelated changes during publication")
            base_entries = self._entries(expected) if expected else {}
            index_entries = self._entries()
            for target, entry in transaction['prepared'].items():
                if (self._working_entry(target) not in (entry['before'], accepted[target])
                        or index_entries.get(target) not in (base_entries.get(target), accepted[target])):
                    raise ValueError("Conflicting accepted-path edit during publication")
            for target, data in payload.items():
                self.write(target, data)
            self.git('add', '--', *sorted(paths))
            index_entries = self._entries()
            if any(index_entries.get(p) != entry for p, entry in accepted.items()):
                raise ValueError("Staged publication differs from accepted bytes/modes")
            self.git('commit', '--allow-empty', '-m', transaction['message'])
            current = self.head()
        message = self.git('log', '-1', '--format=%s').stdout.decode().strip()
        changed = set(self.git('diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', current).stdout.decode().split('\0')) - {''}
        ancestry = self.git('rev-list', '--parents', '-n', '1', current).stdout.decode().split()
        committed = self._entries(current)
        if (message != transaction['message'] or changed - paths
                or ancestry != [current] + ([expected] if expected else [])
                or any(committed.get(p) != entry for p, entry in accepted.items())):
            raise ValueError("Conflicting commit payload during publication recovery")
        self.check_clean()
        record['status'] = 'published' if transaction['knowledge'] else 'completed'
        if transaction['knowledge']:
            self.state['knowledge_commit'] = current
            if record['kind'] == 'bootstrap':
                record['status'] = 'completed'
        record['commit'] = current
        if record['turn_id']:
            if record['turn_id'] not in record['turns']:
                record['turns'].append(record['turn_id'])
            record['turn_id'] = None
        self.state['head'] = current
        self.state['pending'] = None
        self.save()
        return current
