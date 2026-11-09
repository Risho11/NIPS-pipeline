# Shared material and process knowledge

Use the [workflow](workflow.md) for inquiry and
[source/output bindings](workflow.md#source-and-output-bindings), and the
[data contract](data-contract.md) for original evidence and measurement meaning.
Scientific usefulness must be judged from actual inquiry outputs; document QA,
well-formed files and careful uncertainty labels do not establish it. These
contracts are enforced operationally by the [Python runtime](python-runtime.md);
software receipts do not establish scientific truth.

## One inquiry, evolving topic documents

One main coordinates analysis, knowledge maintenance and experiment selection.
Shared knowledge holds material/process claims across campaigns; a round explains
which observations changed what and why. It is not a separate agent system or
an agent's private operating memory. Main alone publishes scientifically reviewed
changes through Python's exact-path publication in the bound repository.

Use four documents under `data/knowledge/<material>/`: `concentration.md`,
`prebath_exposure.md`, `bath_temperature.md` and `bath_residence.md`. They group
variable/process reasoning, not scientific types or one hypothesis per variable.
Each develops the current understanding: physical explanations and expectations,
observations that agree or conflict, revised or competing accounts, remaining
uncertainties and next questions. Preserve conditions, motivation and original
predictions. Summarize actual supporting and contrary observations there:
what comparison showed, which prediction it bears on, the interpretation and
remaining rivals/limits, with links to original round analysis and actual review.
For a broad-history reassessment, apply the [analysis coverage rule](analysis-methods.md#match-analysis-coverage-to-the-question)
and synthesize actual broad and local numeric findings, both supporting and adverse,
with consequential stability/applicability
limits and original analysis links. Explain how that evidence changes or justifies
retaining the explanation/domain/prediction/priority; neither a missing microscopic
intermediate nor unchanged labels replaces the assessment.
The topic document should explain current judgment and consequential revision
reasons; bare references are insufficient. Initial records state theory, actual
literature and expectations, with no target experimental evidence or round-analysis reference
unless such evidence was actually used and its origin disclosed. One analysis
may inform several topics: write cross-variable reasoning once and link it from
the other affected topics. Internal prose/layout is flexible; no fixed sections,
table, new claim ID or hypothesis quota applies. A material directory name does
not verify chemistry. The four topic files replace active per-ID storage and
separate index/coverage-file requirements; retained IDs serve as provenance.

Round originals live under authorized `data/results/<campaign>/mas/rounds/<operation>/attempt-<n>/`:
`inquiry.md` / `inquiry-review.md` for integrated work, or `analysis.md` plus
`hypothesis-update.md` with actual review coverage for split work. Design/review,
`decision.md` and useful `artifacts/` remain there. These paths locate needed work,
not mandatory empty files or a fixed prose schema. Link the round's proposed change
to the topic document and the accepted revision back to its evidence/review.
Do not copy the entire knowledge base into every round. Agents write current
attempt drafts/artifacts only; Python publishes the four canonical topics and
reviewed round records in the existing repository. A campaign/material owns one
Main and tracked checkpoint; another campaign has its own Main and may reuse the
shared bank only through its accepted Git provenance. Concurrent bank changes
require explicit reconsideration. Actual permissions must be checked separately.

When migrating older index/variable/per-claim records, preserve those originals
and trace their exact meanings, judgments, negative evidence and sources into the
relevant topics. Distinguish historical reconstruction and missing originals from
recovered bytes. Review semantic preservation; regrouping adds no scientific support
or independent confirmation. A new test root inherits no acceptance silently;
any deliberate seed needs provenance and authorized scope.

## Initialize, then learn from observations

When no applicable bank exists, main asks the same hypothesis author and distinct
QA to initialize it from material/process/measurement constraints, articulated
physical reasoning and scientific sources actually read, before current outcomes
are examined. Reviewed current analysis is not a prerequisite to this bootstrap.
Account for all known important process variables and fixed/context settings
through the variable coverage below. Form process-centered explanations involving
meaningful stages and coupled effects, without one claim per variable or a
prescribed bank size. Initially unknown applicable ranges may stay unknown; later
observations can locate regimes and motivate predictions for later evaluation.

Preserve the initial meanings, conditional directions, prerequisites, rival
predictions, sources and actual outcome exposure before revealing data. Do not
supply old agent hypotheses/reports, worked causal answers or private outcomes to
fresh initialization participants. Supply only approved constraints and factual
measurement definitions; outcome-bearing source links/sections await reveal. If a participant already knows results, disclose that rather
than claiming an unexposed prior. Existing data-derived claims retain their IDs,
history and retrospective origin; never erase or relabel them as initial theory.
An already exposed continuation resumes that knowledge rather than manufacturing
a fresh blind bootstrap.

After authorized observations arrive, integrated inquiry or reviewed split analysis informs updates,
revisions and new ideas. Theory can be wrong; challenge it rather than force-fit
results. Mark data-generated additions as such, distinguish exploratory use from
an independent confirmatory test, and preserve old meanings when revising. Even
an outcome-withheld reveal of historical data remains a retrospective evaluation,
not a new prospective experiment. External-system evidence is not target-system
confirmation, and using the same evidence to propose and assess a claim adds no
independent support.

Reuse applicable knowledge across rounds/campaigns. Read relevant or changed topic
documents rather than bootstrap again each turn. Reconcile
new theory and older retrospective accounts explicitly without hiding origins or
counting duplicate ideas/evidence as corroboration. Initial publication and later
observation updates remain separate from main's next-test selection.

## Reasoning before and after observations

Separate a measured observation, a testable process-effect proposition and a
proposed pathway explaining that effect. A variable → process/structure → property
chain is useful only when the particular links and direction have a reason in
the material/process context. Cite original comparisons, a physical argument with
stated assumptions or an applicable scientific source actually read. Literature
is optional; invented citations and generic remembered mechanisms are not evidence.

Explaining an increased modulus by saying a change “may make the network/matrix
stiffer” merely restates the response unless the account says why that intermediate
and direction deserve attention. Consider process sequence, persistence of a
preparation state, contrary observations and the strongest credible rival. An
unconfirmed mechanism can be worth testing, but proposed/inconclusive labels
alone do not make it a useful selection rationale.

Compare predictions for available or feasibly obtainable observations under the
same contrast. If pathways have the same available property predictions and differ
only in unavailable assays, retain them as unresolved possible accounts. Do not
present a property screen as their mechanistic discriminator. A narrower process-
effect test can still be worthwhile when its result changes a process decision;
state its limited inference and why it takes priority over practical alternatives.
Apply the workflow's [discrepancy completion rule](workflow.md#completing-discrepancy-inquiry)
before treating that narrower action as completion of requested explanation work.
Keep contextual and combined causes possible when supported, without creating a
mandatory hypothesis for each variable or a new mechanism every turn.

Preserve original precision, provenance and inferred chemistry. Compression pore
fraction is not an image of structure; coverage photos do not measure a cross-section.
A numeric modulus and passing fits do not by themselves certify material quality.
Evaluate each claim/endpoint and shared quality dependencies using the data contract.

## Variable coverage

Keep important-variable coverage in the relevant topic documents or linked existing
context, including explicit reasons and reconsideration cues for variables without
a justified present account. Ground definitions, units and control status in
approved operator context and [source definitions](data-contract.md#conditions-operator-authority-and-decisions).
Consider all known important request tunables, operator-prepared/locked settings,
relevant protocol constants and environmental/provenance variables. Record what
is controllable now, fixed for the batch, measured, inferred or unknown; a code
constant does not certify physical installation. Link relevant context sources.

No important control or context disappears because it lacks its own topic file.
Several variables may enter one pathway and one variable may enter competing
pathways. A justified but untested account differs from no present account; do not
invent mechanisms to fill coverage. Reuse and update the relevant coverage when
knowledge or constraints change, without a separate variable catalog or new files.

Fixed settings can motivate a scientific hypothesis and a future operator
comparison, even though they cannot enter the current executable condition.
Unknown environments or preparation histories are not silently assigned values.

## Conditional explanations and measurement meaning

Give a physical/source reason for the proposed direction, credible competing
processes and the domain in which one could dominate. Nonlinear, coupled or
regime-dependent explanations are welcome when motivated; neither universal signs
nor an optimum for every variable follows. Avoid a symmetric list in which every
outcome supports some interchangeable story. Preserve distinguishing predictions;
when data suggest a boundary, label that discovery and assess later predictions
without retroactively changing the original forecast.

The [producer](../../src/pipeline/curve_segmentation.py) normalizes load by area
and displacement by thickness. In consistent units, `E = k * thickness / area`,
with `k` the load-displacement slope; retain the producer's bar conversion.
More total polymer or thickness alone does not establish increased normalized E.
Separate measured response, proposed internal process and actually measured
intermediate. Agreement with an SS-curve/property prediction can inform process
behavior without confirming internal morphology. Use available originals before
requesting new acquisitions; additional assays are optional only when feasible,
authorized and decision-critical.

## Review, publish and preserve history

Bootstrap author/QA can work before current observations. The default integrated
updater later analyzes outcomes and develops explanations together; a triggered
split supplies analysis under assigned independent review. Distinct hypothesis QA
reviews consequential analysis and inference. The updater drafts proposed changes,
retentions, rationale, rival predictions and recommended question priorities.
For a consequential discrepancy, link the original forecast and adverse observation
to the actual rival comparison: what was learned, what remains unidentified, and
why meaning/domain/prediction/priority changes or stays. A changed substantive
account preserves its predecessor meaning and data-generated origin; status bookkeeping
alone does not supply that development. Justified retention needs no new claim.
Distinct hypothesis QA checks motivation and usefulness as well as source truth,
status and identity. Main reads actual artifacts/findings and makes its own value
judgment before publication/selection; PASS is not a command to choose a claim.

Authors draft only in assigned areas; reviewers keep separate findings and never
repair canonical knowledge or author work. Main publishes accepted changes to
the topic documents, retaining previous meanings, judgments, negative evidence
and round links. If no shared-write authority exists, return a pending proposal.
Explain a changed mechanism, scope or prediction alongside its prior meaning;
do not silently inherit support or require a new ID/file for every revision.
Use the workflow's [invocation-bound Git rule](workflow.md#source-and-output-bindings)
when authorized; accepted knowledge history needs no separate version files or
per-round bank snapshots. No new measurement means no fabricated confirmation/
refutation. Working priority or a better question can
change with improved reasoning while empirical status remains unchanged.
Before describing a claim as confirmed, refuted or withdrawn, compare its actual
before/after meaning and evidence under the original conditions. A conditional
account must not become a universal predecessor merely to reject it. Distinguish
scientific status, learning priority and performance ranking in topic prose and
summaries; a useful first question is not an established best-performing condition.

If design or new evidence invalidates a premise, mark affected judgments as needing
review, suspend dependent run recommendations and return to the appropriate
analysis/author/QA work. Re-review affected reasoning, preserve the correction in
shared history and its round, and retain unaffected evidence. A rejected draft
never becomes current knowledge. Publication, selection and physical execution
are separate decisions; scientific review grants no hardware authority.

## Python publication boundary

The [runtime](python-runtime.md) publishes exactly Main-adopted topic changes and
relevant readable records on Main's behalf. Authors/reviewers do not modify shared
knowledge or Git. Native identity/completion and exact operational publication are
software boundaries, not proof of scientific truth. Preserve rejected findings and
prior accepted versions when a stable, explicitly requested revision is reviewed.
