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
- `tests/test_llm_retry.py`
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

Phase2 bounded extension after returned Writer ownership: align only the existing
required tests/test_llm_retry.py transport fixtures with the unchanged locked
OpenAI/httpx2 interface. No dependency/production change or weakened assertions.
Retain sufficient unchanged stable3 evidence, complete the repaired retry suite
and recheck scope/static identities before the already required live smoke/QA.

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


## Append-only continuation: Main Jinja template and MAS progress logging

Human approval 01a1a8aa-5897-7972-b09c-81cbbddf27cc authorizes these two improvements and tests. Actual prior DCP HEAD523927ff6e3bebf95762887782ea02f855508c10/sole-path parity and clean index verified before append. STANDARD_CONTROLLER_WRITER and manualGit remain; no new Goal is inferred. Predecessor sufficiency PROCEED/VERIFIED_PREDECESSOR: current source + completed independent QA/native source publication are verified; post-app-restart synthetic SDK result a4bab069b1dc6314db26b0aad252665369b73693 is historical live input only. Existing phases1-3/prompt bytes remain historical; only appended Phase5 is newest active DCP.

### Phase 4: Extract Main template and expose MAS progress
1. STEP 1: Extract Main template and expose MAS progress
```harness-step-json
{"phase":4,"step":1,"expected_commit_msg":"feat extract MAS prompt and add progress logs","prompt":"steps/PHASE_4_STEP_1_PROMPT.md"}
```
Literal eight product paths, bounded necessary Jinja/MarkupSafe uv addition/install, exact predecessor prompt parity, cache-vs-connection/publication/decision/error logs, all eight full safe suites/two validators and preservation are in [Phase4 prompt](steps/PHASE_4_STEP_1_PROMPT.md). Current full4-case prompt oracle was captured before product changes. Source and scientific/physical routing stay unchanged. No model/device call. Fresh exact-byte runbook P2 and full-diff independent QA precede manual exact-file source publication.

### Phase 5: Durable Contract Promotion
1. STEP 1: Durable Contract Promotion
```harness-step-json
{"phase":5,"step":1,"expected_commit_msg":"docs Durable Contract Promotion","prompt":"steps/PHASE_5_STEP_1_PROMPT.md"}
```
Only after Phase4 accepted native publication: fresh independent whole-outcome QA selects normalized PROMOTED or NO_DURABLE_CHANGE. Conditional product docs/mas/python-runtime.md only, or no Writer ownership. Controller sole status receipt/native Git verification follows [Phase5 prompt](steps/PHASE_5_STEP_1_PROMPT.md). No historical DCP relabeling or personal/shared memory update.


## Append-only continuation: Repository-contained MAS results and project-local Codex state

Human message01a1a9ed-d122-76e1-b1a9-8709d2c7acf5 approves the discussed data layout, SDK CODEX_HOME at dynamically resolved repository root, tests and a new Goal. Actual completed Phase5 HEAD094af01d1eeddec469fd801a6e8552078af7e8ed/sole-status native Git parity and clean index were verified before append. Preserve phases1-5/old prompts/history; only appended Phase7 is the newest active DCP. Same verified Controller and independent persistent Writer, ordinary explicit-file Git, pinned external skills; no manager/progress/fingerprint. Product mutation requires a new literal Writer grant after fresh independent planning/P2 acceptance. Source measurements, operator settings, legacy modes and prior SDK evidence remain preserved.

### Phase 6: Integrate MAS storage and project-local SDK state
1. STEP 1: Integrate MAS storage and project-local SDK state
```harness-step-json
{"phase":6,"step":1,"expected_commit_msg":"feat integrate MAS storage into project repository","prompt":"steps/PHASE_6_STEP_1_PROMPT.md"}
```
Exact product scope and acceptance are in [Phase6 prompt](steps/PHASE_6_STEP_1_PROMPT.md). Replace the independent-output assumption with data/knowledge/<material>, existing data/results/begins_<campaign>/mas rounds/state and narrowly scoped existing-repository publication. Stable campaign checkpoints are versioned without self-referential hashes; transient journals/locks are excluded. Preserve unrelated changes and source/data integrity, native collaboration/review/bootstrap/reveal and exact physical submission guards. Derive source/input paths portably; do not silently migrate old external/native state. Give only the SDK child repository-root CODEX_HOME; protect source/host/native state while agents write their attempt. Preserve actual derived artifacts and truthful progress/CLI channels. Require fresh meaningful regression/full8suite/two-validator/static/preservation evidence. After stable offline results and returned Writer ownership, bind actual synthetic SDK/auth validation in a new temporary repo, then fresh complete independent product/P2 QA and exact-file native publication. Credentials are not copied or exposed; browser authentication may require human action. First failure stops the bound invocation and remains non-PASS until addressed under explicit scope.

### Phase 7: Durable Contract Promotion
1. STEP 1: Durable Contract Promotion
```harness-step-json
{"phase":7,"step":1,"expected_commit_msg":"docs Durable Contract Promotion","prompt":"steps/PHASE_7_STEP_1_PROMPT.md"}
```
Only after accepted Phase6 native publication and actual validation disposition: fresh independent whole-outcome QA judges the final normalized PROMOTED or NO_DURABLE_CHANGE. Conditional product ownership is docs/mas/python-runtime.md only for a genuine promoted clarification; otherwise no Writer product ownership. Controller owns the factual status receipt and exact staged/committed byte/path/parent verification. See [Phase7 prompt](steps/PHASE_7_STEP_1_PROMPT.md). No new shared/personal-memory action or physical/hosted-CI claim. Mark the Goal complete only when every required objective gate is actually satisfied.

