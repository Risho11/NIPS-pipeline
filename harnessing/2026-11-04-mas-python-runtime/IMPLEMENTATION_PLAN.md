# Python adaptive MAS implementation plan

Human message 01a1a72e-874a-7a40-b00d-93e849c87cf7 in Controller chat 01a19fab-662c-7512-932e-29a933aa8ea2 explicitly authorizes a new Python MAS execution architecture, implementation, MAS legacy cleanup and Goal execution.

FRESH_START, STANDARD_CONTROLLER_WRITER, MANUAL_GIT_TRANSITIONS. Same branch/worktree; no inherited Writer ownership. The initial predecessor preflight is PROCEED / VERIFIED_PREDECESSOR; source baseline, current authority, pinned governor and approved scientific contracts were verified. Historical direct-session usefulness is design input, not acceptance of this Python implementation. Existing old Harness deferred DCPs remain historical and untouched. This plan has one final active DCP.

Controller owns only new Harness files; Writer owns only explicit current product paths. Initial planning/readability and fresh independent planning QA precede implementation. Each product step returns quiescent, then fresh independent full-diff QA and ordinary exact-file Git. Current executable scope has no configured lint/typecheck/build application gate; use actual unittest/schema/syntax/structure/link/TOML validation and name unrun live/hosted/physical checks.

### Phase 1: Implement the adaptive campaign runtime
1. STEP 1: Implement the adaptive campaign runtime
```harness-step-json
{"phase": 1, "step": 1, "expected_commit_msg": "feat implement adaptive MAS campaign runtime", "prompt": "steps/PHASE_1_STEP_1_PROMPT.md"}
```

Literal ownership and validation: [steps/PHASE_1_STEP_1_PROMPT.md](steps/PHASE_1_STEP_1_PROMPT.md).
- `src/pipeline/mas_contract.py`
- `src/pipeline/mas_workspace.py`
- `src/pipeline/mas_runtime.py`
- `tests/test_mas_contract.py`
- `tests/test_mas_workspace.py`
- `tests/test_mas_runtime.py`
- `docs/mas/python-runtime.md`

Implement the smallest three-module runtime with a report-only command entrypoint in mas_runtime.py and meaningful offline tests; document the actual API/layout. mas_contract owns only finite tunables/operator context, run/hold/stop handoff and operational review/publication receipt data. mas_workspace owns explicit workspace/source binding, independent Git, topic/round paths and durable recovery. mas_runtime owns persistent SDK Main lifecycle and native review/condition validation. Choose a small supported public API, document it and use it in Step2 rather than retain an obsolete adapter shim. The CLI must be import-safe and never submit experiments; explicit workspace/material/campaign binding and reconsideration are operational inputs, not new operator material defaults.

Apply REQUIREMENTS.md across bootstrap, native QA and knowledge/design publication, no report hash/equality gates, writable analysis artifacts, interrupted resume, explicit reconsideration, exact conditions and Main-only publication. Prefer minimal real boundaries over a framework. Inspect installed pinned SDK 0.163.0 public api.py/generated models without starting a client. A mocked client must exercise actual SDK-shaped completion/role metadata; do not validate a fiction that the real SDK cannot supply. Persist thread/round identity before work, preserve failures and publication recovery. Do not invent resource readiness or expose outcome inputs before the initial commit. Reject retired state rather than silently migrate it.

Run `uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_contract.py'`, then the same command with `test_mas_workspace.py` and `test_mas_runtime.py` on a stable candidate; run focused cases during repairs. Also run `git diff --check`, syntax-parse all owned Python without starting SDK/devices, and verify source/data/settings preservation. The declared full Step1 gate is all three complete new contract/workspace/runtime test suites, including genuine negative/restart/Git/native-review boundaries. No blanket pytest discovery: repository test scripts include operational/dev paths and no pytest dependency is configured. No full material fitting suite is needed for this runtime-only step.

### Phase 2: Integrate adaptive execution and retire MAS compatibility paths
1. STEP 1: Integrate adaptive execution and retire MAS compatibility paths
```harness-step-json
{"phase": 2, "step": 1, "expected_commit_msg": "feat integrate adaptive MAS and remove superseded paths", "prompt": "steps/PHASE_2_STEP_1_PROMPT.md"}
```

