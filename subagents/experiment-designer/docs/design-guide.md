# Choosing a test that can change a scientific judgment

Use this guide as the explicitly invoked [experiment designer](../AGENTS.md).
The shared [data contract](../../../docs/mas/data-contract.md) defines measurement,
material and stock semantics; [analysis methods](../../../docs/mas/analysis-methods.md)
defines comparison limits. The [workflow](../../../docs/mas/workflow.md) retains
main's selection and final decision. These target/pilot methods do not migrate
the preserved production adapter or authorize execution.

## Translate the selected claim into distinguishable outcomes

Recover the exact selected hypothesis and main's reason for testing it. Identify
its domain, predicted observable and competing explanation. Ask whether the
proposed test permits outcomes that would change judgment. If every possible
outcome would be described as support, revise the question through main before
choosing a point. Do not replace the selected hypothesis silently.

Predictions should distinguish a direction/pattern or an evidence-supported
magnitude from the alternative. Use effect estimates or uncertainty scales only
when the data justify them. Without a trustworthy scale, state a qualitative
prediction and the measurement/comparison needed to interpret it. Do not invent
an exact percentage gain, weighted objective or confidence level. Criteria must
explain support, refutation and inconclusive outcomes before new measurement;
quality failures and unmatched execution are separate from physical refutation.

Check whether analysis already supplies a trustworthy comparator. Trace its
source, processing version, materials, bath, stock context, quality and sampling
unit. A source row's next-point suggestion is not a measured control. Ask main
for analysis or hypothesis review when comparison identity or claim scope is
unresolved. An attractive point cannot fix an unidentified comparison.

## Choose the contrast, controls and repeat strategy

Choose what varies and what must remain comparable to isolate the selected
question. A temperature contrast confounded with formulation or bath composition
may not separate the explanations. If the missing control is itself unmeasured,
explain how the next condition contributes to a planned comparison and what
remains conditional until the other observation exists.

| Evidence need | Purpose to consider | Design consequence |
| --- | --- | --- |
| Alternatives predict different behavior in an untested contrast | Explore | Choose a feasible distinguishing contrast with meaningful controls, even if its expected performance is lower |
| Evidence motivates a local improvement/tradeoff test | Optimize | Explain comparator, prediction and competing outcome without claiming a global optimum or inventing objective weights |
| Independent synthesis variability affects interpretation | Repeat | Define what is newly synthesized and held fixed; separate specimen testing from independent replication |

Explain the primary reason if purposes overlap. Do not require a particular
model, acquisition function, novelty score or figure. Compare relevant alternative
tests by what they could teach, feasibility, uncertainty and actual operator-supplied
resources. A point near the current best may be uninformative; a control with lower
expected modulus may better distinguish a mechanism or validate reproducibility.

Repeat needs depend on observed variability, independence and the decision at
stake. Do not impose a universal specimen/synthesis count or invent a precision
claim. If the evidence cannot justify a repeat count, explain that limitation and
what the next independent observation can and cannot establish. A broad future
repeat plan is not a set of already completed observations.

## Bind exact conditions to the actual constraints

A proposed next point includes all eight tunables, units and the unchanged
operator material/bath context. Use the explicit case's stock metadata, locks and
limits. Check the joint composition region rather than treating polymer/additive
maxima as independent. Inspect the current
[stock helper](../../../src/pipeline/polymer_additive_bounds.py) and
[range rules](../../../src/pipeline/activeLearning_29.py) when source interpretation
is needed; source defaults do not certify the physical bottles.

The preserved [condition validator](../../../src/pipeline/mas_schema.py) rejects
out-of-range values, changed operator settings, additive-lock violations,
compositions outside the stock polygon, and undiluted-stock mixing temperature
other than 25 °C. Projection to a nearby feasible point is not approval of the
original point or of the changed scientific test. Revise the candidate explicitly
and re-review it if values change. Check how a constraint-induced change affects
the controls, prediction and hypothesis; return upstream through main if necessary.

## Worked next point: informative without chasing the maximum

Every condition and outcome in this example is hypothetical, not a repository
measurement, an inferred operator setting or an actual recommendation. Assume
main selected a local claim that increasing bath temperature at fixed formulation
increases compression-estimated pore fraction. A composition-only explanation
predicts no systematic temperature effect under matched conditions. Assume the
supplied case establishes a reliable prior comparator at 14 wt% polymer, 8 °C
bath and the same remaining conditions below, with confirmed comparable material,
bath, stock and processing context.