Phase7 final receipt ordering: Controller drafts and freezes the exact outcome/receipt before fresh QA. After terminal PASS only the exact five-field QA-identity prepend in the atomic prompt is permitted, Controller-verified against the real report/freeze. All other changes invalidate acceptance. Exact staged/committed path/blob/parent/subject/index and command exits provide actual terminal publication proof before Goal completion.


## Phase6 Controller replan: strategy2 publication preservation

Strategy1 ended at terminal QA3 FAIL (report f9af4d1505ebbe051010c1a7bc3c924c5dcfc70529b62a27bb703a8b9004b8b0). The original goal,17-path ceiling, Phase6 expected commit/requirements and mandatory-last Phase7 remain. Active strategy2 is the final section of [Phase6 prompt](steps/PHASE_6_STEP_1_PROMPT.md), superseding blind target/index replacement and single entry-frontier checking. Discovery/21 small-model cases are feasibility only; full cold closure/normal successor/shared-bank/clone handling must be implemented/tested. Fresh independent planning/P2 review precedes a separate seven-path persistent Writer grant. New whole-change review numbering starts at strategy2 QA1; there is no strategy1 QA4. Actual authentication/native gate remains pending and no source publication/Goal completion is authorized by planning.

Strategy2 QA1 then rejected the cached caller's missing pending-publication gate.
Bounded repair1 uses only src/pipeline/run_loop.py and tests/test_dynamic_routing.py,
inside the original17; the other15 remain fixed. This explicitly supersedes the
former initial seven-path grant's run_loop freeze for this repair only. Preserve
Workspace/Runtime recovery; reject unresolved pending under receipt verification
before cached success or dispatch. Require public initial/callback regressions,
normal/resolved controls, affected complete suites and fresh whole-change QA2.
The final Phase6 amendment governs the literal later handoff; it is not itself
a grant. Original user approval/requirements/Step identity and Phase7 are unchanged.

Strategy2 QA2 rejected later-publication cold reconstruction: restoring the old
scientific before-state also restores its old local transaction token, then pairs
it with the new pending intent. Bounded repair2 assigns only mas_workspace.py and
test_dynamic_routing.py inside the original17; all other15, including the fixed
caller guard, stay exact. Preserve strict pointer validation and known publication;
reconstruct the verified current identity coherently, with repeated cold-open and
direct Runtime/caller-first recovery regressions. Complete Workspace/Runtime/
Dynamic/Warm are invalidated; assess other four suites explicitly. The final
Phase6 amendment requires fresh prompt readability and a subsequent literal
grant. Fresh whole-change QA3 is last in strategy2; FAIL requires Controller
adjudication, not QA4. No new objective, strategy, Step, schema, authority or
acceptance relaxation; native/auth/publication/mandatory-last Phase7 stay pending.


## Phase6 Controller adjudication: strategy3 native-name completeness

Strategy2 terminal QA3 FAIL is retained in strategy2-product-qa3-root-native-supplement/.
Basic actual-root login/model/same-thread restart passed; full MAS remains unrun.
Latest human root-test scope supersedes temp-only location. The final Phase6 prompt
now bounds a three-file persistent Writer repair for two actual native names,
root-only ignore/input/context/profile regressions with nested-data controls,
four invalidated full suites, retained-input assessment and fresh planning/P2/QA.
No new Step, objective, product ceiling or Git strategy. Actual root native files
remain unread/unhashed/unchanged. Controller binds synthetic-only real-root MAS
and scoped Git cleanup before execution; source publication and Phase7 stay pending.

Planning QA1 FAIL retained (report2987b7fdd8bf36be5889a920581d734f78f837f9569e4a910c4859dcca13b48e).
Repair1 binds unchanged structure-validator execution to an explicit Git-tracked
Python-source/directory projection; direct recursive CODEX_HOME invocation is
forbidden. Unchanged run-loop validator reads only its explicit source. Three-file
product scope and other gates stay unchanged; fresh prompt/P2 and planning QA2
precede any Writer mutation grant.


Strategy3 QA1 actual native FAIL requires bounded repair1 in mas_runtime.py and
test_mas_runtime.py only; other15 fixed. Wildcard native-directory roots did not
protect descendants. Root no-model pinned native calibration confirms recursive
coverage is required and a matching recursive input deny cannot be overridden;
current-campaign complement patterns preserve the input exception. Fresh P2/
planning review precedes separate two-file grant on the authorized test-only
bootstrap HEADb0f5; original feature base94/rawindex remain for later scoped
restoration preserving the updated code. Full four suites/freshQA2/realSDKcanary
and remaining protocol must pass; no scientific result reveal occurred yet.


Repair1 first return is incomplete: focused3 PASS, actual emitted-profile native
parser65 before probe, fullfour/validators NOT_RUN. Root isolation confirms a
100-character single-profile representation issue; bounded4-alternative groups
pass71 prototype cases, unlike one long union or450 separate rules. Same repair1
completion keeps two-file scope and requires fresh P2/planning then a separate
handoff. Actual calibration uses three separate unmodified emitted profiles,
followed by all required full gates; no old failure or prototype is acceptance.
