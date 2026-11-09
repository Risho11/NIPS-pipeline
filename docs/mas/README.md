# Experiment MAS

Start here for the scientific agent contracts and shared material/process
knowledge. The revised contracts have received independent development review;
actual MAS testing, observed-defect repair and re-evaluation are now requested.
**Human review will address final scientific outputs before DCP. Revised-contract
live results remain NOT_RUN until actual run evidence is recorded.** The earlier
SDK case below is historical evidence, not validation of these revisions.
The current Python integration is described below; live and physical validation remain separate.

## Scientific inquiry

One persistent [campaign main](../../subagents/campaign-main/AGENTS.md) follows
knowledge initialization, observations, explanations and experiment choices.
By explicit dispatch, the existing hypothesis updater performs integrated analysis
and explanation with unified inquiry QA (`hypothesis-qa`). Main applies concrete
[split/rejoin criteria](workflow.md#when-main-splits-and-rejoins-inquiry) when a
bounded analysis issue needs the analyst; separate stage authors are not a
prerequisite every turn. Both routes combine data science and physical/chemical
reasoning. Main selects the question and publishes accepted knowledge; designer
and distinct design QA assess the informative, feasible test before run/hold/stop.
Follow the workflow's [hypothesis-to-design reasoning](workflow.md#deduce-useful-optimization-and-design)
for optimization and concrete upstream returns. Consider both objectives and
conditional applicability before naming explore/optimize/repeat, without forcing
a new hypothesis, method suite or improved performance.

Use the [workflow](workflow.md) for collaboration and upstream returns, the
[data contract](data-contract.md) for measurements/provenance/constraints, the
[analysis methods](analysis-methods.md) for question-led calculations and figures,
and the [campaign guide](../../subagents/campaign-main/docs/campaign-guide.md)
for routing and decision guidance.

Use [shared knowledge](knowledge.md) to separate canonical material/process
claims and bounded history from each round's evidence update and decision.
Updater drafts; independent QA reviews; main alone accepts/publishes shared
changes through the host in the bound repository. Locate authorized original curves,
photos, params and plots before declaring evidence missing. Keep measurements,
actually read literature and proposed inference distinct; unmeasured morphology
does not become observed merely because a property direction agrees.

One unified inquiry QA uses the existing `hypothesis-qa` ID across these authors.
Additional specialist review is exceptional and uses a fresh instance of that same
role for the workflow's named unresolved issue; adding an analyst does not add QA:

| Author and methods | Distinct reviewer and checks |
|---|---|
| Triggered split: [Experiment analyst](../../subagents/experiment-analyst/AGENTS.md) · [Analysis guide](../../subagents/experiment-analyst/docs/analysis-guide.md) | Unified [Inquiry QA](../../subagents/hypothesis-qa/AGENTS.md) covers analysis and inference across both authors |
| Default integrated inquiry or assigned hypothesis update: [Hypothesis updater](../../subagents/hypothesis-updater/AGENTS.md) · [Hypothesis guide](../../subagents/hypothesis-updater/docs/hypothesis-guide.md) | Unified [Inquiry QA](../../subagents/hypothesis-qa/AGENTS.md) · [Review checklist](../../subagents/hypothesis-qa/docs/review-checklist.md) |
| [Experiment designer](../../subagents/experiment-designer/AGENTS.md) · [Design guide](../../subagents/experiment-designer/docs/design-guide.md) | [Design QA](../../subagents/experiment-design-qa/AGENTS.md) · [Review checklist](../../subagents/experiment-design-qa/docs/review-checklist.md) |

Return material findings through main to the affected author and reviewer;
preserve earlier judgments and re-review dependent conclusions. Keep flexible
Markdown inquiry (or split analysis/update), design and final-decision records without
a report-file quota, and a readable index linking artifacts, revisions, actual
QA findings and unresolved evidence. No fixed figure roster, whole-report JSON echoes,
all-report hash gate or parentage framework is required. Shared knowledge uses
four variable/process-topic documents: `concentration.md`, `prebath_exposure.md`,
`bath_temperature.md` and `bath_residence.md`, with current reasoning, supporting/
contrary evidence, remaining questions and round references. These group inquiry;
they require neither a new hypothesis per update nor a fixed prose layout. Actual
operator batches have summaries and proposed next-batch fixed-setting comparisons;
report-only candidates claim no physical completion. See the
[records convention](workflow.md#records-are-navigable-and-revisable).

Run adopts exactly the scientifically reviewed feasible conditions. Hold names
the missing evidence/review/operator need and a condition for reconsideration;
stop explains why another test is unjustified. Hold and stop supply no executable
conditions. A report-only run recommendation grants no physical execution authority.

## Python execution and evaluated scope

Use the [runtime runbook](python-runtime.md) for the report-only API/CLI and actual
loop binding/reconsideration. Three small owners separate operational types,
existing-repository publication/recovery and persistent native Main/review. Five
specialists are registered; Main is the persistent parent, not a sixth binding.
Legacy fixed-stage modules/pilot and the separate analysis-QA role are retired.

[Historical evaluation](pilot-evaluation.md) remains scoped historical evidence.
Current offline tests mock SDK/device transports; actual SDK/trust/sandbox,
Windows, hosted CI and physical/scientific usefulness need their own evidence.

## Scientific session inputs and outputs

Use the workflow's [source/output bindings](workflow.md#source-and-output-bindings),
[data contract](data-contract.md) for originals and warm-start provenance, and
[knowledge guide](knowledge.md) for shared publication and history. Read approved
project evidence while writing only the current campaign operation's
`data/results/<campaign>/mas/rounds/<operation>/attempt-<n>/`. Shared topics are
`data/knowledge/<material>/`; Python publishes exact Main-adopted records and a
tracked campaign checkpoint through the existing repository Git. Scientific
agents never initialize Git, stage, commit or edit canonical topics/state.
Each campaign/material has its own persistent Main and checkpoint; another
campaign may reuse only the proven shared material bank. Native SDK state/auth
is local and ignored, separate from tracked scientific provenance.
Actual permissions must be checked separately from task instructions. Concrete
session paths, read set, authorization and budget belong in the transient dispatch.

## Development and execution authority

The current [Python implementation Harness](../../harnessing/2026-11-04-mas-python-runtime/README.md)
uses the external pinned shared source, STANDARD_CONTROLLER_WRITER and ordinary
explicit-file Git. The [earlier Harness](../../harnessing/2026-10-29-mas-agent-contract-redesign/README.md)
retains historical scientific-contract work. Scientific roles do not inherit
repository Writer ownership or physical execution authority. Preserve measurements,
operator settings and non-MAS single/double/explore/double_explore routes. The
default remains double_explore; reading docs does not switch modes or start work.
