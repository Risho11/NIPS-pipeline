"""Campaign-local state and exact MAS publication in an existing project Git."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import ast
import csv
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

from mas_contract import TOPICS

# Root-only Codex home names. Never apply these patterns recursively to data.
NATIVE_NAMES = {'auth.json', 'auth.json.tmp', 'config.toml', 'history.jsonl', 'session_index.jsonl',
                'models_cache.json', 'version.json', 'installation_id', '.sandbox_migration', '.codex-global-state.json',
                '.codex-global-state.json.backup', 'sessions', 'archived_sessions', 'shell_snapshots',
                'log', 'tmp', 'sqlite', 'skills', 'plugins', 'packages', 'vendor_imports', 'thread-writer-locks'}
NATIVE_GLOBS = {'auth.json*', 'state_*.sqlite*', 'logs_*.sqlite*', '.codex-global-state.json*'}
HOST_NAMES = {'.mas-state.json', '.mas-runtime.json', '.mas.lock', '.pipeline.lock', '.transactions', '.native'}
ARTIFACT_TYPES = {'code': {'.py'}, 'tables': {'.csv', '.tsv', '.json'},
                  'figures': {'.png', '.svg', '.pdf'}}
MAX_ARTIFACT = 16 * 1024 * 1024
MAX_ADOPTION = 64 * 1024 * 1024


def key(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value)
            or value.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(10)),
                                *(f'LPT{i}' for i in range(10))}):
        raise ValueError('Invalid portable material/campaign identifier')
    return value


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


class Workspace:
    """One campaign/material Main; shared approved material knowledge, one project Git.

    Construction is read-only. A tracked checkpoint contains publication tokens,
    never its own commit ID. The ignored local journal retains in-flight work.
    """
    def __init__(self, root, campaign, material):
        root = Path(root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError('Existing regular project repository required')
        self.root = self.source = root.resolve()
        self.campaign, self.material = key(campaign), key(material)
        self.area = f'data/results/{self.campaign}/mas'
        self.state_path = self.path(self.area + '/.mas-runtime.json')
        self.checkpoint = self.area + '/.mas-state.json'
        self.state = None
        top = self.git('rev-parse', '--show-toplevel', check=False)
        if top.returncode or Path(top.stdout.decode().strip()).resolve() != self.root or self.head() is None:
            raise ValueError('Explicit existing project Git root with a committed baseline required')
        self.git_dir = Path(self.git('rev-parse','--absolute-git-dir').stdout.decode().strip())
        self.common_dir = Path(self.git('rev-parse','--path-format=absolute','--git-common-dir').stdout.decode().strip())

    def path(self, relative):
        self.native_homes()
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in str(relative):
            raise ValueError('Repository-relative path required')
        target = self.root / p
        for part in (target, *target.parents):
            if part == self.root:
                break
            if part.is_symlink():
                raise ValueError('Symlink path forbidden')
        if not target.resolve().is_relative_to(self.root):
            raise ValueError('Escaping project path')
        if target.is_file() and target.stat().st_nlink != 1:
            raise ValueError('Hard-linked path forbidden')
        return target

    def relative(self, path):
        if isinstance(path, str) and '\\' in path:
            raise ValueError('Repository-relative path required')
        p = Path(path)
        relative = p.relative_to(self.root) if p.is_absolute() else p
        return self.path(relative.as_posix()).relative_to(self.root).as_posix()

    def native_homes(self):
        return self._native_homes(self.root)

    @staticmethod
    def _native_homes(root):
        # Resolve identities only; never inspect native/authentication contents.
        homes = {Path.home() / '.codex'}
        homes.update(Path(value).expanduser() for name in ('CODEX_HOME', 'CODEX_SQLITE_HOME')
                     if (value := os.environ.get(name)))
        homes = {p.resolve() for p in homes} - {root}
        if any(root.is_relative_to(p) or p.is_relative_to(root)
               or Path(sys.prefix).resolve().is_relative_to(p) for p in homes):
            raise ValueError('External native home overlaps repository/prepared interpreter; explicit binding required')
        return sorted(homes)

    @staticmethod
    def operator_context_path(root, reference):
        """Check the operator binding before its campaign/context body is read."""
        root = Path(root).resolve()
        homes = Workspace._native_homes(root)
        original = Path(reference).absolute()
        path = original.resolve()
        for candidate in (original, path):
            if any(candidate.is_relative_to(home) for home in homes):
                raise ValueError('Operator context cannot name a native home')
            if candidate.is_relative_to(root):
                parts = candidate.relative_to(root).parts
                if parts and (parts[0] in NATIVE_NAMES | HOST_NAMES | {'.git','.codex','.agents'}
                        or any(fnmatch.fnmatchcase(parts[0], pattern) for pattern in NATIVE_GLOBS)
                        or (len(parts)>=5 and parts[:2]==('data','results') and parts[3]=='mas'
                            and parts[4] in HOST_NAMES | {'.inputs'})):
                    raise ValueError('Operator context cannot name native/host metadata')
        if original.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError('Regular unlinked operator context file required')
        return path

    def input_path(self, reference):
        relative = self.relative(reference)
        first = relative.split('/')[0]
        parts = relative.split('/')
        p = self.path(relative)
        host = (len(parts) >= 5 and parts[:2] == ['data', 'results'] and parts[3] == 'mas'
                and (parts[4] in HOST_NAMES or (parts[4] == '.inputs' and parts[2] != self.campaign)))
        if (first in NATIVE_NAMES or any(fnmatch.fnmatchcase(first, pattern) for pattern in NATIVE_GLOBS)
                or first in {'.git', '.codex', '.agents'} or host
                or any(p.is_relative_to(home) for home in self.native_homes())
                or any(p.is_relative_to(directory) for directory in (self.git_dir, self.common_dir))
                or relative.startswith(f'data/knowledge/{self.material}/')
                or (relative.startswith(self.area + '/') and not relative.startswith(self.area + '/.inputs/'))):
            raise ValueError('Original/input binding cannot name host/native/output state')
        if not p.is_file():
            raise ValueError('Regular repository-bound input required')
        return p

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
        self.write(self.area + '/.mas-runtime.json', json.dumps(self.state, indent=2, allow_nan=False) + '\n')

    @contextmanager
    def file_lock(self, relative):
        lock_path = self.path(self.area + '/' + relative)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('a+b') as stream:
            if os.name == 'nt':
                import msvcrt
                if not lock_path.stat().st_size:
                    stream.write(b'0'); stream.flush()
                def acquire():
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                def release():
                    stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            elif os.name == 'posix':
                import fcntl
                acquire = lambda: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                release = lambda: fcntl.flock(stream, fcntl.LOCK_UN)
            else:
                raise RuntimeError('Workspace locking supports Windows and POSIX only')
            try:
                acquire()
            except OSError as exc:
                raise RuntimeError('Campaign workspace is already locked') from exc
            try:
                yield self
            finally:
                release()

    @contextmanager
    def lock(self, *, reconcile=False):
        with self.file_lock('.mas.lock'):
            self._open(reconcile=reconcile)
            yield self

    def git(self, *args, check=True, input=None, index=None):
        self.native_homes()
        env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
        if index is not None:
            env['GIT_INDEX_FILE'] = str(index)
        command = ['git', '-c', f'core.hooksPath={os.devnull}', '-c', 'commit.gpgsign=false',
                   '-c', 'core.fsmonitor=false', '-c', 'core.autocrlf=false', '-c', 'core.filemode=true',
                   '-c', 'user.name=MAS Main', '-c', 'user.email=mas@localhost', *args]
        p = subprocess.run(command, cwd=self.root, env=env, input=input, capture_output=True, timeout=60)
        if check and p.returncode:
            raise RuntimeError(f'Project Git failed: {args[0]}')
        return p

    def head(self):
        p = self.git('rev-parse', '--verify', 'HEAD', check=False)
        return p.stdout.decode().strip() if p.returncode == 0 else None

    def _entries(self, ref=None):
        output = self.git('ls-tree', '-r', '-z', ref).stdout if ref else self.git('ls-files', '--stage', '-z').stdout
        result = {}
        for entry in output.split(b'\0'):
            if entry:
                meta, path = entry.split(b'\t', 1)
                fields = meta.decode().split()
                if not ref and fields[2] != '0':
                    raise ValueError('Unmerged project index')
                result[path.decode()] = dict(mode=fields[0], oid=fields[2] if ref else fields[1])
        return result

    def _blob(self, data, *, store=False):
        digest = hashlib.sha256(data).hexdigest()
        cache = self.__dict__.setdefault('_blob_ids', {})
        if not store and digest in cache:
            return cache[digest]
        args = ['hash-object', '--stdin'] + (['-w'] if store else [])
        cache[digest] = self.git(*args, input=data).stdout.decode().strip()
        return cache[digest]

    def _working_entry(self, relative):
        data, identity = self.publication_read(self.root / relative)
        if identity is None:
            return None
        return dict(mode='100755' if identity['mode'] & 0o111 else '100644', oid=self._blob(data))

    @contextmanager
    def _publication_parent(self, path, *, create=False):
        """Anchor publication I/O; never follow a substituted parent directory."""
        self.native_homes()
        path = Path(path).absolute()
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors, edges = [os.open(path.anchor, flags)], []
        try:
            for name in path.parts[1:-1]:
                parent = descriptors[-1]
                if create:
                    try: os.mkdir(name, mode=0o700, dir_fd=parent)
                    except FileExistsError: pass
                child = os.open(name, flags, dir_fd=parent)
                descriptors.append(child)
                edges.append((parent, name, child))
            def verify():
                for parent, name, child in edges:
                    actual = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    opened = os.fstat(child)
                    if (not stat.S_ISDIR(actual.st_mode)
                            or (actual.st_dev, actual.st_ino) != (opened.st_dev, opened.st_ino)):
                        raise ValueError('Publication parent changed; preserve partial paths')
            verify()
            yield descriptors[-1], path.name, verify
            verify()
        finally:
            for descriptor in reversed(descriptors): os.close(descriptor)

    def publication_read(self, path, *, _links=1):
        """One descriptor-bound byte observation, not scientific review evidence."""
        self.native_homes()
        if os.name != 'posix' or not all(hasattr(os, flag) for flag in ('O_DIRECTORY', 'O_NOFOLLOW')):
            raise RuntimeError('Publication requires anchored no-follow filesystem capabilities')
        def stable(s):
            return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        try:
            with self._publication_parent(path) as (parent, name, verify):
                try: observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError: return None, None
                if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != _links:
                    raise ValueError('Regular unlinked publication file required')
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                with os.fdopen(fd, 'rb') as stream:
                    before = os.fstat(stream.fileno())
                    if stable(before) != stable(observed):
                        raise ValueError('Publication file changed before read')
                    data = stream.read()
                    after = os.fstat(stream.fileno())
                if stable(before) != stable(after) or stable(os.stat(name, dir_fd=parent, follow_symlinks=False)) != stable(after):
                    raise ValueError('Publication file changed during read')
                verify()
                return data, dict(dev=after.st_dev, ino=after.st_ino, mode=stat.S_IMODE(after.st_mode),
                    links=after.st_nlink, size=after.st_size, mtime=after.st_mtime_ns,
                    ctime=after.st_ctime_ns, digest=hashlib.sha256(data).hexdigest())
        except FileNotFoundError:
            return None, None

    def _transaction_path(self, tx, name):
        return self.area + '/.transactions/' + key(tx['token']) + '/' + name

    def _selection_path(self, record, turn):
        digest=hashlib.sha256(json.dumps([record['id'],turn]).encode()).hexdigest()
        return self.area+'/.transactions/selection-'+digest

    def check_selection(self, record):
        if not record.get('turn_id'): return
        area=self.path(self._selection_path(record,record['turn_id']))
        path=area/'selection.json'
        if not path.exists():
            if area.exists(): raise ValueError('Incomplete publication selection; preserve and inspect')
            return
        selection=json.loads(self.publication_read(path)[0])
        if selection['operation']!=record['id'] or selection['turn']!=record['turn_id']:
            raise ValueError('Publication selection binding changed')
        for relative,entry in selection['files'].items():
            if not self._same_moved_identity(self.publication_read(self.path(relative))[1],entry['identity']):
                raise ValueError('Selected authored bytes changed; restore/review before SDK continuation')

    def select_publication(self, record, turn, relative):
        """Retain one chosen payload across interrupted preparation of this native turn."""
        area=self._selection_path(record,turn);path=self.path(area+'/selection.json')
        if path.exists(): selection=json.loads(self.publication_read(path)[0])
        else:
            if self.path(area).exists(): raise ValueError('Incomplete publication selection; preserve and inspect')
            selection=dict(operation=record['id'],turn=turn,files={})
        if selection['operation']!=record['id'] or selection['turn']!=turn:
            raise ValueError('Publication selection binding changed')
        if relative in selection['files']:
            entry=selection['files'][relative]
            if not entry['snapshot'].startswith(area+'/'):
                raise ValueError('Publication selection snapshot escaped')
            data=self.publication_read(self.path(entry['snapshot']))[0]
            if (hashlib.sha256(data).hexdigest()!=entry['identity']['digest']
                    or not self._same_moved_identity(self.publication_read(self.path(relative))[1],entry['identity'])):
                raise ValueError('Selected authored publication file changed')
            return data,entry['identity']
        data,identity=self.publication_read(self.path(relative))
        self.artifact(record,relative,data=data)
        snapshot=area+'/'+uuid.uuid4().hex
        self.write(snapshot,data)
        selection['files'][relative]=dict(snapshot=snapshot,identity=identity)
        self.write(area+'/selection.json',json.dumps(selection,indent=2)+'\n')
        self._sync_publication(self.path(area+'/selection.json'))
        return data,identity

    def _save_transaction(self, tx):
        self.write(self._transaction_path(tx, 'transaction.json'), json.dumps(tx, indent=2) + '\n')
        self.save()
        self._sync_publication(self.path(self._transaction_path(tx, 'transaction.json')))
        self._sync_publication(self.state_path)

    def _active_transaction(self):
        if self.state['pending'] is not None and not isinstance(self.state['pending'],dict):
            raise ValueError('Unsupported pending publication; preserve and inspect')
        def read_json(path):
            data=self.publication_read(path)[0]
            if data is None: raise ValueError('Missing active publication evidence; preserve and inspect')
            return json.loads(data)
        pointer = self.path(self.area + '/.transactions/active.json')
        if not pointer.exists():
            if self.state['pending'] or self.state.get('local_publication'):
                raise ValueError('Missing active publication evidence; preserve and inspect')
            return None
        active = read_json(pointer)
        if not isinstance(active,dict) or not {'token','intent_digest'} <= active.keys():
            raise ValueError('Corrupt active publication pointer')
        tx_path = self._transaction_path(active, 'transaction.json')
        tx = read_json(self.path(tx_path))
        intent = self.publication_read(self.path(self._transaction_path(active, 'intent.json')))[0]
        if (intent is None or hashlib.sha256(intent).hexdigest() != active['intent_digest']
                or not isinstance(tx,dict) or tx.get('strategy') != 2 or tx.get('token') != active['token']):
            raise ValueError('Corrupt/unsupported publication intent; preserve and inspect')
        original = json.loads(intent)
        fields={'prepared','operation','knowledge','message','frontier','before_state'}
        if (not isinstance(original,dict) or not fields <= original.keys() or not fields <= tx.keys()
                or tx.get('phase') not in {'prepared','closing','finalized','unfinished'}):
            raise ValueError('Unsupported active publication intent')
        if self.state.get('local_publication') not in (None,tx['token']):
            raise ValueError('Local publication pointer differs from active intent')
        for field in fields:
            if tx[field] != original[field]:
                raise ValueError('Publication intent binding changed; preserve and inspect')
        if self.state['pending'] and self.state['pending'].get('token') != tx['token']:
            raise ValueError('Pending publication differs from active intent')
        receipt = self.path(self._transaction_path(tx, 'receipt.json'))
        if tx['phase'] == 'finalized':
            if (not receipt.exists() or read_json(receipt) !=
                    dict(token=tx['token'], candidate=tx['candidate'])):
                raise ValueError('Missing/corrupt finalized publication receipt')
            if self.state['pending']:
                raise ValueError('Finalized pointer conflicts with pending state')
            return tx
        if not self.state['pending']:
            prior = tx['before_state']
            if (set(self.state['operations']) != set(prior['operations'])
                    or self.state['publication_id'] not in (prior['publication_id'], tx['token'])):
                raise ValueError('Unfinished intent conflicts with later local work')
            failures = self.state['failures']
            self.state = deepcopy(prior)
            self.state['failures'] = failures
            self.state['local_publication'] = tx['token']
        self.state['pending'] = tx
        return tx

    def _stable(self, state):
        value = deepcopy(state)
        for field in ('head', 'knowledge_commit', 'pending', 'local_publication'):
            value.pop(field, None)
        for record in value['operations'].values():
            record.pop('commit', None)
        # Provider diagnostics may contain sensitive text. Keep them only in the
        # ignored local journal; the portable checkpoint records failure identity.
        value['failures'] = [{field:failure[field] for field in ('operation', 'turn_id', 'type')}
                             for failure in value['failures']]
        return value

    def publication_commit(self, token, campaign=None):
        key(token)
        path = f'data/results/{key(campaign or self.campaign)}/mas/.mas-state.json'
        found = []
        for commit in self.git('log', '--format=%H', '--fixed-strings', '--grep=' + token, 'HEAD', '--', path).stdout.decode().split():
            message = self.git('log', '-1', '--format=%s', commit).stdout.decode().strip()
            if re.fullmatch(r'\d{6}-\d{2}-\d{2} docs adopt MAS (knowledge|decision) ' + re.escape(token), message):
                value = json.loads(self.git('show', f'{commit}:{path}').stdout)
                if value.get('publication_id') == token and value.get('campaign') == (campaign or self.campaign):
                    entries = self._entries(commit)
                    if any(entries.get(p) != e for p,e in value['owned'].items()) or any(entries.get(p) != e for p,e in value['bank'].items()):
                        raise ValueError('Checkpoint committed payload mismatch')
                    found.append(commit)
        if len(found) != 1:
            raise ValueError('Missing/ambiguous accepted publication history; no native migration')
        return found[0]

    def _hydrate(self):
        state = self.state
        state['head'] = self.publication_commit(state['publication_id']) if state['publication_id'] else None
        if state['head']:
            accepted = json.loads(self.git('show',f"{state['head']}:{self.checkpoint}").stdout)
            if (state['thread_id'] != accepted['thread_id'] or state['owned'] != accepted['owned']
                    or not accepted['operations'].keys() <= state['operations'].keys()):
                raise ValueError('Accepted campaign/native binding or history changed')
            for identifier, record in accepted['operations'].items():
                if record['status'] == 'completed':
                    live = {k:v for k,v in state['operations'][identifier].items() if k != 'commit'}
                    if live != record:
                        raise ValueError('Cached decision differs from accepted checkpoint')
        ref = state['knowledge_ref']
        state['knowledge_commit'] = self.publication_commit(ref['publication_id'], ref['campaign']) if ref else None
        for record in state['operations'].values():
            if record.get('publication_id'):
                record['commit'] = self.publication_commit(record['publication_id'])
                if record['status'] == 'completed':
                    checkpoint = json.loads(self.git('show',f"{record['commit']}:{self.checkpoint}").stdout)
                    stable = {k:v for k,v in record.items() if k!='commit'}
                    if checkpoint['operations'].get(record['id']) != stable:
                        raise ValueError('Cached decision differs from accepted checkpoint')
        state.setdefault('pending', None)

    def _discover_bank(self):
        prefix = f'data/knowledge/{self.material}/'
        paths = {prefix+t for t in TOPICS}
        changed_commit = self.git('log', '-1', '--format=%H', 'HEAD', '--', prefix).stdout.decode().strip()
        if not changed_commit:
            if any(self.path(p).exists() for p in paths):
                raise ValueError('Unreviewed material knowledge exists; preserve and review')
            return None, {}
        # A renewed reviewed publication may preserve identical topic bytes.
        # Its checkpoint still advances the accepted knowledge provenance.
        commit, value = None, None
        candidates = self.git('log', '--format=%H', '--grep= docs adopt MAS knowledge ', 'HEAD',
                              '--', ':(glob)data/results/*/mas/.mas-state.json').stdout.decode().split()
        for candidate in candidates:
            changed = self.git('diff-tree','--root','--no-commit-id','--name-only','-r','-z',candidate).stdout.decode().split('\0')
            checkpoints = [p for p in changed if p.startswith('data/results/') and p.endswith('/mas/.mas-state.json')]
            if len(checkpoints) != 1:
                continue
            proposed = json.loads(self.git('show',f'{candidate}:{checkpoints[0]}').stdout)
            if proposed.get('material') == self.material:
                commit, value = candidate, proposed
                break
        if not commit or self.git('merge-base','--is-ancestor',changed_commit,commit,check=False).returncode:
            raise ValueError('Shared knowledge lacks accepted campaign provenance')
        entries = self._entries(commit)
        if not paths <= entries.keys():
            raise ValueError('Incomplete shared knowledge bank')
        if value.get('material') != self.material or not value.get('publication_id'):
            raise ValueError('Shared knowledge material/provenance mismatch')
        ref = dict(campaign=value['campaign'], publication_id=value['publication_id'])
        if self.publication_commit(ref['publication_id'], ref['campaign']) != commit:
            raise ValueError('Shared knowledge publication mismatch')
        return ref, {p:entries[p] for p in paths}

    def _verify_frontier(self, *, bank=True):
        entries = self._entries('HEAD')
        expected = dict(self.state['owned'])
        if bank:
            expected.update(self.state['bank'])
        if self.state['publication_id']:
            commit = self.publication_commit(self.state['publication_id'])
            expected[self.checkpoint] = self._entries(commit)[self.checkpoint]
        for p,e in expected.items():
            if entries.get(p) != e or self._working_entry(p) != e:
                raise ValueError('Accepted MAS content changed; explicit review/reconciliation required')

    def _open(self, *, reconcile=False):
        for legacy in ('.mas-state.json', 'mas/state.json', 'state.json', self.area+'/state.json'):
            if self.path(legacy).exists():
                raise ValueError('Retired/external MAS state must be preserved and explicitly reviewed')
        live = self.state_path if self.state_path.exists() else self.path(self.checkpoint)
        if live.exists():
            self.state = json.loads(live.read_text())
            if (self.state.get('version') != 2 or self.state.get('source') != '.'
                    or self.state.get('campaign') != self.campaign or self.state.get('material') != self.material):
                raise ValueError('Unsupported state or campaign/material binding changed')
            if live == self.root / self.checkpoint and not self.state.get('publication_id'):
                raise ValueError('Checkpoint lacks committed publication provenance')
            self.state.setdefault('pending', None)
        else:
            ref, bank = self._discover_bank()
            self.state = dict(version=2, source='.', campaign=self.campaign, material=self.material,
                publication_id=None, knowledge_ref=ref, bank=bank, owned={}, thread_id=None,
                active=None, operations={}, pending=None, failures=[])
        active = self._active_transaction()
        if not self.state['pending']:
            self._hydrate()
            try:
                self._verify_frontier(bank=False)
            except ValueError:
                if active:
                    incident = self._transaction_path(active, 'incident.json')
                    if not self.path(incident).exists():
                        self.write(incident, json.dumps(dict(token=active['token'], type='AcceptedFrontierChanged'))+'\n')
                raise
            ref, bank = self._discover_bank()
            if bank != self.state['bank'] or ref != self.state['knowledge_ref']:
                if not reconcile:
                    raise ValueError('Shared knowledge changed; explicit reconsideration required')
                self.state['bank'], self.state['knowledge_ref'] = bank, ref
                self._hydrate()
            try:
                self._verify_frontier()
            except ValueError:
                if active:
                    incident=self._transaction_path(active,'incident.json')
                    if not self.path(incident).exists():
                        self.write(incident,json.dumps(dict(token=active['token'],type='AcceptedFrontierChanged'))+'\n')
                raise
        self.save()

    def check_clean(self):
        if self.git('diff', '--cached', '--name-only').stdout.strip():
            raise ValueError('Busy project index: unrelated staged files preserved')
        self._check_index_flags()
        self._verify_frontier()

    def _check_index_flags(self):
        for option in ('-v', '-f'):
            if any(line[:1] != 'H' for line in self.git('ls-files',option).stdout.decode().splitlines()):
                raise ValueError('Busy/special project index flags; preserve and inspect')
        # Disabled fsmonitor can hide its stored valid bits from ls-files. Let
        # Git roundtrip a private copy without providers or split-index writes;
        # reject metadata this safe plumbing would discard, never parse it here.
        index = Path(self.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
        original = index.read_bytes()
        parent = self.path(self.area + '/.transactions')
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent, prefix='index-check-') as directory:
            private = Path(directory) / 'index'
            private.write_bytes(original)
            self.git('update-index','--no-split-index','--force-write-index',index=private)
            if private.read_bytes() != original or index.read_bytes() != original:
                raise ValueError('Busy/special project index metadata; preserve and inspect')

    def round_path(self, record):
        if record['campaign'] != self.campaign:
            raise ValueError('Operation campaign binding changed')
        return self.area + '/rounds/' + key(record['id'])

    def attempt_path(self, record):
        return self.round_path(record) + '/attempt-' + str(len(record['turns']))

    def proposal(self, record, relative, *, data=None):
        p = self.path(relative)
        base = self.path(self.round_path(record))
        if (not p.is_relative_to(base) or not p.is_file()
                or {s.casefold() for s in p.relative_to(base).parts}
                & {'input','inputs','raw','media','cache','caches','.cache','.git','.codex','secrets'}):
            raise ValueError('Current round regular proposal/review file required')
        if data is None: data = self.publication_read(p)[0]
        if p.suffix != '.md' or not data.decode('utf-8').strip():
            raise ValueError('Nonempty Markdown record required')
        return p

    def artifact(self, record, relative, *, data=None):
        p = self.path(relative)
        if p.suffix == '.md':
            return self.proposal(record, relative, data=data), 'markdown'
        base = self.path(self.attempt_path(record) + '/artifacts')
        if not p.is_relative_to(base) or not p.is_file() or len(p.relative_to(base).parts) < 2:
            raise ValueError('Explicit current-attempt derived artifact required')
        kind = p.relative_to(base).parts[0]
        if kind not in ARTIFACT_TYPES or p.suffix.lower() not in ARTIFACT_TYPES[kind] or p.name.casefold() in NATIVE_NAMES:
            raise ValueError('Unsupported derived artifact type/name')
        if ({s.casefold() for s in p.relative_to(base).parts} & {'raw','input','inputs','media','cache','secrets','.git','.codex'}
                or p.stat().st_mode & 0o111):
            raise ValueError('Raw/native/executable-mode artifact forbidden')
        if p.stat().st_size > MAX_ARTIFACT or not p.stat().st_size:
            raise ValueError('Derived artifact must be nonempty and at most 16 MiB')
        if data is None: data = self.publication_read(p)[0]
        if kind == 'code':ast.parse(data.decode('utf-8'), relative)
        elif kind == 'tables':
            if p.suffix == '.json':json.loads(data)
            else:
                rows = list(csv.reader(io.StringIO(data.decode('utf-8')), delimiter='\t' if p.suffix=='.tsv' else ','))
                if len(rows)<2 or not rows[0] or any(len(r)!=len(rows[0]) for r in rows):
                    raise ValueError('Derived table requires a header and rectangular data')
        elif p.suffix == '.svg':
            if ET.fromstring(data).tag.split('}')[-1]!='svg' or b'<!ENTITY' in data or b'<!DOCTYPE' in data:
                raise ValueError('Regular derived SVG required')
        elif p.suffix == '.png':
            if not data.startswith(b'\x89PNG\r\n\x1a\n') or b'IEND' not in data[-16:]:
                raise ValueError('Invalid derived PNG')
        elif not data.startswith(b'%PDF-') or b'%%EOF' not in data[-1024:]:
            raise ValueError('Invalid derived PDF')
        return p, kind

    def _sync_publication(self, path):
        with self._publication_parent(path) as (parent, _, verify):
            os.fsync(parent); verify()

    def _sync_installation_image(self, path):
        with self._publication_parent(path) as (parent,name,verify):
            fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
            try: os.fsync(fd);verify()
            finally: os.close(fd)

    def _publication_capabilities(self, tx, paths):
        directory = self.path(self._transaction_path(tx, 'capability'))
        directory.mkdir(mode=0o700)
        try:
            with self._publication_parent(directory / 'probe') as (parent, _, verify):
                device = os.fstat(parent).st_dev
                fd = os.open('probe', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=parent)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(b'MAS capability\n'); stream.flush(); os.fsync(stream.fileno())
                os.rename('probe', 'captured', src_dir_fd=parent, dst_dir_fd=parent)
                os.link('captured', 'installed', src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.unlink('installed', dir_fd=parent); os.unlink('captured', dir_fd=parent)
                os.fsync(parent); verify()
            for path in paths:
                with self._publication_parent(path, create=True) as (parent, _, verify):
                    if os.fstat(parent).st_dev != device:
                        raise ValueError('Publication requires same-filesystem capture/install; no fallback')
                    os.fsync(parent); verify()
        finally:
            # Only these new disposable capability names, never transaction evidence.
            for name in ('probe', 'captured', 'installed'):
                (directory / name).unlink(missing_ok=True)
            directory.rmdir()

    @staticmethod
    def _same_moved_identity(actual, expected):
        return (actual is not None and expected is not None
                and {k:v for k,v in actual.items() if k not in {'ctime','mtime'}} ==
                    {k:v for k,v in expected.items() if k not in {'ctime','mtime'}})

    def _install_publication(self, tx, target, entry):
        progress = tx['progress'].setdefault(target, {})
        path = Path(target) if entry.get('index') else self.root / target
        slot = self.root / entry['slot']
        with self._publication_parent(path) as (parent, name, verify), self._publication_parent(slot / 'capture') as (saved, _, saved_verify):
            if [os.fstat(parent).st_dev, os.fstat(parent).st_ino] != entry['parent']:
                raise ValueError('Publication parent identity changed; preserve and inspect')
            capture, image = slot / 'capture', slot / 'image'
            if entry['action'] == 'KEEP':
                if not self._same_moved_identity(self.publication_read(path)[1], entry['before_identity']):
                    raise ValueError('Selected authored publication file changed')
                return
            if entry['action'] == 'REPLACE':
                if not os.path.lexists(capture):
                    if progress.get('captured') or progress.get('installed'):
                        raise ValueError('Missing captured publication preimage')
                    # The destination belongs exclusively to this newly allocated slot.
                    verify(); saved_verify()
                    try: os.rename(name, 'capture', src_dir_fd=parent, dst_dir_fd=saved)
                    except FileNotFoundError as error:
                        raise ValueError('Expected publication target was deleted') from error
                    os.fsync(parent); os.fsync(saved); verify(); saved_verify()
                captured = self.publication_read(capture)[1]
                if not self._same_moved_identity(captured, entry['before_identity']):
                    raise ValueError('Captured conflicting publication object; preserve partial path')
                if progress.get('captured') and not self._same_moved_identity(captured, progress['captured']):
                    raise ValueError('Captured publication bytes/identity changed')
                progress['captured'] = captured
                self._save_transaction(tx)
            if progress.get('installed'):
                if not self._same_moved_identity(self.publication_read(path)[1], progress['installed']):
                    raise ValueError('Installed publication file changed')
                return
            # A stopped exact registered two-link install may finish without rewriting.
            linked = os.path.lexists(path)
            if linked:
                actual = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if (not image.exists() and progress.get('linked') and stat.S_ISREG(actual.st_mode)
                        and [actual.st_dev,actual.st_ino,stat.S_IMODE(actual.st_mode)] == entry['image_identity']
                        and actual.st_nlink == 1):
                    data, identity = self.publication_read(path)
                    if self._blob(data) != entry['oid']:
                        raise ValueError('Interrupted installation payload changed')
                    progress['installed'] = identity; self._save_transaction(tx)
                    return
                if (not image.exists() or not stat.S_ISREG(actual.st_mode)
                        or [actual.st_dev, actual.st_ino] != entry['image_identity'][:2]
                        or actual.st_nlink != 2):
                    raise ValueError('New foreign publication target; exclusive install refused')
                data, identity = self.publication_read(path, _links=2)
                image_stat = image.lstat()
                if ([image_stat.st_dev, image_stat.st_ino] != entry['image_identity'][:2]
                        or image_stat.st_nlink != 2 or self._blob(data) != entry['oid']):
                    raise ValueError('Unregistered publication link state')
            else:
                if progress.get('linked'):
                    raise ValueError('Registered installed target was deleted')
                data, identity = self.publication_read(image)
                if (identity is None or [identity['dev'],identity['ino'],identity['mode']] != entry['image_identity']
                        or self._blob(data) != entry['oid']):
                    raise ValueError('Prepared installation image changed')
                verify(); saved_verify()
                try:
                    os.link('image', name, src_dir_fd=saved, dst_dir_fd=parent, follow_symlinks=False)
                except FileExistsError as error:
                    raise ValueError('New foreign publication target; exclusive install refused') from error
                os.fsync(parent); os.fsync(saved); verify(); saved_verify()
            progress['linked'] = True
            self._save_transaction(tx)
            # Remove only our registered image alias; the immutable snapshot is separate.
            image_stat = image.lstat()
            if [image_stat.st_dev,image_stat.st_ino] != entry['image_identity'][:2] or image_stat.st_nlink != 2:
                raise ValueError('Installation image identity changed')
            os.unlink('image', dir_fd=saved); os.fsync(parent); os.fsync(saved)
            data, identity = self.publication_read(path)
            if (identity is None or [identity['dev'],identity['ino'],identity['mode']] != entry['image_identity']
                    or self._blob(data) != entry['oid']):
                raise ValueError('Installed publication bytes changed')
            progress['installed'] = identity
            self._save_transaction(tx)

    def _publication_guard(self, tx, *, ref=None, index=None):
        expected = tx['frontier']
        if ref is not None:
            if self.git('symbolic-ref','HEAD').stdout.decode().strip()!=tx['ref']:
                raise ValueError('Bound publication branch changed; preserve known candidate')
            entries = self._entries(ref)
            if any(entries.get(p) != e for p,e in expected.items()):
                raise ValueError('Publication Git frontier changed')
        for target, entry in tx['prepared'].items():
            path = self.root / target
            with self._publication_parent(path) as (parent, _, verify):
                if [os.fstat(parent).st_dev,os.fstat(parent).st_ino] != entry['parent']:
                    raise ValueError('Publication parent identity changed')
                verify()
            identity = self.publication_read(path)[1]
            wanted = entry['before_identity'] if entry['action'] == 'KEEP' else tx['progress'].get(target,{}).get('installed')
            if not self._same_moved_identity(identity, wanted):
                raise ValueError('Publication working identity changed; pending retained')
            progress = tx['progress'].get(target,{})
            if entry['action'] == 'REPLACE' and not self._same_moved_identity(self.publication_read(self.root / entry['slot'] / 'capture')[1], progress.get('captured')):
                raise ValueError('Captured publication preimage changed')
        for path, entry in expected.items():
            if self._working_entry(path) != entry:
                raise ValueError('Publication working frontier changed; pending retained')
        if index is not None:
            self._check_index_flags()
            if self._entries() != self._entries(index):
                raise ValueError('Publication index projection changed')
            item = tx.get('index_install')
            if item:
                progress = tx['progress'].get(tx['index_path'],{})
                if progress.get('installed') and not self._same_moved_identity(self.publication_read(tx['index_path'])[1], progress['installed']):
                    raise ValueError('Installed project index changed')
                if progress.get('captured') and not self._same_moved_identity(self.publication_read(self.root / item['slot'] / 'capture')[1], progress['captured']):
                    raise ValueError('Captured project index changed')
            elif tx.get('kept_index') and not self._same_moved_identity(self.publication_read(tx['index_path'])[1],tx['kept_index']):
                raise ValueError('Kept project index changed')

    def _verify_publication_commit(self, tx):
        commit = tx['candidate']
        committed = self._entries(commit)
        parent = self.git('rev-list','--parents','-n','1',commit).stdout.decode().split()
        changed = set(self.git('diff-tree','--no-commit-id','--name-only','-r','-z',commit).stdout.decode().split('\0'))-{''}
        if (parent != [commit,tx['base']] or changed-set(tx['prepared'])
                or any(committed.get(p)!=e for p,e in tx['frontier'].items())):
            raise ValueError('Conflicting commit payload during recovery')

    def publish(self, record, files, *, knowledge=False, observations=None):
        if self.state['pending'] is not None:
            raise ValueError('Recover pending publication first')
        self.check_clean()
        base, ref = self.head(), self.git('symbolic-ref','HEAD').stdout.decode().strip()
        accepted = dict(self.state['owned']); accepted.update(self.state['bank'])
        if self.state['publication_id']:
            accepted[self.checkpoint] = self._entries(self.publication_commit(self.state['publication_id']))[self.checkpoint]
        token = uuid.uuid4().hex
        future = deepcopy(self.state)
        adopted = future['operations'][record['id']]
        adopted.update(status='published' if knowledge and record['kind']!='bootstrap' else 'completed', publication_id=token)
        if adopted['turn_id'] and adopted['turn_id'] not in adopted['turns']:
            adopted['turns'].append(adopted['turn_id'])
        adopted['turn_id'] = None
        future['publication_id'] = token
        if knowledge: future['knowledge_ref'] = dict(campaign=self.campaign, publication_id=token)
        prepared, before, observations = {}, {}, observations or {}
        prefix = f'data/knowledge/{self.material}/'
        generated = {self.round_path(record)+'/adoption.json', self.round_path(record)+'/decision.md'}
        for target, text in files.items():
            canonical = target in {prefix+t for t in TOPICS}
            if not (canonical or target in generated or (target.startswith(self.attempt_path(record)+'/') and self.artifact(record,target,data=text.encode('utf-8') if isinstance(text,str) else text))):
                raise ValueError('Publication path is not an accepted MAS artifact')
            data = text.encode('utf-8') if isinstance(text,str) else text
            if not data or len(data)>MAX_ARTIFACT: raise ValueError('Publication file must be nonempty and at most 16 MiB')
            current, identity = self.publication_read(self.path(target))
            if target in observations and not self._same_moved_identity(identity,observations[target]):
                raise ValueError('Selected publication source changed before preparation')
            entry = dict(mode='100644',oid=self._blob(data))
            if canonical:
                original = dict(mode='100755' if identity and identity['mode'] & 0o111 else '100644',oid=self._blob(current)) if identity else None
                if original != accepted.get(target): raise ValueError('Canonical publication preimage changed')
            elif target in generated:
                if target in accepted:
                    original = dict(mode='100755' if identity and identity['mode'] & 0o111 else '100644',oid=self._blob(current)) if identity else None
                    if original != accepted[target]: raise ValueError('Accepted host-generated publication preimage changed')
                elif identity is not None: raise ValueError('Unexpected host-generated publication target exists')
            elif current != data or identity is None or identity['mode'] & 0o111:
                raise ValueError('Authored publication payload differs from selected source')
            before[target] = identity
            if target.endswith('/adoption.json'):
                value=json.loads(data);value['publication_id']=token;data=(json.dumps(value,indent=2)+'\n').encode()
                entry['oid']=self._blob(data)
            (future['bank'] if canonical else future['owned'])[target]=entry
            prepared[target]=data
        future['pending']=None
        prepared[self.checkpoint]=(json.dumps(self._stable(future),indent=2,allow_nan=False)+'\n').encode()
        current, identity = self.publication_read(self.path(self.checkpoint))
        original = dict(mode='100755' if identity and identity['mode'] & 0o111 else '100644',oid=self._blob(current)) if identity else None
        if original != accepted.get(self.checkpoint): raise ValueError('Checkpoint preimage changed')
        before[self.checkpoint]=identity
        if any(len(data)>MAX_ARTIFACT for data in prepared.values()): raise ValueError('Publication file exceeds 16 MiB')
        if sum(map(len,prepared.values()))>MAX_ADOPTION: raise ValueError('Adoption exceeds 64 MiB including checkpoint')
        stamp=datetime.now(timezone.utc).strftime('%y%m%d-%H-%M')
        index_path=Path(self.git('rev-parse','--path-format=absolute','--git-path','index').stdout.decode().strip())
        tx=dict(strategy=2,token=token,base=base,ref=ref,operation=record['id'],knowledge=knowledge,
            message=f"{stamp} docs adopt MAS {'knowledge' if knowledge else 'decision'} {token}",candidate=None,
            lock=None,phase='prepared',prepared={},progress={},before_state=deepcopy(self.state),
            frontier={**future['owned'],**future['bank']},index_path=str(index_path))
        directory=self.path(self._transaction_path(tx,''));directory.mkdir(mode=0o700)
        self._publication_capabilities(tx,[*(self.root/p for p in prepared),index_path])
        parents = {}
        for target in prepared:
            with self._publication_parent(self.root/target) as (parent,_,verify):
                parents[target]=[os.fstat(parent).st_dev,os.fstat(parent).st_ino];verify()
        # Authority is frozen above: no target sampling after private snapshot writes.
        for target,data in prepared.items():
            slot=self._transaction_path(tx,'target-'+str(len(tx['prepared'])))
            self.path(slot).mkdir(mode=0o700)
            snapshot=slot+'/snapshot';self.write(snapshot,data)
            identity=before[target]
            action='KEEP' if identity and identity['digest']==hashlib.sha256(data).hexdigest() else ('REPLACE' if identity else 'ABSENT')
            image_identity=None
            if action!='KEEP':
                self.write(slot+'/image',data)
                os.chmod(self.path(slot+'/image'),identity['mode'] if identity else 0o600)
                self._sync_installation_image(self.path(slot+'/image'))
                observed=self.publication_read(self.path(slot+'/image'))[1]
                image_identity=[observed['dev'],observed['ino'],observed['mode']]
            tx['prepared'][target]=dict(snapshot=snapshot,slot=slot,mode='100644',oid=self._blob(data),
                before=accepted.get(target),before_identity=identity,action=action,parent=parents[target],image_identity=image_identity)
            self._sync_publication(self.root/snapshot)
        tx['frontier'][self.checkpoint]=dict(mode='100644',oid=self._blob(prepared[self.checkpoint]))
        intent=(json.dumps(tx,indent=2)+'\n').encode()
        self.write(self._transaction_path(tx,'intent.json'),intent)
        self.state['pending']=tx;self.state['local_publication']=token
        self._save_transaction(tx)
        self.write(self.area+'/.transactions/active.json',json.dumps(dict(token=token,intent_digest=hashlib.sha256(intent).hexdigest()))+'\n')
        self._sync_publication(self.path(self.area+'/.transactions/active.json'))
        return self.recover_publication()

    def recover_publication(self):
        tx=self.state['pending']
        if tx is None:return None
        if tx.get('strategy')!=2: raise ValueError('Unsupported pending publication; preserve and inspect')
        if self.git('symbolic-ref','HEAD').stdout.decode().strip()!=tx['ref']:
            raise ValueError('Bound publication branch changed; preserve known candidate')
        if self._active_transaction()['token']!=tx['token']: raise ValueError('Active publication changed')
        tx=self.state['pending']
        for target,entry in tx['prepared'].items():
            data=self.publication_read(self.path(entry['snapshot']))[0]
            if self._blob(data)!=entry['oid'] or entry['mode']!='100644': raise ValueError('Pending publication payload changed')
        current_head=self.head();base_entries=self._entries(tx['base']);current_entries=self._entries(current_head)
        candidate=tx['candidate']
        published=bool(candidate and self.git('merge-base','--is-ancestor',candidate,'HEAD',check=False).returncode==0)
        index_path=Path(tx['index_path'])
        index_partial = bool(published and tx.get('index_install')
            and not tx['progress'].get(tx['index_path'],{}).get('installed'))
        # An interrupted owned index capture may leave a gap; reconcile it before Git index reads.
        if index_partial:
            pass
        elif not index_path.exists():
            if not published or not tx.get('index_install'): raise ValueError('Missing project index without owned capture')
        else:
            if (self.git('diff','--cached','--name-only').stdout.strip()
                    and not (published and self._entries()==base_entries)):
                raise ValueError('Busy project index during publication recovery')
            self._check_index_flags()
        index_identity=self.publication_read(index_path)[1] if index_path.exists() and not index_partial else None
        index_before=index_identity['digest'] if index_identity else None
        if not published and tx.get('index_before') and index_before!=tx['index_before']:
            if current_head==tx['base'] or self._entries()!=current_entries:
                raise ValueError('Project index changed before publication recovery; preserve and inspect')
        if not published and current_head!=tx['base'] and self.git('merge-base','--is-ancestor',tx['base'],current_head,check=False).returncode:
            raise ValueError('Project ref is not an unrelated source advance; preserve and inspect')
        lock=index_path.with_name(index_path.name+'.lock');marker=('MAS publication '+tx['token']+'\n').encode()
        if lock.exists():
            identity=lock.stat()
            if not tx['lock'] or [identity.st_dev,identity.st_ino]!=tx['lock'] or lock.is_symlink() or lock.read_bytes()!=marker:
                raise ValueError('Foreign project index lock; preserve and inspect')
        else:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(marker);stream.flush();os.fsync(stream.fileno())
            identity=lock.stat();tx['lock']=[identity.st_dev,identity.st_ino];self._save_transaction(tx)
        prior=self.state
        try:
            if not published:
                self._check_index_flags()
                if self.head()!=current_head or file_digest(index_path)!=index_before: raise ValueError('Project ref/index changed during publication recovery')
                if any(current_entries.get(p)!=base_entries.get(p) for p in set(self.state['owned'])|set(self.state['bank'])|set(tx['prepared'])):
                    raise ValueError('Owned Git content changed during publication')
                if current_head!=tx['base']:
                    tx.setdefault('prior_parents',[]).append(tx['base']);tx['base']=current_head;tx['candidate']=None
                tx['index_before']=index_before
                tx['index_identity']=index_identity
                with self._publication_parent(index_path) as (parent,_,verify):
                    tx['index_parent']=[os.fstat(parent).st_dev,os.fstat(parent).st_ino];verify()
                self._save_transaction(tx)
                private=self.path(self._transaction_path(tx,'index'))
                private.unlink(missing_ok=True);self.git('read-tree',tx['base'],index=private)
                for target,entry in tx['prepared'].items():
                    self._install_publication(tx,target,entry)
                    data=self.publication_read(self.path(entry['snapshot']))[0]
                    if self._blob(data)!=entry['oid']: raise ValueError('Pending publication payload changed')
                    oid=self._blob(data,store=True)
                    self.git('update-index','--add','--cacheinfo',f'100644,{oid},{target}',index=private)
                self._publication_guard(tx)
                tree=self.git('write-tree',index=private).stdout.decode().strip();self._publication_guard(tx)
                if not tx['candidate']:
                    tx['candidate']=self.git('commit-tree',tree,'-p',tx['base'],'-m',tx['message']).stdout.decode().strip();self._save_transaction(tx)
                self._publication_guard(tx)
                self._verify_publication_commit(tx)
                if (self.head()!=tx['base'] or self.git('symbolic-ref','HEAD').stdout.decode().strip()!=tx['ref']
                        or file_digest(index_path)!=tx['index_before']): raise ValueError('Project ref/index changed before CAS')
                self.git('update-ref','-m',tx['message'],tx['ref'],tx['candidate'],tx['base'])
            commit=tx['candidate'];self._verify_publication_commit(tx)
            self._publication_guard(tx,ref='HEAD')
            if not tx.get('index_install') and index_path.exists() and self._entries()==self._entries('HEAD'):
                tx['kept_index']=self.publication_read(index_path)[1]
                self._save_transaction(tx)
            elif not tx.get('index_install'):
                if self.head()!=commit or file_digest(index_path)!=tx['index_before']:
                    # A fully finalized descendant index is never blindly replaced.
                    raise ValueError('Project index changed after publication; preserve and inspect')
                slot=self._transaction_path(tx,'index-install');self.path(slot).mkdir(mode=0o700)
                image=self.path(slot+'/image');self.git('read-tree',commit,index=image)
                identity=tx['index_identity']
                if not self._same_moved_identity(self.publication_read(index_path)[1],identity):
                    raise ValueError('Project index changed before preserving installation')
                os.chmod(image,identity['mode'])
                self._sync_installation_image(image)
                observed=self.publication_read(image)[1]
                tx['index_install']=dict(index=True,slot=slot,action='REPLACE',before_identity=identity,parent=tx['index_parent'],
                    image_identity=[observed['dev'],observed['ino'],observed['mode']],oid=self._blob(self.publication_read(image)[0]))
                self._save_transaction(tx)
            if tx.get('index_install'): self._install_publication(tx,tx['index_path'],tx['index_install'])
            self._publication_guard(tx,ref='HEAD',index='HEAD')
            future=json.loads(self.git('show',f'{commit}:{self.checkpoint}').stdout)
            future['failures']=prior['failures'];future['pending']=None;future['local_publication']=tx['token']
            self.state=future;self._hydrate();self._publication_guard(tx,ref='HEAD',index='HEAD')
            tx['phase']='closing';self._save_transaction(tx)
            self._publication_guard(tx,ref='HEAD',index='HEAD')
            self.write(self._transaction_path(tx,'receipt.json'),json.dumps(dict(token=tx['token'],candidate=commit))+'\n')
            self._sync_publication(self.path(self._transaction_path(tx,'receipt.json')))
            self._publication_guard(tx,ref='HEAD',index='HEAD')
            tx['phase']='finalized';self._save_transaction(tx)
            self._publication_guard(tx,ref='HEAD',index='HEAD')
            current_record=prior['operations'][tx['operation']]
            current_record.clear();current_record.update(self.state['operations'][tx['operation']])
            self.state['operations'][tx['operation']]=current_record
            return commit
        except Exception:
            if self.state is not prior:
                self.state=prior;self.state['pending']=tx;tx['phase']='unfinished'
                self._save_transaction(tx)
            raise
        finally:
            if lock.exists() and [lock.stat().st_dev,lock.stat().st_ino]==tx['lock'] and lock.read_bytes()==marker:
                lock.unlink()
