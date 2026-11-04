# Phase 2 Step 1 — Integrate adaptive execution and retire MAS compatibility paths

```harness-step-json
{"phase": 2, "step": 1, "expected_commit_msg": "feat integrate adaptive MAS and remove superseded paths", "prompt": "steps/PHASE_2_STEP_1_PROMPT.md"}
```

## Mission
Integrate adaptive execution and retire MAS compatibility paths. One verified Writer owns this contract unit; Controller owns lifecycle transitions.

## Protocol
Human message 01a1a72e-874a-7a40-b00d-93e849c87cf7 in Controller chat 01a19fab-662c-7512-932e-29a933aa8ea2 explicitly authorizes a new Python MAS execution architecture, implementation, MAS legacy cleanup and Goal execution.

You are the existing independent persistent top-level Writer. Verify the actual human approval and your identity before acting. Product ownership begins only with a separate explicit Controller handoff; this prompt alone grants none. You are not alone in the codebase: preserve others' edits and request a bounded ownership extension before touching an unlisted path. Read live AGENTS, this Harness README/REQUIREMENTS/plan and pinned external harness-runtime, relevant Python/test guidance, Karpathy simplicity and QA learning/timing. Use existing unittest style; FastAPI/database/frontend scaffolds are NOT applicable. All artifacts English.

Instruction precedence is SYSTEM_DEVELOPER_TOOL > USER_OBJECTIVE_ACCEPTANCE_AUTHORIZATION > TASK_CONTEXT_EXAMPLES_STYLE > OPTIONAL_ENHANCEMENTS; lower_priority_overrides=false; unresolved_execution_conflict=STOP_AND_REPORT.

No canonical manager/progress/fingerprint, stage/commit/branch/remote, shared-source/pin, global config, personal-memory, device/hardware, physical experiment, unbound live SDK/model call or dependency installation. Native Git in tests is only inside fresh temporary repositories. Controller alone mutates source Git and planning/status records. Scratch evidence may be created only under /private/tmp/nips-mas-python-runtime-20261104-review/ with new step-specific filenames; preserve prior evidence. Use UV_NO_CACHE=1 UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp with uv run --locked --no-sync commands. Source and acceptance identities must be recorded with raw command/stdout/stderr/terminal exit evidence. No claimed PASS from partial or mocked scientific prose.

Required input locators: this Harness is harnessing/2026-11-04-mas-python-runtime; read its README.md, REQUIREMENTS.md, EXTERNAL_SOURCE.json, IMPLEMENTATION_PLAN.md and plan.json. Bind NIPS_SHARED_AGENT_ROOT=/Users/junhyeong/research/junhyeong-custom-agent-setting for this task, governor bd6baf99cd8af963b2d8f9077dc2ca690081aada and manager blob234feb7903ee08570311841c60f7be268d21f6be, without changing the external checkout. Required guidance there is skills/harness-runtime/SKILL.md, skills/harness-runtime/references/qa-learning.md, skills/lint-tester/references/validation-timing.md, skills/pytest-expert/SKILL.md (test integrity only; existing unittest and the locked environment take precedence over generic framework/setup examples), and skills/harness-qa/resources/references/{repository-style-qa.md,karpathy-quality-gate.md}. The existing project AGENTS.md and scientific docs/mas/{workflow.md,data-contract.md,knowledge.md,analysis-methods.md} are the product contracts; the current user approval expands their old production-migration exclusion for this implementation. Use source examples src/pipeline/run_loop.py, src/pipeline/url_29.py and tests/test_dynamic_routing.py for local style and integration boundaries. No FastAPI/database/frontend scaffold is required.

Writer may run read-only git status/rev-parse/diff/diff --check and content hashing to record actual HEAD, index, owned diff and source preservation. Writer owns raw command/terminal evidence and its step-specific handoff; Controller binds the actual handoff HEAD/planning snapshot and owns source staging/commit/branch/status-record mutations and acceptance identities. Read-only Git inspection grants no source Git mutation authority. Before implementation, the separate Controller handoff must name the actual current HEAD, seven foundation or current integration literal paths, accepted predecessor evidence and live-smoke binding if applicable.

Literal product ownership (tracked deletions explicitly permitted where required):
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

