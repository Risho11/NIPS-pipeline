# Question-led analysis of membrane experiments

## Start with the decision that evidence could change

Use the [data contract](data-contract.md) for fields, units, sources and execution
boundaries. This guide supplies shared reasoning methods; role instructions
assign authorship, scientific QA and main's final decision. It describes the
target inquiry and isolated analysis work, not capabilities already provided by
the preserved read-only, fixed-stage adapter.

Turn main's question into an assessable uncertainty: did the latest experiment
contradict a prediction, is an apparent improvement robust to processing, can a
temperature effect be separated from composition, or is another synthesis needed?
Read the previous prediction and its comparator/decision criteria when available.
If no prediction was recorded, label the comparison retrospective. Distinguish
a measured outcome, a compatible explanation, and evidence that would discriminate
explanations. Do not choose explore/optimize/repeat or invent a new hypothesis
before identifying the evidence need.

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

## Worked case: actual same-label outcomes

In the [October campaign table](../../data/results/begins_2026-10-15/llm.csv),
select exact names
`14-0add-8deg-cosolv-none-bathSolv-none-0wt-120s-N2-1250s_run2` and
`14-0add-8deg-cosolv-none-bathSolv-none-0wt-120s-N2-1250s_run3`.
Stored values displayed rounded are:

| Row suffix | Elastic Modulus Mean / SD (bar) | Pore Fraction Mean / SD |
| --- | --- | --- |
| `_run2` | 189.4164 / 9.2727 | 0.7150 / 0.0178 |
| `_run3` | 171.4564 / 14.3412 | 0.6270 / 0.0223 |

The second row is about 17.9600 bar lower in mean modulus and 0.0880 lower in mean
pore fraction (8.80 percentage points). This is a difference between selected
aggregate records. It is not a controlled temperature contrast: the labels share
the same bath-temperature setting. Their SDs describe specimen dispersion, not
uncertainty of the between-record difference.

Before calling this a reproducibility failure, inspect specimen identity,
acquisition and processing to establish whether these are independent syntheses
or another representation of the same material. Then inspect exclusions and
stock/environmental context. If independence is confirmed and the difference is
decision-relevant, investigate variability or propose another controlled synthesis.
If it cannot be established, retain the bounded observation and request provenance;
do not claim either successful validation or disproven reproducibility. This
comparison does not perform an experiment or select an actual next point.

## Worked case: temperature and composition change together

Hypothetical example, not repository measurements: A uses 14 wt% polymer and an
8 °C bath and yields 180 bar; B uses 16 wt% and a 15 °C bath and yields 230 bar.
Other conditions, quality and source identities also need checking. The 50 bar
difference cannot isolate temperature because polymer content changed. A modulus
versus bath-temperature graph alone would conceal that.

Search for 14 wt% at both temperatures or 16 wt% at both, with matched bath
chemistry, exposure, stock context and adequate quality. If none exists, a
transparent comparison table can be the useful result: the combined change
improved the observed outcome while both explanations remain compatible. Pass
that distinction to hypothesis maintenance and main. Main can select a hypothesis
and ask design for a feasible matched control rather than optimize an unidentified
temperature trend. If design QA later discovers different bath-solvent content,
return to analysis and reopen affected judgments.

## Worked case: exclusions change the apparent ranking

Hypothetical example: C has specimen modulus values 100, 110 and 300 bar. The
300 bar estimate fails elastic-region fit quality. The pre-discard mean is
170 bar and passing-only mean 105 bar. Comparator D has an observed mean of
120 bar with adequate fitting evidence. C's apparent advantage changes with the
documented exclusion.

Inspect why the fit failed and whether thickness/contact or region selection
explains the extreme estimate. Show both processing interpretations, counts and
ranking consequence; do not choose a variant to favor C. Check other properties
separately: post-discard thickness and 50 bar strain may include broader evidence,
and pore fraction shares fit assumptions. Without original curves, ranking
sensitivity is established but the exclusion's physical explanation is unresolved.
Main may seek processing review, a better measurement or another synthesis.
Deleting a failed fit neither proves poor material performance nor independently
validates D's reproducibility.

## Worked case: history cannot supply a missing control

October example rows record a 0 wt% bath-solvent context; current source settings
describe a PolarClean 10 wt% bath. Suppose main asks whether a point in the latter
context will preserve a historical high modulus. Historical 0 wt% outcomes may
motivate an explanation, but are not measured controls at 10 wt%. Source settings
also do not establish the physical bath used. Request operator-confirmed case
conditions and inspect material/stock provenance. Label extrapolation and ask
what comparison would discriminate the bath effect. Do not relabel history,
describe an unexecuted point as verified, or repeat a historical formulation that
violates current stock feasibility or an additive lock.

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
evidence, or hold/stop. Main chooses after hypothesis maintenance and selection,
predictions, design and relevant scientific QA. A performance decline can still
discriminate a hypothesis. Do not force improvement, a new hypothesis or a
global-optimum claim as the condition for useful analysis.
