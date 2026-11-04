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
                         env={'PILOT_ROOT': str(workspace.source),
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

    def _bindings(self):
        w = self.workspace
        # Discover registered roles in the independent output root, with source
        # role documents resolved through PILOT_ROOT; do not copy source/data.
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

    def _operation(self, observation_id, inputs, reconsideration):
        w, state = self.workspace, self.workspace.state
        active = state['operations'].get(state['active'])
        context = self.context.model_dump(mode='json')
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
and approved shared workflow/knowledge/analysis contracts. PILOT_ROOT={w.source}.
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
Develop readable Markdown candidates and separate reviewer findings. Each native
author/reviewer final answer uses only the small operational receipt schema below,
never echoes report bodies. Receipt operation_id must be {record['id']}.
files maps topic filename to current-round proposal path; design uses files={{}}.
report_path names its own nonempty round Markdown record. No edits after review;
MainReply.records explicitly names any additional relevant accepted round Markdown
to preserve in Git, without dummy reports. Native author/review records and adopted
topic proposals are also committed. Do not select inputs/raw/media/cache files.
if revised, obtain renewed native author/reviewer completions. Reject/retain findings honestly.
Knowledge author conditions/knowledge_commit are null. Knowledge QA returns same
operational file mapping and author_thread_id with pass/fail, never repairs a draft.
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

    def _native_review(self, sdk, native, adoption, record, kind):
        w = self.workspace
        author, reviewer = adoption.author_thread_id, adoption.reviewer_thread_id
        if len({author, reviewer, w.state['thread_id']}) != 3:
            raise ValueError("Main, author and reviewer must be distinct")
        observed = {}
        for raw in native.items:
            item = unwrap(raw)
            if (getattr(item, 'type', None) == 'collabAgentToolCall'
                    and item.sender_thread_id == w.state['thread_id']):
                for identifier, state in item.agents_states.items():
                    if getattr(state.status, 'value', state.status) != 'shutdown':
                        observed[identifier] = state
        messages = []
        for identifier, role in [(author, 'hypothesis-updater' if kind == 'knowledge' else 'experiment-designer'),
                                 (reviewer, 'hypothesis-qa' if kind == 'knowledge' else 'experiment-design-qa')]:
            seen = observed.get(identifier)
            if seen is None or not completed(seen.status) or not seen.message:
                raise ValueError("Missing native completed author/reviewer evidence")
            child = sdk.thread_resume(identifier).read(include_turns=True).thread
            if (child.id != identifier or child.agent_role != role
                    or child.parent_thread_id != w.state['thread_id'] or not child.turns
                    or not completed(child.turns[-1].status)):
                raise ValueError("Wrong native role, parent or completion")
            # Only small operational completion receipts are compared, never reports.
            message = final_text(child.turns[-1])
            if message != seen.message:
                raise ValueError("Native completion changed after Main observed it")
            messages.append(message)
        authored = Contribution.model_validate_json(messages[0])
        reviewed = Review.model_validate_json(messages[1])
        if (authored.operation_id != record['id'] or reviewed.operation_id != record['id']
                or authored.kind != kind or reviewed.kind != kind
                or reviewed.author_thread_id != author or reviewed.verdict != 'pass'
                or authored.files != reviewed.files or authored.conditions != reviewed.conditions
                or authored.knowledge_commit != reviewed.knowledge_commit):
            raise ValueError("Review does not approve this operational proposal")
        w.proposal(record, authored.report_path)
        w.proposal(record, reviewed.report_path)
        attempt = w.path(w.round_path(record) + '/attempt-' + str(len(record['turns'])))
        for relative in [authored.report_path, reviewed.report_path, *authored.files.values()]:
            if not w.proposal(record, relative).is_relative_to(attempt):
                raise ValueError("New native contributions must preserve prior attempt paths")
        if authored.report_path == reviewed.report_path:
            raise ValueError("Independent review record required")
        return authored, reviewed

    def _options(self, *, read_only=False):
        from openai_codex import ApprovalMode, Sandbox
        return dict(cwd=str(self.workspace.root), approval_mode=ApprovalMode.deny_all,
                    sandbox=Sandbox.read_only if read_only else Sandbox.workspace_write)

    def _turn(self, sdk, record, *, retry):
        w = self.workspace
        if w.state['thread_id']:
            thread = sdk.thread_resume(w.state['thread_id'], **self._options())
        else:
            thread = sdk.thread_start(ephemeral=False, **self._options(),
                                      developer_instructions='Operate the explicitly bound scientific campaign only.')
            w.state['thread_id'] = thread.id
            w.save()
        history = thread.read(include_turns=True).thread
        if thread.id != w.state['thread_id'] or history.id != thread.id:
            raise ValueError("Native Main identity changed")
        token = f'[MAS operation {record["id"]}]'
        candidates = []
        for turn in history.turns:
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
        if prior is None and getattr(unwrap(history.status), 'type', None) == 'active':
            raise ValueError("Unknown running native turn; preserve and inspect")
        if record['turn_id'] and (prior is None or prior.id != record['turn_id']):
            raise ValueError("Persisted turn not found in native history")
        running = prior is not None and getattr(prior.status, 'value', prior.status) == 'inProgress'
        if prior and completed(prior.status) and not retry:
            return prior, final_text(prior)
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
        return native, native.final_response

    def _supersede(self, sdk, record, reason):
        """Only explicit reconsideration can retire a terminal incomplete operation."""
        w = self.workspace
        if not reason.strip():
            raise ValueError("Reconsideration requires a substantive reason")
        if w.state['thread_id']:
            history = sdk.thread_resume(w.state['thread_id'], **self._options()).read(include_turns=True).thread
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

    def run(self, *, observation_id=None, inputs=None, reconsideration=None, retry=False):
        """Return Decision, or None after publication; ordinary restarts never reconsider."""
        w = self.workspace
        with w.lock(), ExitStack() as resources:
            if w.state['pending']:
                w.recover_publication()
            sdk = None
            active = w.state['operations'].get(w.state['active'])
            if reconsideration is not None and active and active['status'] != 'completed':
                manager = self.sdk_factory()
                sdk = resources.enter_context(manager) if hasattr(manager, '__enter__') else manager
                self._supersede(sdk, active, reconsideration)
            record = self._operation(observation_id, inputs, reconsideration)
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
        receipt = {'operation_id': record['id'], 'main_thread_id': w.state['thread_id'],
                   'turn_id': native.id, 'adoption': reply.model_dump(mode='json')}
        files = {}
        for relative in reply.records:
            files[relative] = w.proposal(record, relative).read_text(encoding='utf-8')
        if reply.knowledge:
            author, review = self._native_review(sdk, native, reply.knowledge, record, 'knowledge')
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
                author, review = self._native_review(sdk, native, reply.design, record, 'design')
                if (author.files or author.knowledge_commit != w.state['knowledge_commit']
                        or author.conditions != decision.next_params):
                    raise ValueError("Final conditions/version differ from independently reviewed design")
                validate_conditions(decision.next_params, self.context)
                for relative in (author.report_path, review.report_path):
                    files[relative] = w.proposal(record, relative).read_text(encoding='utf-8')
                receipt['author'] = author.model_dump(mode='json')
                receipt['review'] = review.model_dump(mode='json')
            record['decision'] = decision.model_dump(mode='json')
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
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--live', action='store_true', help='Explicitly start/resume the model, never a device')
    args = parser.parse_args(argv)
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
                           reconsideration=args.reconsider, retry=args.retry)
    print(decision.model_dump_json() if decision else '{"status":"knowledge_published"}')


if __name__ == '__main__':
    main()