Suppose the explicitly supplied hypothetical constraints use two-bottle stocks
with vertices (17, 0), (17, 4), (0, 0), additive lock 0 and the normal numeric
ranges. One proposed next condition to complete this local contrast is:

| Tunable | Hypothetical next value |
| --- | --- |
| `mixing_temp` | 25 °C |
| `bath_temp` | 15 °C |
| `pullcast_speed` | 10 mm/s |
| `nitrogen` | true |
| `coupon_to_bath_wait_time` | 120 s |
| `nips_bath_wait_time` | 1250 s |
| `polymer_wt` | 14 wt% |
| `additive_wt` | 0 wt% |

Hold the supplied operator materials/bath unchanged; their actual identities and
concentrations must accompany a real case. These illustrative values serve the
hypothetical matched contrast and lie within those stipulated constraints. They
are not an evidence-derived optimum or proof that a current physical bath exists.
No precise effect size or independent repeat count is inferred from the example.

The purpose is exploration of a distinguishing contrast, even if another
formulation is expected to have higher modulus. Keep quality/objective constraints
in view rather than maximize one metric by inventing weights. Prospective outcome
interpretation is:

- A reliable pore-fraction increase distinguishable from relevant comparison
  uncertainty favors the local positive-temperature relation over no temperature
  effect; it does not establish a specific pore-formation mechanism.
- An adequately measured opposite result challenges the selected local prediction.
  It does not by itself prove the composition-only mechanism.
- An apparently unchanged value that cannot be separated from uncertainty is
  inconclusive; so are invalid fitting evidence or unresolved comparator context.
  Do not label a failed fit as zero pore fraction.
- A modulus decrease can remain useful evidence alongside the predicted pore
  response. Evaluate the observed tradeoff and the selected claim rather than
  declare failure solely because modulus did not improve.

Actual decision thresholds and replication sufficiency require the case's
measurement/independent-variation evidence. If those are unavailable, qualify
what the single result can establish and ask for the needed evidence through main.
This proposal is one future condition against a stipulated existing comparator,
not a claim the new observation or an independent validation was performed.

## Worked rejection: feasible but unable to answer the question

If both polymer content and bath temperature change in the next point, a joint
response can still be measured, but cannot ordinarily isolate the selected
single-factor relation. A feasible stock mixture and a high predicted modulus
do not fix that design. Seek a matched contrast, or ask main to reconsider the
question using analysis/hypothesis review. Do not claim causal discrimination
from a visually appealing two-point trend.

If neither member of a required matched pair has been measured, propose one next
condition only with an explicit future comparator plan and limits on its immediate
interpretation. Do not list both as executable now, pretend the future control
already exists or assert the full comparison will be complete after only one run.

## Worked repeat and null design

Suppose a promising point has several coupons but no verified independent synthesis
repeat. Main may select the reproducibility question. Propose a new physical
synthesis retaining relevant formulation/material/bath/process controls, explain
how its outcomes would affect the earlier judgment, and distinguish later planned
repeats from this next observation. A single additional synthesis can inform
variability without proving reproducibility or supplying an arbitrary confidence
interval.

If current stocks or locks make the historical point infeasible, do not snap the
composition to a nearby point and call it the same repeat. Return the conflict
and its scientific consequence to main. A revised feasible point is a changed
test needing explicit design and review, and possibly changed hypothesis scope.

When selection is absent, a necessary comparator/source is unavailable, constraints
are unresolved, or no feasible condition can test the selected distinction,
return a null design with the reason and concrete next evidence need. Main may
hold while operator confirmation or analysis is obtained, and reconsider within
the target campaign when it arrives. If no informative work is justified under
the objective/feasible space, explain that assessment for main's stop decision;
this is not proof of a global optimum.

## Handoff and repair

Give main and design QA the selected claim, predictions/alternatives, original
comparator evidence, variables/controls, repeat rationale, purpose, exact conditions,
constraint basis, prospective criteria and remaining limits in a readable record.
Link useful artifacts without whole-report JSON copies or hash gates. Preserve
prior judgments and revision reasons; ask main to route upstream questions rather
than silently edit the hypothesis or accepted analysis. Re-review changed exact
values and consequential interpretations before main adopts a run design.
