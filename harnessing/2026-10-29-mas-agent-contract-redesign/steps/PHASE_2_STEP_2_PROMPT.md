# Phase 2 Step 2 — Design hypothesis updater and hypothesis QA contracts

```harness-step-json
{
  "phase": 2,
  "step": 2,
  "expected_commit_msg": "docs design hypothesis reasoning agent pair",
  "prompt": "steps/PHASE_2_STEP_2_PROMPT.md"
}
```

## Mission

Executor: the verified independent persistent Writer in the selected STANDARD_CONTROLLER_WRITER Worktree.
Outcome: Make hypothesis maintenance an evidence-driven reasoning task.
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
- `subagents/hypothesis-updater/AGENTS.md`
- `subagents/hypothesis-updater/docs/hypothesis-guide.md`
- `subagents/hypothesis-qa/AGENTS.md`
- `subagents/hypothesis-qa/docs/review-checklist.md`

Use uv for Python. The user selected MANUAL_GIT_TRANSITIONS: ordinary commits by controller, no automatic manager execution or canonical fingerprints/ledger. Retain external planning/ownership/independent QA/DCP guidance. Resolve harness-runtime/harness-qa through NIPS_SHARED_AGENT_ROOT and verify the pinned source. Use code-agent-builder only as a role-content reference; do not install its unrelated scaffold.
Respect the current user-authorized objective and this literal scope. Report material unresolved conflicts to controller. Existing uncommitted work in these paths is source context to inspect and revise only after ownership is explicitly transferred; preserve all other bytes.
Do not modify measured CSVs, operator settings, legacy modes, production adapter/loop, server/robot clients, shared source, submodules or personal memory. Do not execute devices. No unreviewed Git lifecycle or remote action.
Writer never edits EXECUTION_STATUS.md/progress.json, runs the manager, picks a transaction fingerprint, stages or commits. Independent QA never repairs the candidate.

## Workflow

1. Verify the current step, ownership, external source and dependency evidence. Do not infer activation from these planning files.
2. Inspect the closest live source and relevant shared/domain instructions.
3. Define observation versus explanation, falsifiable predictions and competing explanations with worked examples. Explain when to retain, refine, split, add, support, refute, or leave a hypothesis inconclusive. Preserve claim identity and explain meaning-changing revisions; do not silently rewrite history or force a new hypothesis each round.

Describe evidence strength, contradictory observations and what would change a conclusion. Keep the full hypothesis history navigable without a mandatory generic result.json. Performance improvement alone is not support; failure to improve alone is not refutation. Main chooses the next hypothesis after hypothesis QA.

QA checks the inference from observations, plausible alternatives and discriminability using source evidence, and returns actionable findings. Define when to return to analysis rather than manufacture an explanation.
4. Check the whole affected contract for the same failure mechanism when a defect is found; return grouped findings and owned repairs.
5. Run the applicable checks below, record actual results, and return the proposed payload for controller review.

Validation:
- `git diff --check`
- Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
Do not make live model calls in this step.

## Quality Control

A worked case demonstrates unchanged, supported/refuted and inconclusive outcomes, and main can select a test without the updater silently selecting execution conditions.
Fresh independent development QA reviews the complete changed contract surface, not only the reported focus. Review scientific utility and truthful implementation status as well as format. Ordinary limitations may remain explicit; unresolved blocking findings prevent advancement.
No claim of current production support from target docs, no invented measurements/QA, and no future-performance guarantee from a recommended point. Return raw commands, observed exits, source/artifact locations and the remaining uncertainty.
Missing ownership or additional required changes go through controller scope/replanning before a later step; no silent widening.

Proposed completion payload, only after actual work and QA:
```json
{
  "phase": 2,
  "step": 2,
  "commit_msg": "docs design hypothesis reasoning agent pair",
  "commit_content": "Make hypothesis maintenance an evidence-driven reasoning task.",
  "files": [
    "subagents/hypothesis-updater/AGENTS.md",
    "subagents/hypothesis-updater/docs/hypothesis-guide.md",
    "subagents/hypothesis-qa/AGENTS.md",
    "subagents/hypothesis-qa/docs/review-checklist.md"
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