## Workflow
Read Phase1Step1's independently accepted src/pipeline/mas_runtime.py, mas_workspace.py and mas_contract.py, docs/mas/python-runtime.md and /private/tmp/nips-mas-python-runtime-20261104-review/step1-writer-handoff.md; the separate Controller handoff must supply its actual source commit and independent QA report. If any predecessor is absent/unaccepted, return PENDING without implementation. Replace run_loop's dynamic route with that runtime and provide an intentional, documented reconsideration path. Preserve existing measured-result processing, operator values/default mode, stock validator behavior, exact reviewed point and durable request/journal/checkpoint identity. Test initial and continuing campaigns, RUN/HOLD/STOP, same-session recovery, meaningful explicit HOLD reconsideration and ambiguous/acknowledged submissions. Do not erase QA/checkpoint markers or reissue an already submitted experiment to enable reconsideration.

Remove the four old MAS modules, old fixed-report test_mas.py, old pilot script/test and compatibility-only experiment-analysis-qa binding/docs. Update imports, test fixtures, CI, all owned active docs/roles to the actual new API and the five kept registered specialist roles; keep optional analyst under unified hypothesis-qa. Preserve shared CSV columns and non-MAS routes. Keep pilot-evaluation.md only as a clearly historical evaluation boundary with working current entrypoint references; no stale runnable example. Preserve historical Harness files and removed code in Git, without a copied archive or forwarding shim. Keep root README concise and use docs/mas/python-runtime.md as the detailed owner. If a new required consumer path is unowned, return it for bounded replan rather than quietly editing.

On the stable final integrated candidate, run each exact complete safe suite (not only focused cases): `uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_runtime.py'`; same command with `test_mas_contract.py`, `test_mas_workspace.py`, `test_dynamic_routing.py`, `test_warm_start.py`, `test_network_recovery.py`, `test_llm_retry.py`, and `test_property_context.py`. Run `uv run --locked --no-sync python .github/scripts/validate_structure.py`, `uv run --locked --no-sync python .github/scripts/validate_run_loop.py`, `git diff --check`, syntax parsing and owned active Markdown links/registered TOML validation. Record every exit; stop the current batch at first failure, preserve it and repair before stable rerun. Hosted CI is NOT_RUN without a push; do not claim it from local equivalents. Test that retired contracts cannot be imported/accepted and that the real loop consumer uses the new API while device/model calls remain mocks. The existing test_network_recovery.py ephemeral 127.0.0.1 loopback HTTP fixture with its mocked run callback is explicitly permitted. No real run_loop __main__, operational server bind, remote device connection, cameras or measurements. SDK construction is confined to the explicitly bound synthetic smoke below.


## Bounded actual SDK connection verification

After the stable complete mocked tests and before final independent acceptance, execute one bounded isolated actual pinned SDK smoke with exclusively synthetic condition/measurement fixtures and mocked robot transport, from a fresh temporary workspace. It must exercise the new Python public entrypoint, bootstrap/observation boundary, native author/QA and design/QA evidence, persistent Main resume/reconsideration and stored output/Git. No private experiment rows/raw media are sent, no live device/network client is enabled, no physical command is dispatched, and scientific agents never start nested SDKs. The controller predeclares the exact command, fixture paths/content, <=1200 seconds per bounded invocation and first-failure stopping. Until that concrete binding arrives, complete independent offline implementation/validation work, then return LIVE_SMOKE_PENDING / QUIESCENT with no live SDK invocation; do not invent a command or label the smoke passed. No broad benchmark, repeated same-condition scientific evaluation or silent rerun; a real defect requires preserved failure, bounded repair/QA and an affected smoke rerun. Inaccessible actual SDK/auth/network support is NOT_RUN/blocked live evidence, never mocked PASS or automatic setup/installation. No SDK/model setting override or secret inspection. The existing Codex service is the sole authorized model destination for this necessary product-connection validation. This exception permits only Controller/Writer's explicitly bound smoke harness, not arbitrary live scripts. Any live smoke that cannot be performed must remain an explicit limitation, assessed by independent QA against production-readiness claims.

## Quality Control
All changed lines must map to the current contract. Exact source/test/config/doc and active dependency surfaces must be synchronized, no fixed-stage legacy reintroduction, no fabricated QA or test evidence, no conditions drift or original measurement mutation. QA1/repair1/QA2/repair2/QA3 is the external formal strategy; QA3 FAIL returns to Controller replan, never a QA4. Writer validation is not independent acceptance. Keep original failures and perform a bounded same-pattern sweep. Return exact actual changed paths, raw validation, source identities and the following ordinary-step payload schema (replace explanatory content with actual facts; DCP uses its normalized outcome shape instead):

