"""Adaptive persistent scientific Main. This entrypoint never submits experiments."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from mas_contract import (Context, Contribution, Decision, MainReply, Review, TOPICS,
                          validate_conditions)
from mas_workspace import Workspace, file_digest, key, NATIVE_NAMES, NATIVE_GLOBS, HOST_NAMES, MAX_ADOPTION

ROLES = ('hypothesis-updater', 'hypothesis-qa', 'experiment-designer',
         'experiment-design-qa', 'experiment-analyst')


def unwrap(item):
    return getattr(item, 'root', item)


def final_text(turn):
    for raw in reversed(turn.items):
        item = unwrap(raw)
        if getattr(item, 'type', None) == 'agentMessage':
            phase = getattr(item.phase, 'value', item.phase)
            if phase == 'final_answer':
                return item.text
    raise ValueError("No native final assistant message")


def completed(value):
    return getattr(value, 'value', value) == 'completed'


def isolated_sdk(workspace):
    """Lazy SDK creation, after offline effective-MCP discovery and disabling.

    These configuration requests require the separately authorized live smoke to
    establish actual sandbox enforcement; task instructions are not OS isolation.
    """
    workspace.native_homes()
    from codex_cli_bin import bundled_codex_path
    from openai_codex import Codex, CodexConfig, __version__
    if __version__ != '0.163.0':
        raise RuntimeError("Pinned openai-codex 0.163.0 required")
    record = workspace.state['operations'][workspace.state['active']]
    attempt = workspace.path(workspace.attempt_path(record))
    scratch = attempt / '.scratch'
    native = workspace.path(workspace.area + '/.native')
    native.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    overrides = (
        'project_root_markers=[]', 'project_doc_max_bytes=0',
        'default_permissions="mas"', 'permissions.mas.extends=":read-only"',
        'permissions.mas.network.enabled=false',
        'web_search="disabled"', 'features.apps=false', 'features.plugins=false',
        'features.memories=false', 'agents.enabled=true', 'check_for_update_on_startup=false',
        'sqlite_home=' + json.dumps(str(native / 'sqlite')),
        'log_dir=' + json.dumps(str(native / 'log')),
    )
    filesystem = _attempt_config(workspace, record)['permissions']['mas']['filesystem']
    # The CLI override key parser splits dots even inside quoted path keys.
    # Supply one TOML table value so filename dots remain literal path bytes.
    table = ','.join(json.dumps(p) + '=' + json.dumps(mode) for p, mode in filesystem.items())
    overrides += ('permissions.mas.filesystem={' + table + '}',)
    config = CodexConfig(cwd=str(attempt), codex_bin=str(bundled_codex_path()),
                         config_overrides=overrides,
                         env={**_analysis_env(workspace, record), 'CODEX_HOME':str(workspace.root),
                              'CODEX_SQLITE_HOME':str(native / 'sqlite'), 'MAS_SOURCE_ROOT':str(workspace.source)})

    def mcp_states():
        command = [config.codex_bin]
        for setting in config.config_overrides:
            command += ['--config', setting]
        command += ['mcp', 'list', '--json']
        try:
            p = subprocess.run(command, cwd=config.cwd, env={**os.environ, **config.env},
                               capture_output=True, text=True, timeout=30)
            if p.returncode:
                raise ValueError("MCP inspection failed")
            entries = json.loads(p.stdout)
            if not isinstance(entries, list):
                raise ValueError("Invalid MCP listing")
            states = {}
            for entry in entries:
                name, enabled = entry['name'], entry['enabled']
                if not isinstance(name, str) or not name or type(enabled) is not bool or name in states:
                    raise ValueError("Invalid MCP entry")
                states[name] = enabled
            return states
        except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
            # Never expose CLI output, which can contain credentials.
            raise RuntimeError("Cannot verify disabled MCP; SDK not started") from None

    before = mcp_states()
    table = ','.join(json.dumps(name) + '={enabled=false}' for name in sorted(before))
    config.config_overrides += ('mcp_servers={' + table + '}',)
    after = mcp_states()
    if before.keys() != after.keys() or any(after.values()):
        raise RuntimeError("MCP disable not verified; SDK not started")
    return Codex(config)


def _analysis_env(workspace, record):
    scratch = workspace.path(workspace.attempt_path(record)) / '.scratch'
    scratch.mkdir(parents=True, exist_ok=True)
    return dict(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch),
        UV_CACHE_DIR=str(scratch/'uv-cache'), UV_OFFLINE='1', UV_NO_SYNC='1', UV_NO_PROJECT='1',
        UV_PYTHON_DOWNLOADS='never', UV_PYTHON=sys.executable, VIRTUAL_ENV=sys.prefix,
        UV_PROJECT_ENVIRONMENT=sys.prefix, XDG_CACHE_HOME=str(scratch/'cache'), MPLCONFIGDIR=str(scratch/'matplotlib'))


def _other_campaign_globs(campaign):
    """Bounded flat unions of longer names, mismatches and nonempty prefixes.

    Validated ASCII keys contain no glob syntax. At most 2*n alternatives exclude
    exactly this name without enumerating existing (or future) campaigns. Groups
    of at most four keep the pinned native resolver's regex/rule sizes bounded.
    """
    campaign = key(campaign)
    alternatives = [campaign + '?*']
    for i, char in enumerate(campaign):
        prefix = campaign[:i]
        alternatives.append(prefix + '[!' + char + ']*')
        if prefix:alternatives.append(prefix)
    return ['{' + ','.join(alternatives[i:i+4]) + '}' for i in range(0,len(alternatives),4)]


def _attempt_config(workspace, record):
    attempt = workspace.path(workspace.attempt_path(record))
    homes = workspace.native_homes()
    attempt.mkdir(parents=True, exist_ok=True)
    denied = [workspace.root/'data/results/*/mas'/name for name in HOST_NAMES]
    # Native wildcard directory rules do not inherit to descendants. Keep their
    # roots denied and explicitly cover every host-owned descendant as well.
    denied += [path/'**' for path in denied]
    # A matching recursive deny beats even a literal read exception. Exclude the
    # current campaign from both rules rather than trying to override that deny.
    for pattern in _other_campaign_globs(workspace.campaign):
        other_inputs = workspace.root/'data/results'/pattern/'mas/.inputs'
        denied += [other_inputs, other_inputs/'**']
    denied += [workspace.root/name for name in NATIVE_NAMES | NATIVE_GLOBS]
    denied += [workspace.root/name/'**' for name in NATIVE_GLOBS]
    denied += [workspace.root/'.git', workspace.root/'.agents']
    denied += [workspace.git_dir, workspace.common_dir]
    denied += homes
    filesystem = {str(p):'deny' for p in denied}
    # Only this campaign's caller-prepared observation copies are readable.
    filesystem[str(workspace.path(workspace.area + '/.inputs'))] = 'read'
    filesystem[str(attempt)] = 'write'
    filesystem[str(attempt/'.codex')] = 'read'
    return dict(default_permissions='mas', project_root_markers=[], project_doc_max_bytes=0,
        permissions={'mas':dict(extends=':read-only', filesystem=filesystem, network={'enabled':False})},
        shell_environment_policy={'set':_analysis_env(workspace, record)})


class CampaignRuntime:
    """One native Main turn per run(); None means reviewed knowledge was published.

    Calling run() again continues the pending question with the committed knowledge.
    Completed decisions are reused on ordinary restart. A nonempty reconsideration
    reason creates a new preserved operation, never edits an old decision.
    """
    def __init__(self, workspace, context, *, sdk_factory=None):
        self.workspace = workspace
        self.context = Context.model_validate(context)
        key(self.context.campaign)
        if self.context.campaign != workspace.campaign:
            raise ValueError("Context/campaign workspace binding differs")
        self.sdk_factory = sdk_factory or (lambda: isolated_sdk(workspace))
        self.last_operation_id = None

    def _bindings(self):
        w = self.workspace
        w.native_homes()
        # Discover registered roles in the current attempt, with source
        # role documents resolved through MAS_SOURCE_ROOT; do not copy source/data.
        for role in ROLES:
            source = w.source / '.codex/agents' / f'{role}.toml'
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing regular source role binding")
            record = w.state['operations'][w.state['active']]
            w.write(w.attempt_path(record) + f'/.codex/agents/{role}.toml', source.read_text(encoding='utf-8'))

    def _inputs(self, inputs):
        result = {}
        for label, source in (inputs or {}).items():
            key(label)
            p = Path(source)
            p = self.workspace.input_path(p)
            result[label] = {'path': self.workspace.relative(p), 'sha256': file_digest(p)}
        return result

    def _check_inputs(self, record):
        for value in record['inputs'].values():
            if file_digest(self.workspace.input_path(value['path'])) != value['sha256']:
                raise ValueError("Original observation changed; preserve and reconsider explicitly")

    def _operation(self, observation_id, inputs, reconsideration, revision_id=None):
        w, state = self.workspace, self.workspace.state
        active = state['operations'].get(state['active'])
        context = self.context.model_dump(mode='json')
        if revision_id:
            matches = [r for r in state['operations'].values() if r.get('revision_id') == revision_id]
            if matches:
                prior = matches[0]
                if (context != prior['context'] or reconsideration != prior['reason']
                        or observation_id != prior['observation_id']
                        or (inputs is not None and self._inputs(inputs) != prior['inputs'])):
                    raise ValueError("Revision identity reused with different context/reason/inputs")
                if prior['status'] == 'superseded' or (prior['status'] != 'completed' and state['active'] != prior['id']):
                    raise ValueError("Revision is superseded or no longer active")
                self._check_inputs(prior)
                return prior
        if active and active['status'] != 'completed':
            if reconsideration or (observation_id and observation_id != active['observation_id']):
                raise ValueError("Finish/recover pending operation before changing the question")
            if context != active['context']:
                raise ValueError("Pending context changed")
            if inputs is not None and self._inputs(inputs) != active['inputs']:
                raise ValueError("Pending observation binding changed")
            self._check_inputs(active)
            return active
        if not state['knowledge_commit']:
            if observation_id or inputs:
                raise ValueError("Reviewed theory bootstrap commit required before observation reveal")
            if reconsideration is not None and not reconsideration.strip():
                raise ValueError("Reconsideration requires a substantive reason")
            if active and not reconsideration and active['status'] == 'completed':
                if context != active['context']:
                    raise ValueError("New context requires explicit reconsideration")
                return active
            kind = 'bootstrap'
        else:
            if reconsideration is not None and not reconsideration.strip():
                raise ValueError("Reconsideration requires a substantive reason")
            if not observation_id and not reconsideration:
                if active and context == active['context']:
                    if inputs is not None and self._inputs(inputs) != active['inputs']:
                        raise ValueError("Supplied observation binding changed; identity or reconsideration required")
                    self._check_inputs(active)
                    return active
                if active:
                    raise ValueError("New context requires explicit reconsideration")
                reconsideration = 'New campaign using approved shared knowledge'
            if observation_id and not reconsideration:
                matches = [r for r in state['operations'].values()
                           if r['observation_id'] == observation_id and r['kind'] == 'observation']
                if matches:
                    prior = matches[-1]
                    if context != prior['context'] or (inputs is not None and self._inputs(inputs) != prior['inputs']):
                        raise ValueError("Observation identity/context reused with different inputs")
                    self._check_inputs(prior)
                    return prior
            kind = 'reconsideration' if reconsideration else 'observation'
            if kind == 'observation' and not inputs:
                raise ValueError("Observation requires explicit input bindings")
        if observation_id is not None:
            key(observation_id)
        identifier = uuid.uuid4().hex
        record = dict(id=identifier, campaign=self.context.campaign, kind=kind,
                      observation_id=observation_id, reason=reconsideration,
                      revision_id=revision_id,
                      context=context, inputs=self._inputs(inputs), status='ready',
                      turns=[], turn_id=None, decision=None)
        if reconsideration and inputs is None and active:
            record['inputs'] = self._inputs({label: value['path'] for label, value in active['inputs'].items()})
        state['active'] = identifier
        state['operations'][identifier] = record
        w.path(w.round_path(record)).mkdir(parents=True, exist_ok=True)
        w.save()
        return record

    def _prompt(self, record):
        w = self.workspace
        schemas = {name: cls.model_json_schema() for name, cls in
                   [('main', MainReply), ('author', Contribution), ('reviewer', Review)]}
        template = Environment(loader=FileSystemLoader(Path(__file__).resolve().parent / 'prompts'),
            autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True).get_template('campaign_main.jinja')
        return template.render(operation_id=record['id'],
            main_instructions_path=w.source / 'subagents/campaign-main/AGENTS.md', source_root=w.source,
            attempt_path=w.path(w.round_path(record) + '/attempt-' + str(len(record['turns']))),
            knowledge_path=w.root / 'data/knowledge' / w.material, schemas_json=json.dumps(schemas),
            context_json=json.dumps(record['context']), kind=record['kind'], reason=record['reason'],
            knowledge_commit=w.state['knowledge_commit'], inputs_json=json.dumps(record['inputs']))

    def _artifact(self, record, reference):
        """Canonical current-attempt artifact, never a participant reference."""
        w = self.workspace
        path = Path(reference)
        if '..' in path.parts:
            raise ValueError("Parent traversal artifact reference forbidden")
        relative = path.relative_to(w.root) if path.is_absolute() else path
        target = w.artifact(record, relative.as_posix())[0]
        attempt = w.path(w.round_path(record) + '/attempt-' + str(len(record['turns'])))
        if not target.is_relative_to(attempt):
            raise ValueError("Current attempt artifact required; preserve earlier attempts")
        return target.relative_to(w.root).as_posix()

    def _participants(self, native):
        """Only current public native activity supplies canonical-name bindings."""
        aliases, paths, activity, legacy = {}, {}, {}, {}
        for raw in native.items:
            item = unwrap(raw)
            if getattr(item, 'type', None) == 'subAgentActivity':
                alias, identifier = item.agent_path, item.agent_thread_id
                parts = alias.split('/')
                if (not alias.startswith('/root/') or any(p in ('', '.', '..') for p in parts[1:])
                        or '\\' in alias):
                    raise ValueError("Invalid native canonical participant path")
                if ((alias in aliases and aliases[alias] != identifier)
                        or (identifier in paths and paths[identifier] != alias)):
                    raise ValueError("Ambiguous/remapped native participant alias")
                aliases[alias], paths[identifier] = identifier, alias
                activity[identifier] = dict(agent_path=alias, thread_id=identifier,
                    kind=getattr(item.kind, 'value', item.kind), item_id=item.id)
            elif (getattr(item, 'type', None) == 'collabAgentToolCall'
                  and item.sender_thread_id == self.workspace.state['thread_id']):
                for identifier, state in item.agents_states.items():
                    if getattr(state.status, 'value', state.status) != 'shutdown':
                        legacy[identifier] = state
        def resolve(reference):
            if reference in aliases:
                return aliases[reference]
            if reference in activity or reference in legacy:
                return reference
            raise ValueError("Unobserved native participant reference")
        return resolve, activity, legacy

    def _native_review(self, sdk, native, adoption, record, kind):
        w = self.workspace
        resolve, activity, legacy = self._participants(native)
        author, reviewer = resolve(adoption.author_thread_id), resolve(adoption.reviewer_thread_id)
        if len({author, reviewer, w.state['thread_id']}) != 3:
            raise ValueError("Main, author and reviewer must be distinct native IDs")
        messages, proof = [], dict(main_thread_id=w.state['thread_id'], main_turn_id=native.id)
        for label, identifier, reference, role in [
            ('author', author, adoption.author_thread_id,
             'hypothesis-updater' if kind == 'knowledge' else 'experiment-designer'),
            ('reviewer', reviewer, adoption.reviewer_thread_id,
             'hypothesis-qa' if kind == 'knowledge' else 'experiment-design-qa')]:
            modern, old = activity.get(identifier), legacy.get(identifier)
            if modern is not None and modern['kind'] != 'completed':
                raise ValueError("Native participant work is incomplete/interrupted")
            if old is not None and (not completed(old.status) or not old.message):
                raise ValueError("Missing native completed author/reviewer evidence")
            # _turn has loaded/confirmed the parent first. Do not override child
            # permissions; exclude implicit response history, then read publicly.
            child = sdk.thread_resume(identifier, include_turns=False).read(include_turns=True).thread
            if (child.id != identifier or child.agent_role != role
                    or child.parent_thread_id != w.state['thread_id'] or not child.turns
                    or not completed(child.turns[-1].status)
                    or getattr(unwrap(child.status), 'type', None) == 'active'):
                raise ValueError("Wrong native role, parent or latest completion")
            message = final_text(child.turns[-1])
            if old is not None and message != old.message:
                raise ValueError("Native completion changed after Main observed it")
            messages.append(message)
            proof[label] = dict(thread_id=identifier, role=child.agent_role,
                parent_thread_id=child.parent_thread_id, turn_id=child.turns[-1].id,
                submitted_reference=reference, activity=modern, legacy_message_matched=old is not None)
        authored = Contribution.model_validate_json(messages[0])
        reviewed = Review.model_validate_json(messages[1])
        qa_author = resolve(reviewed.author_thread_id)
        if (authored.operation_id != record['id'] or reviewed.operation_id != record['id']
                or authored.kind != kind or reviewed.kind != kind
                or qa_author != author or reviewed.verdict != 'pass'
                or authored.conditions != reviewed.conditions
                or authored.knowledge_commit != reviewed.knowledge_commit):
            raise ValueError("Review does not approve this operational proposal")
        def normalize(value):
            return value.model_copy(update=dict(
                files={topic:self._artifact(record, path) for topic,path in value.files.items()},
                report_path=self._artifact(record, value.report_path)))
        authored, reviewed = normalize(authored), normalize(reviewed)
        reviewed = reviewed.model_copy(update={'author_thread_id':qa_author})
        if authored.files != reviewed.files:
            raise ValueError("Review file mapping differs from actual proposal")
        if authored.report_path == reviewed.report_path:
            raise ValueError("Independent review record required")
        return authored, reviewed, proof

    def _confirmed_main_turn(self, history, identifier, expected_text):
        if (history.id != self.workspace.state['thread_id'] or not history.turns
                or history.turns[-1].id != identifier or not completed(history.turns[-1].status)
                or getattr(unwrap(history.status), 'type', None) == 'active'):
            raise ValueError("Main native completion/history changed or is not current")
        turn = history.turns[-1]
        text = final_text(turn)
        if text != expected_text:
            raise ValueError("Main operational response changed between stream and history")
        return turn, text

    def _options(self, *, read_only=False):
        from openai_codex import ApprovalMode
        record = self.workspace.state['operations'][self.workspace.state['active']]
        return dict(cwd=str(self.workspace.path(self.workspace.attempt_path(record))),
                    approval_mode=ApprovalMode.deny_all, config=_attempt_config(self.workspace, record))

    def _turn(self, sdk, record, *, retry):
        w = self.workspace
        history = None
        if w.state['thread_id']:
            # Resume by the durable identity without implicit history hydration;
            # explicit authoritative history is still mandatory for known Main.
            print('[MAS] Resuming Main session.', file=sys.stderr, flush=True)
            thread = sdk.thread_resume(w.state['thread_id'], include_turns=False, **self._options())
            history = thread.read(include_turns=True).thread
        else:
            if w.state['head'] is not None or any(r.get('turn_id') or r.get('turns')
                                                  for r in w.state['operations'].values()):
                raise ValueError("Missing native Main identity for recorded work")
            print('[MAS] Starting Main session.', file=sys.stderr, flush=True)
            thread = sdk.thread_start(ephemeral=False, **self._options(),
                                      developer_instructions='Operate the explicitly bound scientific campaign only.')
            w.state['thread_id'] = thread.id
            w.save()
            # A thread created by this call has no prior turn to recover. The
            # backend can reject history reads until that first turn exists.
        if thread.id != w.state['thread_id'] or (history is not None and history.id != thread.id):
            raise ValueError("Native Main identity changed")
        token = f'[MAS operation {record["id"]}]'
        candidates = []
        for turn in (() if history is None else history.turns):
            if turn.id in record['turns']:
                continue
            for raw in turn.items:
                item = unwrap(raw)
                if getattr(item, 'type', None) == 'userMessage' and any(
                        token in getattr(unwrap(c), 'text', '') for c in item.content):
                    candidates.append(turn)
                    break
        if len(candidates) > 1:
            raise ValueError("Ambiguous native turn recovery")
        prior = candidates[0] if candidates else None
        running = prior is not None and getattr(prior.status, 'value', prior.status) == 'inProgress'
        if history is not None:
            if ((getattr(unwrap(history.status), 'type', None) == 'active' and not running)
                    or any(getattr(t.status, 'value', t.status) == 'inProgress'
                           and (prior is None or t.id != prior.id) for t in history.turns)):
                raise ValueError("Unknown running native turn; preserve and inspect")
            if prior is not None and history.turns[-1].id != prior.id:
                raise ValueError("Pending native turn is not the latest; preserve and inspect")
        if record['turn_id'] and (prior is None or prior.id != record['turn_id']):
            raise ValueError("Persisted turn not found in native history")
        if prior and completed(prior.status) and not retry:
            return self._confirmed_main_turn(history, prior.id, final_text(prior))
        if prior and not running:
            if not retry:
                raise RuntimeError("Failed/interrupted native turn retained; explicit retry required")
            record['turns'].append(prior.id)
            record['turn_id'] = None
            w.save()
            self._bindings()
            thread = sdk.thread_resume(w.state['thread_id'], include_turns=False, **self._options())
        handle = thread.turn(self._prompt(record), output_schema=MainReply.model_json_schema())
        if running and handle.id != prior.id:
            raise ValueError("SDK did not join the pending native turn")
        record['turn_id'] = handle.id
        record['status'] = 'running'
        w.save()
        print('[MAS] Waiting for Main completion.', file=sys.stderr, flush=True)
        native = handle.run()
        if not completed(native.status):
            raise RuntimeError("Native Main turn incomplete; no adoption")
        # TurnResult collects item-completed notifications; hydrated history can
        # additionally contain native sub-agent activity. Confirm the exact Main
        # turn through its public history before resolving any participant.
        return self._confirmed_main_turn(thread.read(include_turns=True).thread, native.id, native.final_response)

    def _supersede(self, sdk, record, reason):
        """Only explicit reconsideration can retire a terminal incomplete operation."""
        w = self.workspace
        if not reason.strip():
            raise ValueError("Reconsideration requires a substantive reason")
        if w.state['thread_id']:
            history = sdk.thread_resume(w.state['thread_id'], include_turns=False, **self._options()).read(include_turns=True).thread
            if history.id != w.state['thread_id']:
                raise ValueError("Native Main identity changed")
            if (getattr(unwrap(history.status), 'type', None) == 'active'
                    or any(getattr(t.status, 'value', t.status) == 'inProgress' for t in history.turns)):
                raise ValueError("Cannot supersede a running native turn")
            if record['turn_id'] and record['turn_id'] not in {t.id for t in history.turns}:
                raise ValueError("Cannot establish terminal status for the pending turn")
        elif record['turn_id']:
            raise ValueError("Missing Main identity for pending turn")
        record['status'] = 'superseded'
        record['superseded_reason'] = reason
        w.state['active'] = None
        w.save()

    def run(self, *, observation_id=None, inputs=None, reconsideration=None, revision_id=None, retry=False):
        """Return Decision, or None after publication; ordinary restarts never reconsider."""
        w = self.workspace
        w.native_homes()
        if revision_id is not None:
            key(revision_id)
            if not reconsideration or not reconsideration.strip():
                raise ValueError("Revision identity requires a substantive reconsideration reason")
        with w.lock(reconcile=bool(reconsideration)), ExitStack() as resources:
            if w.state['pending']:
                knowledge = w.state['pending']['knowledge']
                try:
                    w.recover_publication()
                except Exception as error:
                    print(f'[MAS] Publication recovery failed ({type(error).__name__}).', file=sys.stderr, flush=True)
                    raise
                print(f"[MAS] Recovered {'knowledge' if knowledge else 'decision'} publication at {w.state['head']}.",
                      file=sys.stderr, flush=True)
            sdk = None
            active = w.state['operations'].get(w.state['active'])
            existing_revision = revision_id and any(r.get('revision_id') == revision_id for r in w.state['operations'].values())
            if reconsideration is not None and active and active['status'] != 'completed' and not existing_revision:
                print('[MAS] Connecting SDK for reconsideration.', file=sys.stderr, flush=True)
                manager = self.sdk_factory()
                sdk = resources.enter_context(manager) if hasattr(manager, '__enter__') else manager
                self._supersede(sdk, active, reconsideration)
            record = self._operation(observation_id, inputs, reconsideration, revision_id)
            self.last_operation_id = record['id']
            w.check_selection(record)
            if record['status'] == 'completed':
                action = record['decision']['action'].upper() if record['decision'] else 'knowledge'
                print(f'[MAS] Reusing validated cached {action} result; no SDK connection.', file=sys.stderr, flush=True)
                return Decision.model_validate(record['decision']) if record['decision'] else None
            self._bindings()
            try:
                if sdk is None:
                    print('[MAS] Connecting SDK.', file=sys.stderr, flush=True)
                    manager = self.sdk_factory()
                    sdk = resources.enter_context(manager) if hasattr(manager, '__enter__') else manager
                native, text = self._turn(sdk, record, retry=retry)
                reply = MainReply.model_validate_json(text)
                self._check_inputs(record)
                if self.context.model_dump(mode='json') != record['context']:
                    raise ValueError("Operator context changed during native work")
                self._adopt(sdk, native, reply, record)
                if native.id not in record['turns']:
                    record['turns'].append(native.id)
                record['turn_id'] = None
                w.save()
                return reply.decision
            except Exception as error:
                w.state['failures'].append(dict(operation=record['id'], turn_id=record['turn_id'],
                                                type=type(error).__name__, message=str(error)))
                w.save()
                print(f'[MAS] Request failed ({type(error).__name__}); failure recorded.', file=sys.stderr, flush=True)
                raise

    def _adopt(self, sdk, native, reply, record):
        w = self.workspace
        reply = reply.model_copy(update={'records':[self._artifact(record, p) for p in reply.records]})
        receipt = {'operation_id': record['id'], 'main_thread_id': w.state['thread_id'],
                   'turn_id': native.id, 'adoption': reply.model_dump(mode='json')}
        files = {}
        observations, selected = {}, {}
        def take(relative):
            if relative not in selected:
                data, identity = w.select_publication(record,native.id,relative)
                selected[relative], observations[relative] = data, identity
            return selected[relative]
        artifacts = []
        for relative in reply.records:
            files[relative] = take(relative)
            _, kind = w.artifact(record, relative, data=files[relative])
            artifacts.append(dict(path=relative, kind=kind, operation_id=record['id'], inputs=record['inputs']))
        if sum(len(v) for v in files.values()) > MAX_ADOPTION:
            raise ValueError('Adoption exceeds 64 MiB')
        if reply.knowledge:
            author, review, proof = self._native_review(sdk, native, reply.knowledge, record, 'knowledge')
            reply = reply.model_copy(update={'knowledge':reply.knowledge.model_copy(update={
                'author_thread_id':proof['author']['thread_id'], 'reviewer_thread_id':proof['reviewer']['thread_id']})})
            receipt['native_review'] = proof
            if (not author.files or set(author.files) - set(TOPICS)
                    or author.conditions is not None or author.knowledge_commit is not None):
                raise ValueError("Invalid knowledge publication receipt")
            if record['kind'] == 'bootstrap' and set(author.files) != set(TOPICS):
                raise ValueError("Initial theory review must cover all four topics")
            for topic, proposed in author.files.items():
                files[f'data/knowledge/{w.material}/{topic}'] = take(proposed)
                files[proposed] = files[f'data/knowledge/{w.material}/{topic}']
            for relative in (author.report_path, review.report_path):
                files[relative] = take(relative)
            receipt['author'] = author.model_dump(mode='json')
            receipt['review'] = review.model_dump(mode='json')
        else:
            decision = reply.decision
            if record['kind'] == 'bootstrap' and decision.action == 'run':
                raise ValueError("Bootstrap cannot execute experiments")
            if decision.knowledge_commit != w.state['knowledge_commit']:
                raise ValueError("Decision knowledge version drift")
            if decision.action == 'run':
                author, review, proof = self._native_review(sdk, native, reply.design, record, 'design')
                reply = reply.model_copy(update={'design':reply.design.model_copy(update={
                    'author_thread_id':proof['author']['thread_id'], 'reviewer_thread_id':proof['reviewer']['thread_id']})})
                receipt['native_review'] = proof
                if (author.files or author.knowledge_commit != w.state['knowledge_commit']
                        or author.conditions != decision.next_params):
                    raise ValueError("Final conditions/version differ from independently reviewed design")
                validate_conditions(decision.next_params, self.context)
                for relative in (author.report_path, review.report_path):
                    files[relative] = take(relative)
                receipt['author'] = author.model_dump(mode='json')
                receipt['review'] = review.model_dump(mode='json')
            record['decision'] = decision.model_dump(mode='json')
            relative = w.round_path(record) + '/decision.md'
            links = '\n'.join(f'- [{Path(p).name}]({os.path.relpath(w.path(p), w.path(w.round_path(record)))})'
                              for p in files)
            text = (f'# Campaign decision: {decision.action}\n\n{decision.reason}\n\n'
                    f'Knowledge commit: {decision.knowledge_commit}\n\n'
                    f'Accepted records:\n{links or "No additional authored records were adopted."}\n')
            files[relative] = text
            record['report_path'] = relative
        receipt['adoption'] = reply.model_dump(mode='json')
        for artifact in artifacts:
            artifact['native_review'] = receipt.get('native_review')
            if artifact['kind'] != 'markdown' and not artifact['native_review']:
                raise ValueError('Derived artifacts require native author/reviewer provenance')
        receipt['artifacts'] = artifacts
        files[w.round_path(record) + '/adoption.json'] = json.dumps(receipt, indent=2) + '\n'
        w.publish(record, files, knowledge=reply.knowledge is not None, observations=observations)
        if reply.knowledge:
            print(f"[MAS] Knowledge published at {w.state['knowledge_commit']}.", file=sys.stderr, flush=True)
        else:
            print(f'[MAS] Accepted final action: {reply.decision.action.upper()}.', file=sys.stderr, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Report-only adaptive MAS; never submit a device request')
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--material', required=True)
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--observation-id')
    parser.add_argument('--input', action='append', default=[], metavar='LABEL=PATH')
    parser.add_argument('--reconsider')
    parser.add_argument('--revision-id', help='Stable reconsideration identity for restart/lost-ack reuse')
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--live', action='store_true', help='Explicitly start/resume the model, never a device')
    args = parser.parse_args(argv)
    if bool(args.reconsider) != bool(args.revision_id):
        parser.error('--reconsider and a stable --revision-id must be supplied together')
    inputs = {}
    for binding in args.input:
        label, separator, path = binding.partition('=')
        if not separator or label in inputs:
            parser.error('Unique LABEL=PATH input bindings required')
        inputs[label] = Path(path)
    context_path = Workspace.operator_context_path(args.repo, args.context)
    context = Context.model_validate_json(context_path.read_text(encoding='utf-8'))
    runtime = CampaignRuntime(Workspace(args.repo, context.campaign, args.material), context)
    if not args.live:
        print('{"status":"NOT_RUN","reason":"Add --live only within an authorized invocation"}')
        return
    decision = runtime.run(observation_id=args.observation_id, inputs=inputs or None,
                           reconsideration=args.reconsider, revision_id=args.revision_id, retry=args.retry)
    print(decision.model_dump_json() if decision else '{"status":"knowledge_published"}')


if __name__ == '__main__':
    main()
