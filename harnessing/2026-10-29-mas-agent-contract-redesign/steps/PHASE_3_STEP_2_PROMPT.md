# Phase 3 Step 2 — Evaluate next experiment selection on existing observations

```harness-step-json
{
  "phase": 3,
  "step": 2,
  "expected_commit_msg": "docs evaluate MAS inquiry on existing experiment data",
  "prompt": "steps/PHASE_3_STEP_2_PROMPT.md"
}
```

## Mission

Executor: the verified independent persistent Writer in the selected STANDARD_CONTROLLER_WRITER Worktree.
Outcome: Judge whether the documented agents can use existing evidence to recommend a defensible next point.
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
- `harnessing/2026-10-29-mas-agent-contract-redesign/reports/PILOT_EVALUATION.md`

Use uv for Python. The user selected MANUAL_GIT_TRANSITIONS: ordinary commits by controller, no automatic manager execution or canonical fingerprints/ledger. Retain external planning/ownership/independent QA/DCP guidance. Resolve harness-runtime/harness-qa through NIPS_SHARED_AGENT_ROOT and verify the pinned source. Use code-agent-builder only as a role-content reference; do not install its unrelated scaffold.
Respect the current user-authorized objective and this literal scope. Report material unresolved conflicts to controller. Existing uncommitted work in these paths is source context to inspect and revise only after ownership is explicitly transferred; preserve all other bytes.
Do not modify measured CSVs, operator settings, legacy modes, production adapter/loop, server/robot clients, shared source, submodules or personal memory. Do not execute devices. No unreviewed Git lifecycle or remote action.
Writer never edits EXECUTION_STATUS.md/progress.json, runs the manager, picks a transaction fingerprint, stages or commits. Independent QA never repairs the candidate.

## Workflow

1. Verify the current step, ownership, external source and dependency evidence. Do not infer activation from these planning files.
2. Inspect the closest live source and relevant shared/domain instructions.
3. Run the reviewed report-only pilot using copies of data/results/begins_2026-10-15/{llm,agg,reps}.csv and/or data/warm_start/polysulfone_polarclean_notebook_filtered_2026-10-15.csv. Choose and record a small bounded case set before model execution: a current-data next-point recommendation; a case with confounding or missing provenance; and one actual QA-follow-up/revision opportunity. Do not fabricate a QA finding if none occurs; record that coverage as missing.

The user subsequently requested repeated actual runs, observed-defect repairs and reruns, and explicitly approved transmitting the specified 37 files and derived results to OpenAI Codex for repeated evaluation. The former automatic-review block is resolved by that explicit human response; remain within the reviewed transfer scope and1200second per-run limit. All scientific prompts, delegation and artifacts must be English. Controller reviews each result and binds any repair to literal paths; this report-only ownership never grants silent edits to source/roles. Preserve each run and its failures, use fresh output directories, and rerun after bounded repair/independent QA until the tested scope has no actionable unresolved defect. Do not turn ordinary uncertainty or untested physical performance into an endless speculative loop.

Judge original-evidence use, question-led analysis/figures, hypothesis changes, the next point's explore/optimize/repeat rationale, comparators/criteria, and QA influence. A feasible novel point alone is insufficient. Do not assert that an unexecuted next point will outperform prior experiments. Optional historical replay must exclude later observations from the inputs and cannot establish performance at an unmeasured point.

Record actual commands, inputs/cutoffs, artifacts, thread references when available, QA findings, main decisions, limitations and NOT_RUN cases. Independent development QA reviews original evidence and generated artifacts. If reasoning fails, controller inserts bounded repair work before DCP; writer may not silently edit prior owned contracts or label a weak recommendation PASS.

No robot invocation, physical experiment, production CSV export, or wide benchmark. This report records evaluation, not automatic production activation.
4. Check the whole affected contract for the same failure mechanism when a defect is found; return grouped findings and owned repairs.
5. Run the applicable checks below, record actual results, and return the proposed payload for controller review.

Validation:
- `uv run --locked python scripts/mas_agent_pilot.py --help`
- Execute the case-bound command documented and reviewed in docs/mas/pilot-evaluation.md; record the exact actual invocation.
- `git diff --check`
This step performs live inference only after the reviewed pilot and its bounded case plan are ready. It never submits physical work.

## Quality Control

Real model execution and artifact inspection support a clear accept/revise judgment about next-point selection. No mocked outcome is labeled live evidence; untested coverage stays explicit.
Fresh independent development QA reviews the complete changed contract surface, not only the reported focus. Review scientific utility and truthful implementation status as well as format. Ordinary limitations may remain explicit; unresolved blocking findings prevent advancement.
No claim of current production support from target docs, no invented measurements/QA, and no future-performance guarantee from a recommended point. Return raw commands, observed exits, source/artifact locations and the remaining uncertainty.
Missing ownership or additional required changes go through controller scope/replanning before a later step; no silent widening.

Proposed completion payload, only after actual work and QA:
```json
{
  "phase": 3,
  "step": 2,
  "commit_msg": "docs evaluate MAS inquiry on existing experiment data",
  "commit_content": "Judge whether the documented agents can use existing evidence to recommend a defensible next point.",
  "files": [
    "harnessing/2026-10-29-mas-agent-contract-redesign/reports/PILOT_EVALUATION.md"
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