Literal ownership and validation: [steps/PHASE_2_STEP_1_PROMPT.md](steps/PHASE_2_STEP_1_PROMPT.md).
- `src/pipeline/mas_contract.py`
- `src/pipeline/mas_workspace.py`
- `src/pipeline/mas_runtime.py`
- `tests/test_mas_contract.py`
- `tests/test_mas_workspace.py`
- `tests/test_mas_runtime.py`
- `docs/mas/python-runtime.md`
- `src/pipeline/run_loop.py`
- `src/pipeline/codex_context.py`
- `src/pipeline/mas_records.py`
- `src/pipeline/mas_schema.py`
- `src/pipeline/mas_analysis.py`
- `scripts/mas_agent_pilot.py`
- `tests/test_mas.py`
- `tests/test_mas_agent_pilot.py`
- `tests/test_dynamic_routing.py`
- `.github/workflows/ci.yml`
- `AGENTS.md`
- `README.md`
- `docs/mas/README.md`
- `docs/mas/workflow.md`
- `docs/mas/data-contract.md`
- `docs/mas/knowledge.md`
- `docs/mas/analysis-methods.md`
- `docs/mas/pilot-evaluation.md`
- `subagents/campaign-main/AGENTS.md`
- `subagents/campaign-main/docs/campaign-guide.md`
- `.codex/agents/experiment-analyst.toml`
- `subagents/experiment-analyst/AGENTS.md`
- `subagents/experiment-analyst/docs/analysis-guide.md`
- `.codex/agents/hypothesis-updater.toml`
- `subagents/hypothesis-updater/AGENTS.md`
- `subagents/hypothesis-updater/docs/hypothesis-guide.md`
- `.codex/agents/hypothesis-qa.toml`
- `subagents/hypothesis-qa/AGENTS.md`
- `subagents/hypothesis-qa/docs/review-checklist.md`
- `.codex/agents/experiment-designer.toml`
- `subagents/experiment-designer/AGENTS.md`
- `subagents/experiment-designer/docs/design-guide.md`
- `.codex/agents/experiment-design-qa.toml`
- `subagents/experiment-design-qa/AGENTS.md`
- `subagents/experiment-design-qa/docs/review-checklist.md`
- `.codex/agents/experiment-analysis-qa.toml`
- `subagents/experiment-analysis-qa/AGENTS.md`
- `subagents/experiment-analysis-qa/docs/review-checklist.md`

Read the independently accepted Phase1Step1 API, actual step1-writer-handoff.md, independent QA and source commit bound by Controller handoff. Replace run_loop's dynamic route with that runtime and provide an intentional, documented reconsideration path. Preserve existing measured-result processing, operator values/default mode, stock validator behavior, exact reviewed point and durable request/journal/checkpoint identity. Test initial and continuing campaigns, RUN/HOLD/STOP, same-session recovery, meaningful explicit HOLD reconsideration and ambiguous/acknowledged submissions. Do not erase QA/checkpoint markers or reissue an already submitted experiment to enable reconsideration.

Remove the four old MAS modules, old fixed-report test_mas.py, old pilot script/test and compatibility-only experiment-analysis-qa binding/docs. Update imports, test fixtures, CI, all owned active docs/roles to the actual new API and the five kept registered specialist roles; keep optional analyst under unified hypothesis-qa. Preserve shared CSV columns and non-MAS routes. Keep pilot-evaluation.md only as a clearly historical evaluation boundary with working current entrypoint references; no stale runnable example. Preserve historical Harness files and removed code in Git, without a copied archive or forwarding shim. Keep root README concise and use docs/mas/python-runtime.md as the detailed owner. If a new required consumer path is unowned, return it for bounded replan rather than quietly editing.

