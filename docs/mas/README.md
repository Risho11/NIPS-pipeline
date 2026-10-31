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
observations, hypotheses, predictions and open questions. Reviewed analysis
informs hypothesis maintenance and main's selection; predictions and competing
explanations inform design; the reviewed feasible design informs the final
run/hold/stop decision. The same MAS updates shared material/process knowledge,
then selects and designs the next informative test. Seek process variable →
proposed process/structure → property explanations and competing predictions;
rank persistence and fit/repeatability checks need not answer that inquiry.
Choose explore, optimize or repeat for the information needed, without forcing
a new hypothesis or promising improved performance.

Use the [workflow](workflow.md) for collaboration and upstream returns, the
[data contract](data-contract.md) for measurements/provenance/constraints, the
[analysis methods](analysis-methods.md) for question-led calculations and figures,
and the [campaign guide](../../subagents/campaign-main/docs/campaign-guide.md)
for decision examples.

Use [shared knowledge](knowledge.md) to separate canonical material/process
claims and bounded history from each round's evidence update and decision.
Updater drafts; independent QA reviews; main alone accepts/publishes shared
changes within the authorized output root. Locate authorized original curves,
photos, params and plots before declaring evidence missing. Keep measurements,
actually read literature and proposed inference distinct; unmeasured morphology
does not become observed merely because a property direction agrees.

Main directs three author/independent scientific-QA pairs:

| Author and methods | Distinct reviewer and checks |
|---|---|
| [Experiment analyst](../../subagents/experiment-analyst/AGENTS.md) · [Analysis guide](../../subagents/experiment-analyst/docs/analysis-guide.md) | [Analysis QA](../../subagents/experiment-analysis-qa/AGENTS.md) · [Review checklist](../../subagents/experiment-analysis-qa/docs/review-checklist.md) |
| [Hypothesis updater](../../subagents/hypothesis-updater/AGENTS.md) · [Hypothesis guide](../../subagents/hypothesis-updater/docs/hypothesis-guide.md) | [Hypothesis QA](../../subagents/hypothesis-qa/AGENTS.md) · [Review checklist](../../subagents/hypothesis-qa/docs/review-checklist.md) |
| [Experiment designer](../../subagents/experiment-designer/AGENTS.md) · [Design guide](../../subagents/experiment-designer/docs/design-guide.md) | [Design QA](../../subagents/experiment-design-qa/AGENTS.md) · [Review checklist](../../subagents/experiment-design-qa/docs/review-checklist.md) |

Return material findings through main to the affected author and reviewer;
preserve earlier judgments and re-review dependent conclusions. Keep flexible
Markdown analysis, hypothesis-update, design and final-decision records without
a report-file quota, and a readable index linking artifacts, revisions, actual
QA findings and unresolved evidence. No fixed figure roster, whole-report JSON echoes,
all-report hash gate or parentage framework is required.

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