```json
{
  "phase": 2,
  "step": 1,
  "commit_msg": "feat integrate adaptive MAS and remove superseded paths",
  "commit_content": "Describe actual accepted changes and validation, without overstating live or scientific coverage.",
  "files": [
    "src/pipeline/mas_contract.py",
    "src/pipeline/mas_workspace.py",
    "src/pipeline/mas_runtime.py",
    "tests/test_mas_contract.py",
    "tests/test_mas_workspace.py",
    "tests/test_mas_runtime.py",
    "docs/mas/python-runtime.md",
    "src/pipeline/run_loop.py",
    "src/pipeline/codex_context.py",
    "src/pipeline/mas_records.py",
    "src/pipeline/mas_schema.py",
    "src/pipeline/mas_analysis.py",
    "scripts/mas_agent_pilot.py",
    "tests/test_mas.py",
    "tests/test_mas_agent_pilot.py",
    "tests/test_dynamic_routing.py",
    ".github/workflows/ci.yml",
    "AGENTS.md",
    "README.md",
    "docs/mas/README.md",
    "docs/mas/workflow.md",
    "docs/mas/data-contract.md",
    "docs/mas/knowledge.md",
    "docs/mas/analysis-methods.md",
    "docs/mas/pilot-evaluation.md",
    "subagents/campaign-main/AGENTS.md",
    "subagents/campaign-main/docs/campaign-guide.md",
    ".codex/agents/experiment-analyst.toml",
    "subagents/experiment-analyst/AGENTS.md",
    "subagents/experiment-analyst/docs/analysis-guide.md",
    ".codex/agents/hypothesis-updater.toml",
    "subagents/hypothesis-updater/AGENTS.md",
    "subagents/hypothesis-updater/docs/hypothesis-guide.md",
    ".codex/agents/hypothesis-qa.toml",
    "subagents/hypothesis-qa/AGENTS.md",
    "subagents/hypothesis-qa/docs/review-checklist.md",
    ".codex/agents/experiment-designer.toml",
    "subagents/experiment-designer/AGENTS.md",
    "subagents/experiment-designer/docs/design-guide.md",
    ".codex/agents/experiment-design-qa.toml",
    "subagents/experiment-design-qa/AGENTS.md",
    "subagents/experiment-design-qa/docs/review-checklist.md",
    ".codex/agents/experiment-analysis-qa.toml",
    "subagents/experiment-analysis-qa/AGENTS.md",
    "subagents/experiment-analysis-qa/docs/review-checklist.md"
  ]
}
```

## Documentation Update Assessment
- Needed: yes; synchronize owned runtime docs and semantic docstrings.
- Target files: only the explicit ownership list.
- Reason: current executable contracts must be readable and truthful.

## Short-memory Update
- Updated: no.
- Files: none.
- Reason: Controller task-local status suffices; no memory write authority.

## Long-memory Promotion Candidate
- Needed: assess actual accepted findings; do not manufacture a lesson.
- Trigger: none until supported by actual evidence.
- Observed evidence: actual command/finding paths or none.
- Pattern family: actual pattern or none.
- Recurrence rationale: justified threshold or none.
- Applicability: this runtime/consumer boundary or none.
- Negative boundaries: no scientific or hardware confirmation.
- Proposed durable guidance or gate: existing-rule correction, product regression, or candidate only.
- Proposed canonical owner: repository runtime docs or none.
- Excluded material: raw transcripts, secrets, credentials, temporary IDs, local scratch paths and one-off logs.
- Promotion status: CANDIDATE_ONLY or none; not promotion.
- Repository durable update gate: Controller review, user approval and mandatory-last DCP.
- Codex user-memory update gate: separate explicit user request.

## Contract Update Assessment
- Candidate type: runtime, docs, AGENTS, tests as applicable.
- Target role: runtime owner or scientific Main.
- Target files: only literal owned paths.
- Rationale: synchronize executable boundaries and truthful documentation.

## Main-agent Follow-up Required
- Actions: fresh independent QA, bounded repair if required, exact native Git publication and final DCP. Return QUIESCENT / OWNERSHIP_RETURNED with no source Git mutation.
