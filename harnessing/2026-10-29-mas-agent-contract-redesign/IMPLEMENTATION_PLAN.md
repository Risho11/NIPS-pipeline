# MAS Agent Contracts and Real-Data Pilot

## Objective and status

Design useful operating contracts for the experiment main and its six specialist/QA roles, then evaluate next-point selection on existing evidence with a minimal isolated SDK pilot.
This is a docs-first plan, not an implementation-complete claim. The user authorized Goal execution on 2026-10-30. The independent persistent Writer has completed identity/authority preflight. The user selected ordinary Git commits rather than the automatic manager. MANUAL_GIT_TRANSITIONS retains the eight-step scope, ownership, independent QA and final DCP. Product execution begins only through a literal handoff; no production integration is included.

## Sources and authority

Read REQUIREMENTS.md, README.md and EXTERNAL_SOURCE.json in this workspace.
Use the pinned external harness-runtime and harness-qa skills; code-agent-builder is a reference for role-content design only, not authority to bootstrap its entire scaffold.
STANDARD_CONTROLLER_WRITER is user-selected. Controller owns planning and advancement; a verified independent persistent top-level Writer in the same Worktree owns exactly the current product step. A read-only reviewer is not a Writer. No implicit fork or inherited mutation authority.
No submodule, source-checkout edits, extra global hooks, robot work, GitHub lifecycle work or blanket worktree commit.
Preserve original measurements/operator settings, legacy modes and pre-existing uncommitted product files. The controller uses native Git with exact explicit-file staging and post-commit verification; do not run the canonical manager or simulate progress.json/fingerprints.
No predecessor implementation/test PASS supplies acceptance. FRESH_START applies to this initial governed planning objective; reassess live readiness before execution.

## Contract inventory

