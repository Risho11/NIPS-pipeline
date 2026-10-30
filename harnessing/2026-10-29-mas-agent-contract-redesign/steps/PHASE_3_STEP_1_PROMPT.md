# Phase 3 Step 1 — Prepare an isolated report-only SDK pilot

```harness-step-json
{
  "phase": 3,
  "step": 1,
  "expected_commit_msg": "feat add isolated MAS agent contract pilot",
  "prompt": "steps/PHASE_3_STEP_1_PROMPT.md"
}
```

## Mission

Executor: the verified independent persistent Writer in the selected STANDARD_CONTROLLER_WRITER Worktree.
Outcome: Provide the smallest way to exercise the accepted agent contracts on actual existing data.
Read this workspace's REQUIREMENTS.md, IMPLEMENTATION_PLAN.md, README.md, EXECUTION_STATUS.md and EXTERNAL_SOURCE.json before execution. These are reference-guided prompts, not claims that omitted source facts are already known.

## Protocol

```json
{
  "instruction_precedence": [
    "SYSTEM_DEVELOPER_TOOL",
    "USER_OBJECTIVE_ACCEPTANCE_AUTHORIZATION",
    "TASK_CONTEXT_EXAMPLES_STYLE",
    "OPTIONAL_ENHANCEMENTS"
  ],
  "lower_priority_overrides": false,
  "unresolved_execution_conflict": "STOP_AND_REPORT"
}
```

Owned files, literally and exclusively:
- `.codex/agents/experiment-analyst.toml`
- `.codex/agents/experiment-analysis-qa.toml`
- `.codex/agents/hypothesis-updater.toml`
- `.codex/agents/hypothesis-qa.toml`
- `.codex/agents/experiment-designer.toml`
- `.codex/agents/experiment-design-qa.toml`
- `scripts/mas_agent_pilot.py`
- `tests/test_mas_agent_pilot.py`
- `docs/mas/pilot-evaluation.md`
- `subagents/experiment-analyst/AGENTS.md`
- `subagents/experiment-analysis-qa/AGENTS.md`
- `docs/mas/workflow.md`

Use uv for Python. The user selected MANUAL_GIT_TRANSITIONS: ordinary commits by controller, no automatic manager execution or canonical fingerprints/ledger. Retain external planning/ownership/independent QA/DCP guidance. Resolve harness-runtime/harness-qa through NIPS_SHARED_AGENT_ROOT and verify the pinned source. Use code-agent-builder only as a role-content reference; do not install its unrelated scaffold.
Respect the current user-authorized objective and this literal scope. Report material unresolved conflicts to controller. Existing uncommitted work in these paths is source context to inspect and revise only after ownership is explicitly transferred; preserve all other bytes.
Do not modify measured CSVs, operator settings, legacy modes, production adapter/loop, server/robot clients, shared source, submodules or personal memory. Do not execute devices. No unreviewed Git lifecycle or remote action.
Writer never edits EXECUTION_STATUS.md/progress.json, runs the manager, picks a transaction fingerprint, stages or commits. Independent QA never repairs the candidate.

## Workflow

1. Verify the current step, ownership, external source and dependency evidence. Do not infer activation from these planning files.
2. Inspect the closest live source and relevant shared/domain instructions.
3. Inspect the pinned installed Codex SDK before implementing. Update the six domain role bindings to the accepted guides. Synchronize only the three listed role/workflow descriptions of current binding permissions; keep preserved production-adapter restrictions explicit. No production migration; do not generate an unrelated developer-agent scaffold, global hooks, submodule, or copied shared skills.

Add a small report-only pilot entry point that uses one main thread to operate the specialists. Create an isolated scratch workspace containing copies of selected data and the needed role/instruction files, allowing analysis artifacts without granting writes to original evidence or source. Never import/call run_loop, robot clients, or production recommendation export. Do not route through the existing fixed four-request adapter.

