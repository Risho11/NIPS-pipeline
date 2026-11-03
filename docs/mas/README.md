# Experiment MAS

Start here for the scientific agent contracts and shared material/process
knowledge. The revised contracts have received independent development review;
actual MAS testing, observed-defect repair and re-evaluation are now requested.
**Human review will address final scientific outputs before DCP. Revised-contract
live results remain NOT_RUN until actual run evidence is recorded.** The earlier
SDK case below is historical evidence, not validation of these revisions.
Production Python integration remains separate work.

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
changes within the authorized output root. Locate authorized original curves,
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

The retained [analysis-QA role](../../subagents/experiment-analysis-qa/AGENTS.md)
and [method checks](../../subagents/experiment-analysis-qa/docs/review-checklist.md)
serve explicit preserved adapter/compatibility-pilot dispatch. They are not a
second target inquiry QA; the historical SDK route remains separate.

Return material findings through main to the affected author and reviewer;
preserve earlier judgments and re-review dependent conclusions. Keep flexible
Markdown inquiry (or split analysis/update), design and final-decision records without
a report-file quota, and a readable index linking artifacts, revisions, actual
QA findings and unresolved evidence. No fixed figure roster, whole-report JSON echoes,
all-report hash gate or parentage framework is required. Shared knowledge uses
an index, `variables.md` (linked and explicitly unlinked coverage) and stable
hypothesis files with concise evidence assessments and round references. Actual
operator batches have summaries and proposed next-batch fixed-setting comparisons;
report-only candidates claim no physical completion. See the
[records convention](workflow.md#records-are-navigable-and-revisable).

Run adopts exactly the scientifically reviewed feasible conditions. Hold names
the missing evidence/review/operator need and a condition for reconsideration;
stop explains why another test is unjustified. Hold and stop supply no executable
conditions. A report-only run recommendation grants no physical execution authority.

## Implementation and evaluated scope

The [pilot](../../scripts/mas_agent_pilot.py) activates main's instruction
contract and copies the [six specialist bindings](../../.codex/agents/) into an
isolated scientific workspace. These bindings and earlier contracts were accepted
for that pilot; current contract revisions still need their own review and live
evaluation. Main is not a seventh registered SDK binding.

The [evaluation report](../../harnessing/2026-10-29-mas-agent-contract-redesign/reports/PILOT_EVALUATION.md)
records one actual English native SDK main inquiry on 58 promoted, 64 aggregate
and 232 specimen rows copied from the October campaign. It completed in
1001.382 seconds with exit 0. Three scoped scientific QAs passed, and
[independent development QA2](../../harnessing/2026-10-29-mas-agent-contract-redesign/EXECUTION_STATUS.md#phase-3-step-2-qa2-acceptance)
accepted the defensible independent-repeat recommendation. No physical experiment
or guaranteed improvement resulted from this evaluation.

Authored scientific repair/re-review, upstream reopening, prior hypothesis
history and prediction scoring, hold/stop, live failure/deadline recovery,
raw-curve/image assessment, physical behavior and production integration remain
unexercised in that live case. The broader coordination count was 18 starts/messages
against a soft aim of 12; that aim was unmet. Visible English instructions,
artifacts and main messages were verified; encrypted delegation utterances could
not be audited. No private reasoning was decoded to fill that gap. See the report
for source uncertainty and full coverage limits.

## Scientific session inputs and outputs

Use the workflow's [source/output bindings](workflow.md#source-and-output-bindings),
[data contract](data-contract.md) for originals and warm-start provenance, and
[knowledge guide](knowledge.md) for shared publication and history. Read approved
project evidence while writing only assigned temporary round/knowledge outputs.
Actual permissions must be checked separately from task instructions. Concrete
session paths, read set, authorization and budget belong in the transient dispatch.

## Historical SDK pilot route

Follow the [pilot guide](pilot-evaluation.md) for explicit objective/material/bath/
stock context, additive lock, source cutoff and a new output directory outside
the repository. Use `uv run` for Python commands. Preparation is the default;
only explicit `--live` starts inference. The guide's P3S1 `NOT_RUN` status is its
preparation snapshot; the evaluation report above records the subsequent live case.

For that route, before inference verify the configured OpenAI provider, exact
data-transfer authorization and Controller's bounded handoff. The approved transfer covered
37 specified files and derived results; it grants no broader dataset/destination
scope. Each authorized evaluation run is limited to 1200 seconds. Retain failed
attempts and obtain a new bounded handoff before another run. The guide describes
isolation and effective-MCP checks; it does not grant hardware access.

## Production and development boundaries

The production [Codex adapter](../../src/pipeline/codex_context.py) and
[run loop](../../src/pipeline/run_loop.py) have **not been migrated** to this
adaptive pilot workflow. Their existing read-only, fixed-stage adapter behavior
remains a separate compatibility route. Preserve measured data, operator settings
and legacy `single`, `double`, `explore`, `double_explore` modes. Reading these
docs or running the pilot does not activate production or authorize robot calls.

Repository development uses a separate external-reference
[Controller/Writer Harness](../../harnessing/2026-10-29-mas-agent-contract-redesign/README.md),
with independent development QA and user-selected ordinary Git commits. Shared
guidance resolves through `NIPS_SHARED_AGENT_ROOT` at the
[pinned external source](../../harnessing/2026-10-29-mas-agent-contract-redesign/EXTERNAL_SOURCE.json),
without a submodule or copied shared skill bodies. Scientific authors/reviewers
do not inherit development ownership or physical execution authority.