| Contract | Existing evidence | Owned future surface |
| --- | --- | --- |
| User inquiry/autonomy and records | current user requirements in REQUIREMENTS.md | main AGENTS/guide and workflow.md |
| Measurements and provenance | curve_segmentation.py, property_context.py, llm_context.py, actual llm/agg/reps and warm-start headers | data-contract.md, analysis-methods.md |
| Feasible conditions/operator authority | polymer_additive_bounds.py, activeLearning_29.py current_ranges, run_loop.py settings | domain docs; isolated pilot constraints |
| Analysis and original-evidence QA | subagents/experiment-analyst and experiment-analysis-qa | their literal AGENTS/docs below |
| Hypothesis maintenance and QA | subagents/hypothesis-updater and hypothesis-qa | their literal AGENTS/docs below |
| Design and QA | subagents/experiment-designer and experiment-design-qa | their literal AGENTS/docs below |
| SDK role selection and artifact permissions | .codex/agents/*.toml, installed pinned SDK, current read-only adapter limitations | six bindings and an isolated pilot |
| Useful next-point reasoning | existing actual data; current mocked tests are insufficient | explicit pilot method and observed evaluation |
| Production recommendation/submission | codex_context.py, mas_records.py, mas_schema.py, mas_analysis.py, run_loop.py, url_29.py | OUT OF SCOPE: later integration review |

## Design and acceptance priorities

Role AGENTS.md files explain mission, authority and useful actions directly. Docs explain question-led methods, project facts, examples and handoffs. Generic “read docs / return JSON / do not write” instructions are insufficient.
Use shared data knowledge once, meaningful role-specific reasoning, three distinct scientific QA roles, main hypothesis selection and final decision. No static figure roster, forced new hypotheses, report-echo JSON, report-hash gating or native genealogy framework.
Retain four flexible accepted Markdown reports and navigable artifact locations. Permit revisions and upstream returns, with affected judgments re-reviewed. Real-data next-point selection is the useful evaluation; mechanical correctness alone is not.
Target docs must explicitly distinguish the accepted future design from the still-unmigrated production adapter. Any pilot flaw triggers bounded controller repair/replanning before DCP; no automatic acceptance or goal completion.

## Validation boundaries

Planning: canonical plan/prompt identity parity remains useful structural evidence. Execution uses user-selected native Git; no actual-manager preview/fingerprint is required or claimed. Use relevant repository structural validators and git diff --check. No model/device call.
Role steps: original-source/semantic QA, link checks and worked uncertainty/return-path cases; context-isolated readability where independent consumption is promised, separately adjudicated by harness-qa.
Pilot plumbing: uv run --locked python -m unittest discover -s tests -p 'test_mas_agent_pilot.py' with mocked SDK/clients and temporary data only.
Scientific usefulness: real SDK calls on isolated copies of actual data, recorded case limits, original artifacts and independent judgment. Never label mocked events as live QA.
No full legacy suite is required for doc-only changes. The offline pilot guard tests run on a stable candidate; rerun only affected checks after repairs. Future production integration owns its regression suite.
The generic shared full-application documentation skeleton is not adopted; semantic MAS-document review is mandatory instead.

## Execution Plan (Atomic Commits)

### Phase 1: Shared Knowledge and Campaign Direction

1. STEP 1: Establish experiment evidence and inquiry guidance

```harness-step-json
{
  "phase": 1,
  "step": 1,
  "expected_commit_msg": "docs define MAS evidence and inquiry guidance",
  "prompt": "steps/PHASE_1_STEP_1_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Ground scientific decisions in the repository's real data and a usable method-selection guide.
- files: ["docs/mas/data-contract.md","docs/mas/analysis-methods.md"]
- validation: git diff --check; Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
- acceptance: A reader can locate the actual measurement fields and select an analysis based on an uncertainty. Missing provenance stays unknown; the SS processing/agent boundary is explicit.

2. STEP 2: Design the campaign main agent and adaptive workflow

```harness-step-json
{
  "phase": 1,
  "step": 2,
  "expected_commit_msg": "docs design adaptive campaign main agent",
  "prompt": "steps/PHASE_1_STEP_2_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Give one campaign main agent authority to route inquiry and revisit judgments.
- files: ["subagents/campaign-main/AGENTS.md","subagents/campaign-main/docs/campaign-guide.md","docs/mas/workflow.md"]
- validation: git diff --check; Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
- acceptance: Main can follow report/artifact locations, route a design QA finding back to analysis, and explain why the next experiment is justified. Current adapter limitations remain clearly labeled.

### Phase 2: Specialist and Scientific QA Contracts

1. STEP 1: Design analyst and analysis QA operating contracts

```harness-step-json
{
  "phase": 2,
  "step": 1,
  "expected_commit_msg": "docs design experiment analysis agent pair",
  "prompt": "steps/PHASE_2_STEP_1_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Make analysis and independent scientific review actionable.
- files: ["subagents/experiment-analyst/AGENTS.md","subagents/experiment-analyst/docs/analysis-guide.md","subagents/experiment-analysis-qa/AGENTS.md","subagents/experiment-analysis-qa/docs/review-checklist.md"]
- validation: git diff --check; Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
- acceptance: The pair can choose a new graph, find a confounder, request a targeted repair, and agree on a bounded conclusion from original evidence.

2. STEP 2: Design hypothesis updater and hypothesis QA contracts

```harness-step-json
{
  "phase": 2,
  "step": 2,
  "expected_commit_msg": "docs design hypothesis reasoning agent pair",
  "prompt": "steps/PHASE_2_STEP_2_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Make hypothesis maintenance an evidence-driven reasoning task.
- files: ["subagents/hypothesis-updater/AGENTS.md","subagents/hypothesis-updater/docs/hypothesis-guide.md","subagents/hypothesis-qa/AGENTS.md","subagents/hypothesis-qa/docs/review-checklist.md"]
- validation: git diff --check; Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
- acceptance: A worked case demonstrates unchanged, supported/refuted and inconclusive outcomes, and main can select a test without the updater silently selecting execution conditions.

3. STEP 3: Design experiment designer and design QA contracts

```harness-step-json
{
  "phase": 2,
  "step": 3,
  "expected_commit_msg": "docs design hypothesis testing agent pair",
  "prompt": "steps/PHASE_2_STEP_3_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Choose an informative next experiment from a selected hypothesis.
- files: ["subagents/experiment-designer/AGENTS.md","subagents/experiment-designer/docs/design-guide.md","subagents/experiment-design-qa/AGENTS.md","subagents/experiment-design-qa/docs/review-checklist.md"]
- validation: git diff --check; Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
- acceptance: The pair can justify the next point and its purpose, explain alternative outcomes, and identify a design that would not answer the question.

### Phase 3: Isolated Pilot and Scientific Usefulness

1. STEP 1: Prepare an isolated report-only SDK pilot

```harness-step-json
{
  "phase": 3,
  "step": 1,
  "expected_commit_msg": "feat add isolated MAS agent contract pilot",
  "prompt": "steps/PHASE_3_STEP_1_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Provide the smallest way to exercise the accepted agent contracts on actual existing data.
- files: [".codex/agents/experiment-analyst.toml",".codex/agents/experiment-analysis-qa.toml",".codex/agents/hypothesis-updater.toml",".codex/agents/hypothesis-qa.toml",".codex/agents/experiment-designer.toml",".codex/agents/experiment-design-qa.toml","scripts/mas_agent_pilot.py","tests/test_mas_agent_pilot.py","docs/mas/pilot-evaluation.md","subagents/experiment-analyst/AGENTS.md","subagents/experiment-analysis-qa/AGENTS.md","docs/mas/workflow.md"]
- validation: uv run --locked python -m unittest discover -s tests -p 'test_mas_agent_pilot.py'; git diff --check
- scope clarification: Synchronize only the three listed role/workflow descriptions of current bindings when the six TOMLs change; retain the preserved production-adapter boundary. No production code migration.
- acceptance: Offline checks show the pilot preserves originals and cannot submit robot work. The actual SDK pilot remains NOT_RUN until Phase 3 Step 2; binding files match the documents.

2. STEP 2: Evaluate next experiment selection on existing observations

```harness-step-json
{
  "phase": 3,
  "step": 2,
  "expected_commit_msg": "docs evaluate MAS inquiry on existing experiment data",
  "prompt": "steps/PHASE_3_STEP_2_PROMPT.md"
}
```
- owner: verified persistent Writer; independent read-only development QA
- purpose: Judge whether the documented agents can use existing evidence to recommend a defensible next point.
- files: ["harnessing/2026-10-29-mas-agent-contract-redesign/reports/PILOT_EVALUATION.md"]
- validation: uv run --locked python scripts/mas_agent_pilot.py --help; Execute the case-bound command documented and reviewed in docs/mas/pilot-evaluation.md; record the exact actual invocation.; git diff --check
- acceptance: Real model execution and artifact inspection support a clear accept/revise judgment about next-point selection. No mocked outcome is labeled live evidence; untested coverage stays explicit.

### Phase 4: Durable Closeout

1. STEP 1: Durable Contract Promotion

```harness-step-json
{
  "phase": 4,
  "step": 1,
  "expected_commit_msg": "docs Durable Contract Promotion",
  "prompt": "steps/PHASE_4_STEP_1_PROMPT.md"
}
```
- owner: controller / harness-runtime; Writer owns the approved durable evidence
- purpose: Close the reviewed agent-contract work with an honest durable entry point.
- files: ["docs/mas/README.md"]
- validation: git diff --check; Source-to-contract semantic review, relative link checks, and the step's worked cases; record actual paths/results.
- acceptance: Independent acceptance exists; the chosen DCP outcome is correct; the final native Git receipt and actual committed files agree. Production integration remains an explicit separate follow-up.


### Phase 5: Actual explanatory MAS evaluation and repair

1. STEP 1: Exercise the scientific MAS and deliver outputs for review

```harness-step-json
{
  "phase": 5,
  "step": 1,
  "expected_commit_msg": "docs exercise explanatory MAS on historical evidence",
  "prompt": "steps/PHASE_5_STEP_1_PROMPT.md"
}
```
- owner: Controller orchestrates; verified persistent Writer owns literal product-doc repairs; separate scientific main owns temporary research outputs; independent development QA reviews useful behavior.
- purpose: Actual direct-session evaluation, observed-defect repair and re-evaluation, ending in review of scientific outputs rather than agent-doc review.
- scope: Preserve the current 20-document candidate; remove the one-off direct-session test manual and fix its references, retaining reusable guidance. Source project is read-only to science; outputs use /tmp/<test-root>/data/results/<campaign>/mas/rounds and data/knowledge. No Python/production integration or hardware.
- inputs: exact expanded input-scope.json in the transient handoff; PSf/PolarClean warm73 plus October llm58/agg64/reps232 and consequential original sources. Human explicitly approved selective OpenAI transfer and repeated evaluation within that scope on2026-10-31; each run <=1200seconds.
- validation: actual session/event/output inspection, original-source and scientific-QA review, source preservation, meaningful explanatory hypotheses and competing predictions, separate cumulative knowledge, reviewed feasible exact decision; fix and rerun observed material defects.
- acceptance: final native scientific outputs are available for human review with truthful limits; report-only recommendation is never physical execution. A static documentation PASS is insufficient. Retain failed runs and review findings; do not claim all possible scientific behavior tested.
- continuation: user-selected manual-Git append equivalent; old eight steps and historical DCP remain immutable. No canonical-manager command, fake ledger or claim of canonical reopen execution. Existing FOLLOWUP_PLAN.md is retained as historical docs-only attempt, not active execution authority.

2. STEP 2: Durable Contract Promotion — deferred for human review

```harness-step-json
{
  "phase": 5,
  "step": 2,
  "expected_commit_msg": "docs Durable Contract Promotion",
  "prompt": "steps/PHASE_5_STEP_2_PROMPT.md"
}
```
- owner: Controller after later explicit authorization.
- purpose: retain mandatory-last continuation shape without executing DCP before the requested final-output review.
- files: no DCP product ownership is granted now.
- validation/acceptance: NOT_RUN / DEFERRED; not part of this Goal's requested delivery.


### Phase 6: Hypothesis usefulness repair and actual inquiry

Human identified that Phase5 stopped after endpoint repair without sufficient hypothesis improvement. Historical PASS is bounded, not usefulness completion. Resume verified same-Worktree Writer/independent QA and native English inquiry including approved warm/current/raw evidence; index plus per-claim records. Preserve all prior entries. Phase5Step2 remains unexecuted; Phase6Step2 is latest deferred DCP. Manual-Git append, no canonical reopen-append, hardware or production Python.

```harness-step-json
{
  "phase": 6,
  "step": 1,
  "expected_commit_msg": "docs strengthen and exercise MAS hypothesis inquiry",
  "prompt": "steps/PHASE_6_STEP_1_PROMPT.md"
}
```

Ownership/acceptance: [Phase6Step1](steps/PHASE_6_STEP_1_PROMPT.md). New temporary rounds preserve earlier rounds and meanings.

```harness-step-json
{
  "phase": 6,
  "step": 2,
  "expected_commit_msg": "docs Durable Contract Promotion",
  "prompt": "steps/PHASE_6_STEP_2_PROMPT.md"
}
```

DCP deferred until human output review.


### Phase 7: Knowledge-first initialization with open observational revision

Human approved the knowledge-first bank plus observation-driven updates/new hypotheses after finding theory/variable coverage inadequate. Retain one MAS and existing roles, prior12plan entries and historical commits. Existing data-informed claims are retrospective, not pre-observation predictions. Allow scoped public primary-literature work without private-data queries. Actual fresh bootstrap author/QA precedes current-data reveal, then real current/warm/original inquiry; independent development QA and native explicit-file Git. No productionPython/hardware/DCP.

```harness-step-json
{
  "phase": 7,
  "step": 1,
  "expected_commit_msg": "docs initialize knowledge before campaign updates",
  "prompt": "steps/PHASE_7_STEP_1_PROMPT.md"
}
```

Literal ownership, source/permission boundaries and acceptance: [Phase7Step1](steps/PHASE_7_STEP_1_PROMPT.md).

```harness-step-json
{
  "phase": 7,
  "step": 2,
  "expected_commit_msg": "docs Durable Contract Promotion",
  "prompt": "steps/PHASE_7_STEP_2_PROMPT.md"
}
```

Latest DCP checkpoint remains deferred; prior pending DCPs were not executed.

Runtime alignment clarification within Phase7Step1: bounded ownership additionally includes ONLY .codex/agents/hypothesis-updater.toml and .codex/agents/hypothesis-qa.toml because their developer instructions blanket-ban services. Permit scoped authorized public scientific reading while retaining parent permissions and all hardware/other-service/production restrictions. No model/MCP/globalconfig/sandbox/approval settings change or hot-reload guarantee. Validate actual fresh-role capability rather than infer it from edited source.