Keep Pydantic only for meaningful execution/decision values if needed; avoid a new orchestration framework, native parentage checks, per-report hashes and report-echo protocols. Reports need not be machine-parsed. Expose useful artifact/report locations and record honest agent/QA outcomes.

Document evaluation cases, a bounded model-call budget and run-stop controls, chosen input cutoffs and explicit material/stock context. Defaults are no hardware and no live model call in tests. Mock tests verify original-data isolation, output placement and no submission; they do not prove research quality.
4. Check the whole affected contract for the same failure mechanism when a defect is found; return grouped findings and owned repairs.
5. Run the applicable checks below, record actual results, and return the proposed payload for controller review.

Validation:
- `uv run --locked python -m unittest discover -s tests -p 'test_mas_agent_pilot.py'`
- `git diff --check`
Do not make live model calls in this step.

## Quality Control

Offline checks show the pilot preserves originals and cannot submit robot work. The actual SDK pilot remains NOT_RUN until Phase 3 Step 2; binding files match the documents.
Fresh independent development QA reviews the complete changed contract surface, not only the reported focus. Review scientific utility and truthful implementation status as well as format. Ordinary limitations may remain explicit; unresolved blocking findings prevent advancement.
No claim of current production support from target docs, no invented measurements/QA, and no future-performance guarantee from a recommended point. Return raw commands, observed exits, source/artifact locations and the remaining uncertainty.
Missing ownership or additional required changes go through controller scope/replanning before a later step; no silent widening.

Proposed completion payload, only after actual work and QA:
```json
{
  "phase": 3,
  "step": 1,
  "commit_msg": "feat add isolated MAS agent contract pilot",
  "commit_content": "Provide the smallest way to exercise the accepted agent contracts on actual existing data.",
  "files": [
    ".codex/agents/experiment-analyst.toml",
    ".codex/agents/experiment-analysis-qa.toml",
    ".codex/agents/hypothesis-updater.toml",
    ".codex/agents/hypothesis-qa.toml",
    ".codex/agents/experiment-designer.toml",
    ".codex/agents/experiment-design-qa.toml",
    "scripts/mas_agent_pilot.py",
    "tests/test_mas_agent_pilot.py",
    "docs/mas/pilot-evaluation.md",
    "subagents/experiment-analyst/AGENTS.md",
    "subagents/experiment-analysis-qa/AGENTS.md",
    "docs/mas/workflow.md"
  ]
}
```
This is a proposal, not a result or authorization to run it. The controller makes an ordinary Git commit with the exact reviewed product files and its progress receipt. No canonical progress.json or fingerprint is produced.

## Documentation Update Assessment
- Needed: assess from the actual change.
- Target files: only the literal owned paths, or propose a later bounded step.
- Reason: explain the reusable impact.

## Short-memory Update
- Updated: no unless separately owned and authorized.
- Files: none.
- Reason: return concise transient context; no personal memory changes.

## Long-memory Promotion Candidate
- Needed: assess from observed evidence.
- Trigger: one-highly-consequential-generalizable-preventable-event, repeated-lower-severity-pattern, or none.
- Observed evidence: actual paths/results, or none.
- Pattern family: identify, or none.
- Recurrence rationale: establish, or none.
- Applicability: state bounded contexts, or none.
- Negative boundaries: state exclusions, or none.
- Proposed durable guidance or gate: propose only, or none.
- Proposed canonical owner: role/file, or none.
- Excluded material: raw transcripts, secrets, credentials, temporary IDs, local scratch paths, and one-off logs.
- Promotion status: CANDIDATE_ONLY or none; candidate creation is not promotion.
- Repository durable update gate: controller review, user approval, and DCP.
- Codex user-memory update gate: separate explicit user request.

## Contract Update Assessment
- Candidate type: assess AGENTS/docs/runtime/skill-reference/none.
- Target role: the affected role, or none.
- Target files: literal paths, or none.
- Rationale: explain reusable impact.

## Main-agent Follow-up Required
- Actions: fresh independent QA, controller review, and the proposed payload; never self-advance.