On the stable final integrated candidate, run each exact complete safe suite (not only focused cases): `uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_runtime.py'`; same command with `test_mas_contract.py`, `test_mas_workspace.py`, `test_dynamic_routing.py`, `test_warm_start.py`, `test_network_recovery.py`, `test_llm_retry.py`, and `test_property_context.py`. Run `uv run --locked --no-sync python .github/scripts/validate_structure.py`, `uv run --locked --no-sync python .github/scripts/validate_run_loop.py`, `git diff --check`, syntax parsing and owned active Markdown links/registered TOML validation. Record every exit; stop the current batch at first failure, preserve it and repair before stable rerun. Hosted CI is NOT_RUN without a push; do not claim it from local equivalents. Test that retired contracts cannot be imported/accepted and that the real loop consumer uses the new API while device/model calls remain mocks. The existing test_network_recovery.py ephemeral 127.0.0.1 loopback HTTP fixture with its mocked run callback is explicitly permitted. No real run_loop __main__, operational server bind, remote device connection, cameras or measurements. SDK construction is confined to the explicitly bound synthetic smoke.

### Phase 3: Durable Contract Promotion
1. STEP 1: Durable Contract Promotion
```harness-step-json
{"phase": 3, "step": 1, "expected_commit_msg": "docs Durable Contract Promotion", "prompt": "steps/PHASE_3_STEP_1_PROMPT.md"}
```

Literal ownership and validation: [steps/PHASE_3_STEP_1_PROMPT.md](steps/PHASE_3_STEP_1_PROMPT.md).
- `docs/mas/python-runtime.md`

Only after both product steps have actual independent QA PASS and verified native Git publication, inspect their accepted snapshots, actual tests and remaining risks. Fresh independent harness-qa must accept the entire integrated source/cleanup/output contract and the proposed DCP outcome. Controller selects exactly PROMOTED with genuinely changed docs/mas/python-runtime.md and absent dcp_reason, or independently accepted NO_DURABLE_CHANGE with files=[] and a present trimmed nonempty dcp_reason. Ordinary no-change cannot complete this step. No legacy checkpoint is rewritten as completed. No shared/personal memory change or hardware/live integration acceptance is inferred.

If a genuine reusable product clarification is needed, only the verified Writer receives an explicit narrow docs/mas/python-runtime.md handoff; otherwise no Writer ownership is created. Preserve accepted implementation and executable evidence; documentation-only clarification gets link/diff checks plus independent final QA and can reuse sufficient unchanged executable evidence. Controller stages only actual exact outcome/receipt files, verifies membership, commits `YYMMDD-HH-MM docs Durable Contract Promotion` with ordinary Git, and verifies actual HEAD/paths/bytes/index. This manual exception has no manager-owned progress ledger or fingerprint to simulate. Failed publication keeps DCP pending, preserves original index/external state and reports the failure; no destructive reset/stash/rollback. Mark Goal complete only after required implementation, cleanup, independent QA, Git and DCP actually finish.


## Bounded actual SDK connection verification

After the stable complete mocked tests and before final independent acceptance, execute one bounded isolated actual pinned SDK smoke with exclusively synthetic condition/measurement fixtures and mocked robot transport, from a fresh temporary workspace. It must exercise the new Python public entrypoint, bootstrap/observation boundary, native author/QA and design/QA evidence, persistent Main resume/reconsideration and stored output/Git. No private experiment rows/raw media are sent, no live device/network client is enabled, no physical command is dispatched, and scientific agents never start nested SDKs. The controller predeclares the exact command, fixture paths/content, <=1200 seconds per bounded invocation and first-failure stopping. No broad benchmark, repeated same-condition scientific evaluation or silent rerun; a real defect requires preserved failure, bounded repair/QA and an affected smoke rerun. Inaccessible actual SDK/auth/network support is NOT_RUN/blocked live evidence, never mocked PASS or automatic setup/installation. No SDK/model setting override or secret inspection. The existing Codex service is the sole authorized model destination for this necessary product-connection validation. This exception permits only Controller/Writer's explicitly bound smoke harness, not arbitrary live scripts. Any live smoke that cannot be performed must remain an explicit limitation, assessed by independent QA against production-readiness claims.

Planning P2 initial findings were repaired before acceptance: exact guidance/predecessor locators, read-only Git permission, Step2 runtime/doc ownership and explicit pending live-smoke binding. Earlier raw findings remain in native reader records; no product acceptance is claimed.
