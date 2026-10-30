# Reviewing experimental analysis against original evidence

Use this guide when assigned the [scientific analysis QA role](../AGENTS.md).
Its purpose is independent source and reasoning review, not a formatting score
or a demand to reproduce every sentence. Consult the shared
[data contract](../../../docs/mas/data-contract.md) and
[analysis methods](../../../docs/mas/analysis-methods.md) for domain facts; use the
[workflow](../../../docs/mas/workflow.md) for main's routing and affected review.
Actual runtime permissions govern any independent calculation/artifact work.

## Bind the claim to the question and candidate

Identify what main is trying to decide and which claims in the current report
could change that decision. Follow the actual candidate and artifact locations,
not an old summary. Read prior findings and what the author says changed. If an
artifact is missing, different from the reported revision or inaccessible, state
that rather than claim it was reviewed. No cryptographic identity system or
complete JSON report echo is needed to identify the reviewed material.

Trace consequential claims to original file paths, exact conditions, processing
versions and specimen identities where relevant. Reproduce the important
selection, calculation or comparison independently of the author's prose. A script
that agrees with its own report can still have selected the wrong source rows.
Check a consequential source join directly, particularly when a historical export
and current campaign share a name. A selected processing variant is not an
independent synthesis, and `_runN` alone does not settle independence.

## Check numbers and artifacts where they matter

| Claim at issue | Independent check | Consequence of a mismatch |
| --- | --- | --- |
| A condition improved a property | Re-read numeric source fields, units, row identity, comparator and processing version; recompute the contrast | Correct the number or comparison and reconsider dependent rankings/interpretations |
| The figure shows a tradeoff | Inspect the rendered axes/encodings and selected source values; check missingness and aggregation units | Repair the artifact and any claim based on a missing, mislabeled or duplicated point |
| Variation is small or repeatability is established | Identify contributing specimens and verified independent syntheses, exclusions and SD meaning | Qualify specimen consistency separately from unestablished synthesis reproducibility |
| The result agrees with a prediction | Link proposed to executed conditions and apply recorded criteria to observed outcomes | Mark unmatched, retrospective or inconclusive components without inventing criteria |
| One factor explains the change | Look for matched controls, changed bath/material/stock context and counterexamples | Restrict attribution or request a comparison that distinguishes explanations |

Use original precision to reproduce calculations and allow sensible display
rounding. Determine whether the discrepancy changes a conclusion rather than
blocking on harmless rounding. Check denominators and available counts by
property. Missing/nonfinite values must not become zeros or borrowed historical
measurements. For important pore-fraction claims, check the actual aggregate
field and its compression-derived meaning rather than trusting an existing plot.
Empty specimen pore fields limit reconstruction; they do not disprove populated
aggregate measurements.

For a figure central to the claim, inspect the image when possible and follow
its source selection/transformation. If visual inspection is unavailable, say
whether tabular/computational checks suffice for the narrower conclusion. If the
claim depends on an uninspected fit shape, request the original curve/fit image
or qualify that claim. Do not demand visual artifacts when a table already
answers the question.

## Seek a counterexample and assess comparison validity

Ask what else could produce the observed contrast. Examine changed polymer
content, bath chemistry, exposure/nitrogen, stock/time context or fit selection
where relevant. Check for a nearby or matched observation that contradicts the
claimed trend. A missing counterexample is not proof of causality; a demonstrated
confounder may require qualification rather than discarding the numeric result.

If the author excluded a failure or picked a processing version, check the
recorded reason and whether another defensible inclusion choice changes the
ranking. Shared curve-processing origins can limit a mechanistic interpretation
of modulus/pore-fraction associations. Distinguish a measured property failure
from failure to obtain a reliable property estimate. Do not treat every missing
value as a physical failure or every lower performance result as an unsuccessful
scientific test.

## Worked review: temperature attribution without matched evidence

Hypothetical author draft: A at 14 wt% polymer and 8 °C has modulus 180 bar; B at
16 wt% and 15 °C has 230 bar. The draft attributes the 50 bar increase to bath
temperature. Independently confirm the original values and that both variables
changed; inspect bath composition and quality as additional possible confounders.
An attractive modulus-versus-temperature plot cannot isolate the factor.

A concrete blocking finding could say: the stated temperature effect is not
identified because polymer content also changed; this attribution supports the
proposed hypothesis direction. Request a matched comparison at fixed polymer
content with consequential context checked. If no such comparison exists, ask
for a descriptive joint-change conclusion and the missing discriminating evidence,
not an invented temperature slope or a mandatory statistical test.

After main returns the repaired candidate, inspect the cited search/comparison
and any revised figure. If no matched data exist and the author explicitly
withdraws causal attribution, the 50 bar descriptive contrast can pass with that
scope and residual uncertainty. Tell main that dependent temperature-hypothesis
support/selection/design may need reconsideration. Do not independently choose a
replacement hypothesis or final experimental conditions.

## Worked review: a correct mean can still support the wrong comparison

In the shared guide's hypothetical exclusion case, 100, 110 and 300 bar average
to 170 bar; removing the failed 300 bar fit leaves 105 bar. Recomputing 170 alone
would not validate a ranking against a comparator whose values were post-discard.
Trace each variant and failure rationale, inspect relevant fit evidence, and
request a consistent comparison plus sensitivity where the ranking changes.
The same discrepancy can affect multiple tables/figures; ask the analyst to find
and repair that whole affected set, then check consequential repairs.

If original curves are absent, do not invent validation of the exclusion's
physical reason. A report can correctly show sensitivity and an unresolved
fit-quality question. That supports a bounded analysis, while an unqualified
claim of superior material or validated reproducibility remains blocking.
Your review notes/calculations stay in your own authorized area; author repair
is returned through main, never performed by rewriting the candidate.

## Distinguish blockers from uncertainty and finish usefully

A blocker is a defect or missing essential support that could change the claimed
answer or main's next decision: wrong units/rows, duplicated independent counts,
unjustified factor attribution, altered criteria, or a materially omitted
processing limitation. Identify the claim and original evidence, explain the
consequence, and request the smallest concrete analysis/source/qualification
that could resolve it. Do not prescribe an unrelated figure list or fixed
significance threshold.

A bounded limitation is not automatically a blocker. Unknown mechanism, sparse
independent replication or unavailable fit images may remain explicit when the
accepted conclusion stays within observed evidence. Conversely, labeling an
uncertainty does not rescue a conclusion that still relies on the missing fact.
State whether the report's conclusion is sufficient for its intended use and
which question must remain open for main.

Return a readable pass/fail judgment on the current candidate, checked original
and artifact locations, consequential independent calculations, findings and
remaining limitations. Record the actual review scope without copying the whole
report into JSON. Pass means no material blockers remain for that bounded
analysis; it does not prove future performance or authorize execution. On fail,
main routes targeted repairs to the analyst. Review revised material before
claiming acceptance; if progress needs new evidence rather than another repair,
name that evidence and the decision limitation explicitly.
