# Reviewing whether the next experiment can teach us something

Use this guide as the explicitly invoked [scientific design QA](../AGENTS.md).
Consult the [data contract](../../../docs/mas/data-contract.md),
[analysis methods](../../../docs/mas/analysis-methods.md) and
[workflow](../../../docs/mas/workflow.md) for shared evidence and main's authority.
Review candidate reasoning and exact conditions against originals, not report
format or a whole-report JSON copy. Actual invocation permissions govern any
independent review calculations/artifacts; preserve the author's candidate.

## Start from selection, not attractiveness of the point

Recover main's selected hypothesis and why it was selected. Compare that meaning
with the claim the proposed experiment actually tests. A designer can explain a
problem with the selected test, but cannot silently replace the hypothesis to
justify an attractive point. Inspect the current candidate/revision and previous
findings, then trace the comparator and consequential evidence to originals.
If material changes during review, clarify the revision and recheck affected
claims/values before giving a current judgment.

Ask what possible result would favor the selected claim, what would challenge
it and what would remain inconclusive. Can a competing explanation predict the
same outcomes? If so, does the design identify the limitation or falsely claim
mechanistic discrimination? A vague promise to "learn about performance" does not
justify a specific causal conclusion. Quality failure, missing outcome or
execution mismatch is not automatically physical refutation.

## Review the information argument

| Design component | Independent question | A useful repair request |
| --- | --- | --- |
| Prediction | Does the observable follow from the selected scoped claim and differ meaningfully from alternatives? | Explain the discriminating outcome or return the unresolved hypothesis question through main |
| Comparator/controls | Is the comparator actually measured and comparable in material/bath/formulation/stock/processing context? | Locate the source, obtain a matched comparison, or label the missing future control and limit immediate interpretation |
| Repeat strategy | What is independently synthesized, and why does that evidence need matter now? | Separate specimens from synthesis repeats and explain what the next observation can establish |
| Purpose | Why explore/optimize/repeat for this uncertainty instead of a relevant alternative? | Compare informative contrasts without invented weights or a compulsory model method |
| Criteria | Are support/refutation/inconclusive outcomes specified prospectively and consistent with available uncertainty/quality? | Resolve criteria that label every result support, or disclose the evidence needed for an effect threshold |

Do not equate a novel point with information gain or a feasible/high-predicted
point with a valid test. A lower-performing control can be more informative.
Check that any numerical prediction, objective tradeoff weight, precision claim
or repeat count has an evidence/constraint basis rather than appearing as a
plausible-looking invented constant. No universal significance test or fixed
replicate count is required. Honest uncertainty can motivate the experiment,
provided its interpretation is not overstated.

## Check feasibility as a separate requirement

Independently inspect the supplied current numeric limits, all eight tunables,
operator material/bath settings, stock composition metadata, joint feasible
polygon, additive lock and undiluted-stock condition. Source
[range rules](../../../src/pipeline/activeLearning_29.py),
[stock helper](../../../src/pipeline/polymer_additive_bounds.py) and
[condition validation](../../../src/pipeline/mas_schema.py) explain existing code;
they do not establish which bottles or bath are physically installed.

Check missing/nonfinite values and units before geometry. A point may satisfy
polymer and additive maxima separately but lie outside the stock region. A
projection helper's nearby feasible output must not be substituted for reviewed
values. Reject the original infeasible candidate and return the required repair
through main; the author must assess whether a changed mixture still answers
the question. The zero-additive undiluted polymer stock requires mixing temperature
25 °C under the current rule; do not apply historical mixing temperatures blindly.

An operator lock or material restriction is not a model preference to optimize.
A request to change it goes through main/operator and scientific reconsideration,
not silent reviewer repair. If current stock context is missing, do not certify
physical feasibility from defaults. Mechanical validation supplements scientific
review; it does not prove that the comparator or inference is valid.

## Worked review: an informative matched contrast

The [designer guide](../../experiment-designer/docs/design-guide.md) gives an
explicitly hypothetical next condition at 14 wt% polymer, zero additive and 15 °C
bath, against a stipulated measured 8 °C comparator with other relevant conditions
matched. Independently verify those assumptions in a real case; the example
itself is not evidence that the comparator or physical setup exists.

If the supplied sources establish that comparison and current constraints permit
the exact condition, ask whether a reliable pore-fraction increase, reliable
opposite result and an uncertainty-limited result have appropriately different
interpretations. A modulus decrease need not defeat the local pore-fraction test.
The outcome may discriminate a local temperature relation from no temperature
effect while leaving the underlying mechanism unresolved. Do not demand a higher
expected modulus to accept a useful contrast.

If review instead finds a different polymer concentration or bath composition in
the comparator, the temperature attribution is not isolated. Return the exact
source difference through main for analysis/comparability review and, if needed,
hypothesis reconsideration. Ask the designer to revise the test/interpretation
only after the upstream question is resolved. Do not quietly rewrite its
comparator or choose a different hypothesis yourself.

## Worked review: repeats, missing controls and false completion

Suppose the draft calls another coupon from the same synthesis independent
validation. Trace physical specimen/synthesis identity and ask for a design that
addresses the selected reproducibility question, or a qualified within-synthesis
measurement aim through main. A new independent synthesis is different evidence,
but one additional observation does not by itself establish a reliable variance
estimate or guaranteed reproducibility.

If that historical formulation is outside current stocks or violates a lock,
a nearby snapped point is not an exact repeat. Return the infeasible values and
scientific consequence; require explicit redesign and renewed review, including
upstream reassessment if claim scope changes. Never repair the candidate yourself.

If a needed comparator is only planned, the next executable condition can be
acceptable as one component of a clearly justified future comparison. Check that
its immediate conclusion remains conditional and later controls/repeats are not
presented as measured. A claimed completed comparison without either a measured
control or an honest future plan is blocking. Ask what decision can be made after
this point alone and what must await further observations.

## Null design, findings and bounded acceptance

A null proposal can be correct when main selected no defensible hypothesis,
current operator context is missing, a necessary comparison cannot be obtained,
or no feasible condition answers the selected question. Check the specific reason
and what evidence or decision would permit reconsideration. Main may hold with
that resumption condition or stop if further work is not justified within the
objective/feasible space. Do not demand invented conditions to fill the report
or equate null with a failed scientific inquiry or proof of a global optimum.

Blocking findings should identify the exact claim/condition, original evidence
or constraint, independent check, consequence for interpretation/execution and
smallest useful repair/request. Route upstream issues through main. Distinguish
those defects from ordinary explicit uncertainty that the proposed test is
intended to resolve. A disclaimer does not rescue an infeasible point or a
conclusion that still depends on a nonexistent control.

Return pass/fail for the current candidate, checked source/constraint locations,
consequential calculations, outcome interpretations, findings and remaining
limits. On repair, recheck exact values and affected reasoning; an earlier pass
does not apply to a changed point. Main alone decides run/hold/stop. Its run
conditions must equal the reviewed feasible design without clamping; held/stopped
or report-only pilot decisions do not authorize equipment submission.
