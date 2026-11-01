# Question-led analysis of membrane experiments

## Start with the decision that evidence could change

Use the [data contract](data-contract.md) for fields, units, sources and execution
boundaries. This guide supplies shared reasoning methods; role instructions
assign authorship, scientific QA and main's final decision. It describes the
target inquiry and isolated analysis work, not capabilities already provided by
the preserved read-only, fixed-stage adapter.

Default integrated inquiry and a triggered split both use data science and
physical/chemical reasoning. The integrated author performs needed calculations;
an analyst receives a bounded unresolved issue under the workflow's
[split/rejoin criteria](workflow.md#when-main-splits-and-rejoins-inquiry), not every
round by default. Initialization uses approved definitions/constraints without
following evidence links to outcomes, prior agent answers or notebook outputs.
The comparisons below apply after authorized observation access.

Turn main's question into an assessable uncertainty: did the latest experiment
contradict a prediction, is an apparent improvement robust to processing, can a
temperature effect be separated from composition, or is another synthesis needed?
Read the previous prediction and its comparator/decision criteria when available.
If no prediction was recorded, label the comparison retrospective. Distinguish
a measured outcome, a compatible explanation, and evidence that would discriminate
explanations. Do not choose explore/optimize/repeat or invent a new hypothesis
before identifying the evidence need.

For a process/property question, also ask how a process change could produce an
intermediate process/structure change and the observed property response. Use
the [shared knowledge guide](knowledge.md) to separate original measurements,
actually read scientific sources and proposed inferences. Search authorized
original curves/photos/params/plot metadata via the [data contract](data-contract.md)
before declaring evidence absent. Read current accepted knowledge and report
which prior prediction the latest actual result does or does not test.

## Build a defensible comparison

Locate the supplied CSV headers and numeric values. Trace material claims to a
path, exact condition, processing variant and, where relevant, Trial. Calculate
with stored precision and display readable rounded values. Do not substitute
narrative measurements for authoritative numeric fields or split multiline CSVs
into supposed rows by text lines.

For the candidate comparison:

1. Identify the physical unit: specimen, synthesis, processing variant or
   historical context. Resolve duplicate exports and reused material before
   calculating an effective sample count.
2. Match variables needed for the question. A bath-temperature comparison also
   needs scrutiny of formulation, polymer/solvent/bath identities, nitrogen and
   exposure, immersion time, casting speed, mixing history, stock age and
   environment. Unknown controls remain unknown.
3. Check finite outcomes, thickness/contact reliability, fit flags/reasons,
   property-specific contributing specimens and pre/post-discard choice. Inspect
   source curves/plots if fitting could change the conclusion; request them
   through main if not supplied.
4. State what the comparison can answer. A matched contrast supports a
   conditional association; it does not itself prove a pore-formation mechanism.
   A confounded comparison can describe a combined change and motivate a
   discriminating control without isolating either factor.

Explain inclusion/exclusion and whether a plausible alternative changes the
decision. Do not silently remove inconvenient failures. Missing outcomes need
not invalidate unrelated observed properties, but can prevent a two-objective
comparison.

## Choose a method for the uncertainty

| Uncertainty | Useful analysis to consider | Limit on the conclusion |
| --- | --- | --- |
| Did the latest point behave as predicted? | Link proposed conditions to actual execution; compare the stated observable and comparator; classify agreement, disagreement or inconclusive evidence | An unmatched proposal or qualitative resemblance is not a verified prediction |
| Is a gain a processing artifact? | Compare aggregate variants, specimen inclusion and source fits; calculate sensitivity to documented processing choices | A better-looking post-discard mean is not automatically more reproducible material |
| Is one factor responsible? | Seek matched controls or local contrasts; display other changed factors and competing explanations | A multivariable trajectory cannot isolate causality just because one axis is temperature |
| Which process explanation is worth testing? | Trace variable → proposed intermediate → property, compare alternative predictions and inspect relevant original evidence | A compatible property direction does not establish the intermediate; unresolved causation does not forbid a clearly proposed explanation |
| Is a result repeatable? | Separate specimen spread from verified independent-synthesis outcomes; inspect batch, time and process differences | Small specimen SD or `_runN` alone does not establish synthesis reproducibility |
| Which tradeoff deserves a test? | Compare modulus and compression pore fraction jointly with quality/missingness visible; identify observed nondominated candidates if useful | A sampled frontier is not a global optimum or guaranteed future frontier |
| Is the evidence region sparse? | Inspect coverage in relevant variables, with categories/scales explicit; identify an untested contrast that could change a hypothesis | Arbitrarily scaled coordinate distance is not scientific information gain |

For a measured contrast, report the absolute difference in source units. A
relative difference can help when the reference is meaningful and nonzero; name
the denominator. Do not average all exports as independent observations or use
pooled specimen SD as between-synthesis uncertainty. With verified independent
counts, an appropriate uncertainty calculation may help; no significance test is
mandatory. With sparse syntheses, show individual outcomes and limitations rather
than manufacturing precision.

If a model would answer a real question, state its target, covariates, processing
choices and available independent observations. Prevent specimens or duplicate
exports of one synthesis from leaking across evaluation splits. Treat
extrapolation, missing controls and limited independent coverage as limitations.
A fitted surface is an analysis aid, not a mechanism or verified performance at
an unexecuted point.

## Let data science and physical reasoning challenge each other

Inspect question-relevant feature/response relations, local behavior, nonlinearity,
interactions, regimes and dispersion alongside variable correlations and missing
coverage. Input correlation means settings co-occur; effect interaction means a
variable's response relation depends on another setting. A correlated campaign
trajectory does not identify either a causal main effect or interaction merely
because a model assigns importance. Locate matched/local contrasts and credible
counterexamples; preserve simultaneous changes and unknown controls.

Use physical/chemical reasoning to propose interpretable domains, competing
processes and distinguishing predictions. Examine authorized raw SS curves,
params, photos and non-objective mechanical descriptors when they could challenge
those predictions. Shared curve-fit outputs are dependent evidence, not independent
morphology measurements. Data can locate an initially unknown regime or suggest
a new account; preserve the original forecast and label data-inspired refinements
before testing later predictions. Avoid a story that changes to fit every result.
Useful process behavior can be learned without full internal-mechanism identification.

Choose a model only for an actual question and available independent coverage.
In observation analysis, [campaign_trends.ipynb](../../EVALUATE/campaign_trends.ipynb)
contains ridge, cross-validated permutation importance, interaction products,
linear SHAP and PCA examples. Inspect source choices when relevant, without
executing it by default, copying its filters/plots or treating it as a mandatory
suite. Linear coefficients and linear SHAP cannot demonstrate arbitrary nonlinear
behavior; PCA describes input variance, and importance explains predictive use,
not a causal direction. Consider a suitable nonlinear/local comparison when the
question/data justify it, not a universal complex-model requirement.

For decision-critical predictions, assess held-out predictive sufficiency relative
to a relevant simple baseline, residual behavior and support of the proposed
region. Keep preprocessing, feature/model selection and tuning inside the relevant
training split. Do not leak specimens/processing variants of one synthesis across
splits. Use verified synthesis, temporal or operator-batch grouping/generalization
when relevant, and state unknown independence rather than inventing groups.
Assess sensitivity/stability to defensible exclusions, strata, features and model
choices, including correlated-feature attribution. Sparse coverage may justify a
bounded descriptive conclusion instead of reliable validation. Repeated random
splits alone do not establish new-batch generalization.

If defensible choices still change the next variable/region/action, a missing or
invalid decision-critical analysis/model/evaluation method blocks the next action,
or actual QA finds selective evidence or moving explanations, tell main with exact
evidence. For a method task identify what is missing/invalid, its action blocker,
concrete construction/repair and validity check. Routine CSV reading, arithmetic or
a figure using an applicable method alone is not that trigger; an actual method
gap can justify split without an authored error. Main must apply the split
contract and record duties, review coverage and the rejoin condition. Adding agents
does not manufacture data. Additional SEM/assays are optional only if feasible,
authorized and necessary for the current decision.

## Make the artifacts the question needs

A table may expose missing bath metadata more clearly than a plot. A matched
contrast plot may expose a confounder; specimen points and fit overlays may
resolve an exclusion question; a joint-property scatter may clarify a tradeoff.
Choose accordingly. There is no required figure roster or quota.

When authorized to create artifacts, use the supplied isolated experiment work
area. Preserve original measurements and operator settings. Record source paths,
row selectors, columns, units, processing versions, transformations and inclusion
decisions in the script or adjacent artifact explanation so scientific QA can
reproduce consequential numbers. Use `uv run` for Python. Do not import or launch
the hardware loop for analysis context; read source/configuration and supplied
evidence instead.

Label axes and group encodings. Distinguish specimen points from synthesis means
and label error bars with their actual meaning, such as within-synthesis SD.
Preserve missing values in tables and explain omitted points; a missing pore
coordinate is not zero. Do not present row order as elapsed time or imply causal
trends through changed conditions. Explain the pattern a figure reveals and the
alternatives it leaves unresolved. A figure's existence is not evidence that its
source values or mechanism were checked.

## Preserve observations while testing interpretations

A descriptive difference can remain correct while factor attribution is withdrawn.
Keep exact sources, processing versions, controls and sample identities; show how
alternative defensible inclusion or fit choices affect the decision. Do not select
an attractive variant to protect an explanation. Missing/failed fits do not mean
zero performance, and unavailable secondary endpoints do not automatically erase
or validate a primary contrast: inspect their shared quality dependencies.

Prediction assessment uses actual executed conditions and preserved criteria,
not improvement alone or thresholds invented after reveal. A model fit, a repeated
review or reuse of generative data adds no independent confirmation. Link the
round's analysis to each affected claim with a concise observation/interpretation/
limit summary in the canonical record, preserving adverse evidence and original
predictions. Integrated QA reviews the analysis and explanation; focused analysis
QA may add methodological depth when main explicitly justifies it.

## Decide when to return the work

Continue when a feasible check of available evidence could change the comparison,
hypothesis status or experiment choice: resolve a duplicate source, inspect an
exclusion, or locate a matched historical row. Do not generate figures merely
because uncertainty remains. When available analysis cannot resolve the material
gap, name the needed measurement, provenance or discriminating experiment and
return it through main.

The handoff should let main find accepted observations/artifacts, understand the
strongest supported conclusion and competing explanations, and see what remains
unknown. Preserve earlier judgments and explain revisions in the flexible analysis
record. Give scientific QA original source pointers and computation context to
check consequential claims independently; writer self-checks are not acceptance.

An informative action can be a repeat to assess independent variability,
exploration to separate explanations, a local optimization test, a request for
evidence, or hold/stop. Main chooses after reviewed inquiry and selection,
predictions, design and relevant scientific QA. A performance decline can still
discriminate a hypothesis. Do not force improvement, a new hypothesis or a
global-optimum claim as the condition for useful analysis.
