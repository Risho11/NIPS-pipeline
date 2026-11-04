"""Adaptive persistent scientific Main. This entrypoint never submits experiments."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from mas_contract import (Context, Contribution, Decision, MainReply, Review, TOPICS,
                          validate_conditions)
from mas_workspace import Workspace, file_digest, key

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
    from codex_cli_bin import bundled_codex_path
    from openai_codex import Codex, CodexConfig, __version__
    if __version__ != '0.163.0':
        raise RuntimeError("Pinned openai-codex 0.163.0 required")
    overrides = (
        'project_root_markers=[]', 'sandbox_mode="workspace-write"',
        'sandbox_workspace_write.writable_roots=[]',
        'sandbox_workspace_write.exclude_slash_tmp=true',
        'sandbox_workspace_write.exclude_tmpdir_env_var=true',
        'sandbox_workspace_write.network_access=false', 'web_search="disabled"',
        'features.apps=false', 'features.plugins=false', 'features.memories=false',
        'agents.enabled=true',
    )
    scratch = workspace.path('.scratch')
    config = CodexConfig(cwd=str(workspace.root), codex_bin=str(bundled_codex_path()),
                         config_overrides=overrides,
                         env={'MAS_SOURCE_ROOT': str(workspace.source),
                              'PYTHONDONTWRITEBYTECODE': '1',
                              'TMPDIR': str(scratch), 'TMP': str(scratch), 'TEMP': str(scratch),
                              'UV_CACHE_DIR': str(scratch / 'uv-cache'),
                              'UV_OFFLINE': '1', 'UV_NO_SYNC': '1', 'UV_NO_PROJECT': '1',
                              'UV_PYTHON_DOWNLOADS': 'never', 'UV_PYTHON': sys.executable,
                              'VIRTUAL_ENV': sys.prefix, 'UV_PROJECT_ENVIRONMENT': sys.prefix,
                              'XDG_CACHE_HOME': str(scratch / 'cache'),
                              'MPLCONFIGDIR': str(scratch / 'matplotlib')})
    scratch.mkdir(exist_ok=True)

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
        self.sdk_factory = sdk_factory or (lambda: isolated_sdk(workspace))
        self.last_operation_id = None

    def _bindings(self):
        w = self.workspace
        # Discover registered roles in the independent output root, with source
        # role documents resolved through MAS_SOURCE_ROOT; do not copy source/data.
        for role in ROLES:
            source = w.source / '.codex/agents' / f'{role}.toml'
            if source.is_symlink() or not source.is_file():
                raise ValueError("Missing regular source role binding")
            w.write(f'.codex/agents/{role}.toml', source.read_text(encoding='utf-8'))

    def _inputs(self, inputs):
        result = {}
        for label, source in (inputs or {}).items():
            key(label)
            p = Path(source)
            if p.is_symlink() or not p.is_file() or p.resolve().is_relative_to(self.workspace.root):
                raise ValueError("Original inputs must be regular files outside output root")
            result[label] = {'path': str(p.resolve()), 'sha256': file_digest(p)}
        return result

    def _check_inputs(self, record):
        for value in record['inputs'].values():
            if file_digest(value['path']) != value['sha256']:
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
                raise ValueError("New context requires explicit reconsideration")
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
        return f'''[MAS operation {record['id']}]
You are persistent scientific campaign Main, not a development Writer.
Read {w.source / 'subagents/campaign-main/AGENTS.md'} and its guide,
and approved shared workflow/knowledge/analysis contracts. MAS_SOURCE_ROOT={w.source}.
Source and original data are read-only. All drafts, reviews, scripts and figures
belong in {w.path(w.round_path(record) + '/attempt-' + str(len(record['turns'])))}.
Use uv run --no-sync python for analysis with the prepared interpreter and bound
workspace-local scratch/cache environment. Never install, sync or download dependencies.
Preserve earlier attempt files and failed findings; use this attempt's new paths.
Canonical topics under
{w.root / 'data/knowledge' / w.material} and .mas-state.json are host-published:
no agent edits them, uses Git, changes configuration, starts SDKs, services or devices.
Use registered roles, integrated hypothesis-updater with independent hypothesis-qa;
optional analyst only for an actual split trigger, designer with distinct design QA.
Reuse sessions as useful; do not force a fixed stage loop, new hypothesis or figure.
The optional analyst returns bounded findings/artifacts to Main/integrated author;
it is not a direct knowledge/design adoption role and adds no extra QA stage.
Develop readable Markdown candidates and separate reviewer findings. Each native
adoption author/reviewer final answer uses only the small operational receipt schema below,
never echoes report bodies. Receipt operation_id must be {record['id']}.
Artifact references (files values, report_path and MainReply.records) must name
nonempty Markdown in this exact current attempt. Either a workspace-relative path
or an absolute path inside that attempt is accepted and published as a relative
path. Never use parent traversal, earlier attempts, links or external/raw/cache files.
files maps topic filename to proposal path; design uses files={{}}.
report_path names its own separate authored/review Markdown record. No edits after review;
MainReply.records explicitly names any additional relevant accepted attempt Markdown
to preserve in Git, without dummy reports. Native author/review records and adopted
topic proposals are also committed. Do not select inputs/raw/media/cache files.
if revised, obtain renewed native author/reviewer completions. Reject/retain findings honestly.
Knowledge author conditions/knowledge_commit are null. Knowledge QA returns same
operational file mapping and author_thread_id with pass/fail, never repairs a draft.
Participant fields author_thread_id/reviewer_thread_id are a separate namespace:
use the actual observed native UUID or canonical /root/... participant reference.
Never invent a binding or treat a participant reference as an artifact path.
Main must observe current completed native participant activity before adoption;
the host resolves actual IDs and reads each child's public latest completion.
Design author and design QA include exact conditions and the current knowledge
commit, plus separate Markdown records. Only run may carry conditions.
Host validates actual native role metadata/completion, not your assertion of PASS.
{json.dumps(schemas)}
Knowledge publication and final design/decision are separate operational returns:
after host publishes, continue the question using the actual commit supplied below.
If no justified executable design, decide hold/stop with null next_params/design.
No recommendation authorizes execution. Keep the original objective and pending work explicit.
Context: {json.dumps(record['context'])}
Kind: {record['kind']}; reason: {record['reason']}
Knowledge commit: {w.state['knowledge_commit']}
{'BOOTSTRAP: theory/provenance only before outcomes; do not read observations, historical reports, notebooks or outcome-bearing source sections. Disclose actual exposure; no global blindness claim. Return all four topic proposals and independent review. If initialization cannot be completed, return hold/stop with null knowledge_commit and no executable conditions; this does not initialize knowledge or unlock observation access.' if record['kind'] == 'bootstrap' else 'Authorized observations (do not modify): ' + json.dumps(record['inputs'])}
Return only MainReply JSON. Use English records; preserve uncertainty and original meanings.
'''

    def _artifact(self, record, reference):
        """Canonical current-attempt artifact, never a participant reference."""
        w = self.workspace
        path = Path(reference)
        if '..' in path.parts:
            raise ValueError("Parent traversal artifact reference forbidden")
        relative = path.relative_to(w.root) if path.is_absolute() else path
        target = w.proposal(record, relative.as_posix())
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
        from openai_codex import ApprovalMode, Sandbox
        return dict(cwd=str(self.workspace.root), approval_mode=ApprovalMode.deny_all,
                    sandbox=Sandbox.read_only if read_only else Sandbox.workspace_write)

    def _turn(self, sdk, record, *, retry):
        w = self.workspace
        history = None
        if w.state['thread_id']:
            # Resume by the durable identity without implicit history hydration;
            # explicit authoritative history is still mandatory for known Main.
            thread = sdk.thread_resume(w.state['thread_id'], include_turns=False, **self._options())
            history = thread.read(include_turns=True).thread
        else:
            if w.state['head'] is not None or any(r.get('turn_id') or r.get('turns')
                                                  for r in w.state['operations'].values()):
                raise ValueError("Missing native Main identity for recorded work")
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
        handle = thread.turn(self._prompt(record), output_schema=MainReply.model_json_schema())
        if running and handle.id != prior.id:
            raise ValueError("SDK did not join the pending native turn")
        record['turn_id'] = handle.id
        record['status'] = 'running'
        w.save()
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
        if revision_id is not None:
            key(revision_id)
            if not reconsideration or not reconsideration.strip():
                raise ValueError("Revision identity requires a substantive reconsideration reason")
        with w.lock(), ExitStack() as resources:
            if w.state['pending']:
                w.recover_publication()
            sdk = None
            active = w.state['operations'].get(w.state['active'])
            existing_revision = revision_id and any(r.get('revision_id') == revision_id for r in w.state['operations'].values())
            if reconsideration is not None and active and active['status'] != 'completed' and not existing_revision:
                manager = self.sdk_factory()
                sdk = resources.enter_context(manager) if hasattr(manager, '__enter__') else manager
                self._supersede(sdk, active, reconsideration)
            record = self._operation(observation_id, inputs, reconsideration, revision_id)
            self.last_operation_id = record['id']
            if record['status'] == 'completed':
                return Decision.model_validate(record['decision']) if record['decision'] else None
            self._bindings()
            try:
                if sdk is None:
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
                raise

    def _adopt(self, sdk, native, reply, record):
        w = self.workspace
        reply = reply.model_copy(update={'records':[self._artifact(record, p) for p in reply.records]})
        receipt = {'operation_id': record['id'], 'main_thread_id': w.state['thread_id'],
                   'turn_id': native.id, 'adoption': reply.model_dump(mode='json')}
        files = {}
        for relative in reply.records:
            files[relative] = w.proposal(record, relative).read_text(encoding='utf-8')
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
                files[f'data/knowledge/{w.material}/{topic}'] = w.proposal(record, proposed).read_text(encoding='utf-8')
                files[proposed] = w.proposal(record, proposed).read_text(encoding='utf-8')
            for relative in (author.report_path, review.report_path):
                files[relative] = w.proposal(record, relative).read_text(encoding='utf-8')
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
                    files[relative] = w.proposal(record, relative).read_text(encoding='utf-8')
                receipt['author'] = author.model_dump(mode='json')
                receipt['review'] = review.model_dump(mode='json')
            record['decision'] = decision.model_dump(mode='json')
            relative = w.round_path(record) + '/decision.md'
            links = '\n'.join(f'- [{Path(p).name}]({os.path.relpath(w.path(p), w.path(w.round_path(record)))})'
                              for p in files)
            text = (f'# Campaign decision: {decision.action}\n\n{decision.reason}\n\n'
                    f'Knowledge commit: {decision.knowledge_commit}\n\n'
                    f'Accepted records:\n{links or "No additional authored records were adopted."}\n')
            w.write(relative, text)
            files[relative] = text
            record['report_path'] = relative
        receipt['adoption'] = reply.model_dump(mode='json')
        files[w.round_path(record) + '/adoption.json'] = json.dumps(receipt, indent=2) + '\n'
        w.publish(record, files, knowledge=reply.knowledge is not None)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Report-only adaptive MAS; never submit a device request')
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
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
    runtime = CampaignRuntime(Workspace(args.workspace, args.source, args.material),
                              Context.model_validate_json(args.context.read_text(encoding='utf-8')))
    if not args.live:
        print('{"status":"NOT_RUN","reason":"Add --live only within an authorized invocation"}')
        return
    decision = runtime.run(observation_id=args.observation_id, inputs=inputs or None,
                           reconsideration=args.reconsider, revision_id=args.revision_id, retry=args.retry)
    print(decision.model_dump_json() if decision else '{"status":"knowledge_published"}')


if __name__ == '__main__':
    main()
