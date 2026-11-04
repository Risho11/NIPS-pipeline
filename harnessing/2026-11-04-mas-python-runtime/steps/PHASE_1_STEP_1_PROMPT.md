# Phase 1 Step 1 — Implement the adaptive campaign runtime

```harness-step-json
{"phase": 1, "step": 1, "expected_commit_msg": "feat implement adaptive MAS campaign runtime", "prompt": "steps/PHASE_1_STEP_1_PROMPT.md"}
```

## Mission
Implement the adaptive campaign runtime. One verified Writer owns this contract unit; Controller owns lifecycle transitions.

## Protocol
Human message 01a1a72e-874a-7a40-b00d-93e849c87cf7 in Controller chat 01a19fab-662c-7512-932e-29a933aa8ea2 explicitly authorizes a new Python MAS execution architecture, implementation, MAS legacy cleanup and Goal execution.

You are the existing independent persistent top-level Writer. Verify the actual human approval and your identity before acting. Product ownership begins only with a separate explicit Controller handoff; this prompt alone grants none. You are not alone in the codebase: preserve others' edits and request a bounded ownership extension before touching an unlisted path. Read live AGENTS, this Harness README/REQUIREMENTS/plan and pinned external harness-runtime, relevant Python/test guidance, Karpathy simplicity and QA learning/timing. Use existing unittest style; FastAPI/database/frontend scaffolds are NOT applicable. All artifacts English.

Instruction precedence is SYSTEM_DEVELOPER_TOOL > USER_OBJECTIVE_ACCEPTANCE_AUTHORIZATION > TASK_CONTEXT_EXAMPLES_STYLE > OPTIONAL_ENHANCEMENTS; lower_priority_overrides=false; unresolved_execution_conflict=STOP_AND_REPORT.

No canonical manager/progress/fingerprint, stage/commit/branch/remote, shared-source/pin, global config, personal-memory, device/hardware, physical experiment, live SDK/model call or dependency installation. Native Git in tests is only inside fresh temporary repositories. Controller alone mutates source Git and planning/status records. Scratch evidence may be created only under /private/tmp/nips-mas-python-runtime-20261104-review/ with new step-specific filenames; preserve prior evidence. Use UV_NO_CACHE=1 UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp with uv run --locked --no-sync commands. Source and acceptance identities must be recorded with raw command/stdout/stderr/terminal exit evidence. No claimed PASS from partial or mocked scientific prose.

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

## Workflow
Implement the smallest three-module runtime with a report-only command entrypoint in mas_runtime.py and meaningful offline tests; document the actual API/layout. mas_contract owns only finite tunables/operator context, run/hold/stop handoff and operational review/publication receipt data. mas_workspace owns explicit workspace/source binding, independent Git, topic/round paths and durable recovery. mas_runtime owns persistent SDK Main lifecycle and native review/condition validation. Choose a small supported public API, document it and use it in Step2 rather than retain an obsolete adapter shim. The CLI must be import-safe and never submit experiments; explicit workspace/material/campaign binding and reconsideration are operational inputs, not new operator material defaults.

Apply REQUIREMENTS.md across bootstrap, native QA and knowledge/design publication, no report hash/equality gates, writable analysis artifacts, interrupted resume, explicit reconsideration, exact conditions and Main-only publication. Prefer minimal real boundaries over a framework. Inspect installed pinned SDK 0.163.0 public api.py/generated models without starting a client. A mocked client must exercise actual SDK-shaped completion/role metadata; do not validate a fiction that the real SDK cannot supply. Persist thread/round identity before work, preserve failures and publication recovery. Do not invent resource readiness or expose outcome inputs before the initial commit. Reject retired state rather than silently migrate it.

Run `uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_contract.py'`, then the same command with `test_mas_workspace.py` and `test_mas_runtime.py` on a stable candidate; run focused cases during repairs. Also run `git diff --check`, syntax-parse all owned Python without starting SDK/devices, and verify source/data/settings preservation. The declared full Step1 gate is all three complete new contract/workspace/runtime test suites, including genuine negative/restart/Git/native-review boundaries. No blanket pytest discovery: repository test scripts include operational/dev paths and no pytest dependency is configured. No full material fitting suite is needed for this runtime-only step.

## Quality Control
All changed lines must map to the current contract. Exact source/test/config/doc and active dependency surfaces must be synchronized, no fixed-stage legacy reintroduction, no fabricated QA or test evidence, no conditions drift or original measurement mutation. QA1/repair1/QA2/repair2/QA3 is the external formal strategy; QA3 FAIL returns to Controller replan, never a QA4. Writer validation is not independent acceptance. Keep original failures and perform a bounded same-pattern sweep. Write /private/tmp/nips-mas-python-runtime-20261104-review/step1-writer-handoff.md with exact actual changed paths, raw validation, source identities and the following ordinary-step payload schema (replace explanatory content with actual facts; DCP uses its normalized outcome shape instead):

```json
{
  "phase": 1,
  "step": 1,
  "commit_msg": "feat implement adaptive MAS campaign runtime",
  "commit_content": "Describe actual accepted changes and validation, without overstating live or scientific coverage.",
  "files": [
    "src/pipeline/mas_contract.py",
    "src/pipeline/mas_workspace.py",
    "src/pipeline/mas_runtime.py",
    "tests/test_mas_contract.py",
    "tests/test_mas_workspace.py",
    "tests/test_mas_runtime.py",
    "docs/mas/python-runtime.md"
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
