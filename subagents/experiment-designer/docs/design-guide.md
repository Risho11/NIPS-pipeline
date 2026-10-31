# Choosing a test that can change a scientific judgment

Use this guide as the explicitly invoked [experiment designer](../AGENTS.md).
The shared [data contract](../../../docs/mas/data-contract.md) defines measurement,
material and stock semantics; [analysis methods](../../../docs/mas/analysis-methods.md)
defines comparison limits. The [workflow](../../../docs/mas/workflow.md) retains
main's selection and final decision. These target/pilot methods do not migrate
the preserved production adapter or authorize execution.

## Translate the selected claim into distinguishable outcomes

Recover main's exact selected claim from `hypotheses/<stable-ID>.md` through
shared `index.md`, its evidence/review and why this question takes priority.
Use [knowledge.md](../../../docs/mas/knowledge.md) for meaning/history. Do not
silently substitute a pathway or narrow its meaning to rescue an attractive point.

State the intended inference: a process-effect contribution or a pathway distinction.
If rival pathways predict the same available properties, a property-only test
cannot distinguish their intermediates. A useful limited effect screen can still
proceed when its comparator/outcomes answer a justified process question; leave
the mechanisms unresolved. If another observable is essential, check whether it
exists or is feasibly authorized, or return the claim/question to main. Do not
prescribe new assays, hypotheses or coordinates merely to appear more explanatory.

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

## Worked next point: concentration explanations with different predictions

Every condition, outcome and intermediate in this example is hypothetical, not
repository evidence, a material law, installed stock confirmation or an actual
recommendation. Main selects H-K, the proposed PSf/PolarClean exchange-limited
architecture account in [knowledge.md](../../../docs/mas/knowledge.md), against
H-S's proposed matrix-state account. Both predict higher normalized modulus as
polymer concentration rises. H-K predicts delayed exchange and more compact
architecture with lower compression-estimated pore fraction; H-S specifically
predicts changed solvent retention/plasticization and increased intrinsic matrix
modulus at comparable architecture. More total material or a thicker membrane
alone is not that pathway. Recover the full
proposed meanings and limits before using these predictions.

Assume the case explicitly supplies a reliable 14 wt% polymer, 8 °C bath comparator
with all remaining settings below matched, fixed PSf/PolarClean/no-cosolvent
materials, a specified unchanged bath composition, and comparable stock/acquisition
context. These are assumptions for the example; locate real comparator evidence
before offering a real point. Suppose stocks are the supplied triangle (17,0),
(17,4),(0,0), additive lock0, with normal source numeric bounds.

| Tunable | Hypothetical next value |
| --- | --- |
| `mixing_temp` | 25 °C |
| `bath_temp` | 8 °C |
| `pullcast_speed` | 10 mm/s |
| `nitrogen` | true |
| `coupon_to_bath_wait_time` | 120 s |
| `nips_bath_wait_time` | 1250 s |
| `polymer_wt` | 16 wt% |
| `additive_wt` | 0 wt% |

Only concentration changes relative to the stipulated comparator. The proposed
(16,0) composition is diluted polymer stock, feasible as 16/17 stock plus 1/17
solvent by mass; the undiluted-stock special rule is not triggered. Keep all
actual material/bath constraints explicit; no dispensing instruction or physical
execution follows. This point explores a distinction rather than chasing the
largest predicted modulus. No exact gain, tolerance or sufficient repeat count
is invented.

First inspect authorized existing curves/photos/params/processing evidence and
warm-start comparisons to identify what is already measurable. If valid exchange
timing, solvent/matrix-state or structural measurements exist, evaluate their
applicability. Surface
coverage images are not cross-section images; compression pore estimates cannot
supply exchange kinetics. Additional rheology, time-resolved observations or
structural or residual-solvent acquisition would be a separately authorized
measurement plan, not a
new tunable or an observation assumed already available.

Prospectively distinguish:

- Delayed exchange and independently compact architecture with higher bulk
  modulus, at comparable matrix state, favors H-K as the principal driver within
  the controls. A pore estimate alone does not image that architecture.
- Lower retained solvent and independently increased matrix modulus at comparable
  architecture favors the stated H-S. Mass/thickness increase alone does not.
  A conditioning contrast that equalizes solvent content could further test the
  predicted reduction of the bulk-modulus difference only if architecture and
  other conditions remain comparable and that measurement/treatment is authorized.
  Missing solvent/matrix evidence leaves this pathway untested; reliable absence
  of its specified changes challenges H-S.
- Mixed architecture and matrix changes may support combined explanations.
  Neither a favorable property direction nor a mass/thickness change proves an
  exclusive pathway. Retain contrary property and intermediate observations.
- Property changes alone can test the scoped property predictions but leave
  intermediate pathways unresolved. If both accounts fit all available outcomes,
  request another discriminating observable or narrow the inference through main.
- Invalid acquisition, missing outcomes, unmatched execution or unresolved
  uncertainty leaves the affected distinction inconclusive. Preserve valid adverse
  evidence rather than using uncertainty to dismiss every unfavorable result.

Explain why this next synthesis and comparison would be informative under actual
resource/quality constraints, and what it alone cannot establish. An additional
matched observation or independent repeat may be needed; label it future planned
work. No generic repeatability question replaces the selected process explanation
unless main explicitly reselects after affected review.

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
