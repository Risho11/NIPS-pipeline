# Maintaining hypotheses without rewriting the evidence

This guide supports the explicitly invoked [hypothesis updater](../AGENTS.md).
Use the [data contract](../../../docs/mas/data-contract.md) and
[analysis methods](../../../docs/mas/analysis-methods.md) for measurement and
comparison semantics. The [workflow](../../../docs/mas/workflow.md) assigns main
hypothesis selection after independent review. These methods do not change the
preserved production adapter's invocation permissions or schemas.

## Keep observation, pattern and explanation distinct

An observation reports what a source supports: a condition, numeric outcome,
processing/quality context and comparison. A pattern relates observations under
stated conditions. An explanation proposes why the pattern occurs. Evidence for
a pattern need not identify its mechanism, especially when outcomes share curve
processing or several process variables changed together.

Before updating a hypothesis, recover its prior meaning, scope, predictions,
status and evidence. Ask which new observation actually bears on it. Check that
the actual experiment matches the predicted contrast, that required outcomes
exist, and that source identity/quality allows the comparison. Inspect original
pointers for important claims; accepted analysis is a reasoned input, not license
to ignore a visible contradiction or a missing control.

A useful explanation permits disagreement. Say what observable result would be
expected, under what controls, what alternative also predicts it and what could
distinguish those alternatives. A broad phrase such as "better morphology improves
performance" is too underspecified to adjudicate without defining the morphology,
observable and relevant conditions. Do not fill the gap with an invented
measurement or an after-the-fact success threshold. Request the needed analysis
or propose a clearly tentative testable explanation instead.

## Choose a maintenance action for a reason

| Action | When it is useful | What to preserve or clarify |
| --- | --- | --- |
| Retain | No relevant new evidence changes the earlier judgment, or the existing explanation is still the useful question | Same ID/meaning, earlier evidence and why no change is justified |
| Clarify | Wording or a source reference becomes clearer without changing what outcomes the claim permits | Same ID, revision note and unchanged substantive claim |
| Refine meaning | The mechanism, domain, relation or distinguishing prediction changes | Original claim/history; new linked ID for the changed meaning, without inheriting old support automatically |
| Split | An earlier compound explanation contains separable claims that evidence affects differently | Parent claim and why it was decomposed; linked distinct claims and their separate evidence |
| Add | Evidence motivates a genuinely different, testable alternative not already represented | New ID, motivating observation, scope, competing explanation and discriminating observable |
| Update status | Relevant evidence changes support or contradiction within the existing claim's meaning | Prior/new judgment, original evidence, contradictory observations and reason |

These are reasoning/editing choices, not new mandatory runtime status fields or
a generic ontology. Keep readable links between prior and current claims. Do not
rename an old refuted claim to make its contradiction disappear, change its scope
after an unfavorable result without a new linked claim, or duplicate synonyms as
new hypotheses. Several existing claims may remain useful without adding any.

## Evaluate evidence strength and status

**Proposed** means a motivated, testable explanation awaits adequate evaluation.
**Supported** means relevant evidence favors the stated claim within its scope;
it is not proof, verified future performance or automatic confirmation of a
mechanism. **Refuted** means reliable relevant evidence conflicts with the
claim's stated predictions/criteria within the tested scope. **Inconclusive**
means the available test/evidence does not justify the intended distinction.
An absence of relevant new evidence can leave any earlier status unchanged.

Consider comparison validity, observed uncertainty, independent synthesis coverage,
fit quality, provenance and competing explanations. An increase in modulus can
be compatible with many causes; it is not itself support for whichever mechanism
was proposed. A performance decline may match the prediction and supply support
for a scoped relationship. A missing outcome, unexecuted proposal or failed fit
is not a measured contradiction. A single reliable counterexample can matter to
a universal claim, while a probabilistic/local claim needs interpretation under
its actual uncertainty and criteria. Do not impose a universal significance test
or invent a posterior probability from a few rows.

Keep positive and opposing evidence together. If studies disagree, assess whether
they test the same claim with comparable materials, controls and processing, or
whether provenance/quality makes one uninformative. Do not merely count rows as
votes; duplicate exports/specimens do not create independent confirmation. State
what new evidence would change the current conclusion.

## Worked outcomes for one stable claim

All conditions, outcomes and identifiers in this example are hypothetical, not
repository measurements. H-T states: within a specified polymer/solvent/bath
system at fixed polymer content, exposure, stock context and adequate measurement
quality, raising bath temperature across a specified local comparison increases
compression-estimated pore fraction. It is a scoped pattern claim, not a proven
pore-formation mechanism. Its prediction and useful comparison criteria must be
recorded before evaluating the test; the designer later specifies the exact point.

- **Unchanged:** the new experiment changed casting speed without a comparable
  temperature contrast. Retain H-T's prior status and evidence. Explain that this
  result does not evaluate its prediction; do not add a replacement hypothesis
  just to record activity.
- **Supported:** a verified matched contrast, assessed under the stated criteria,
  shows the predicted increase with quality and uncertainty adequate for that
  conclusion. Update support for H-T's local pattern. Do not transfer that support
  to a nitrogen or phase-separation mechanism that was not discriminated.
- **Refuted in tested scope:** a verified matched contrast gives a reliable
  opposite result that conflicts with the stated prediction/criteria. Record
  the contradiction and scoped refutation. Do not quietly rewrite H-T to predict
  a decrease or narrow away the tested conditions under its existing ID.
- **Inconclusive:** temperature and polymer content both change, bath identity is
  unresolved, the relevant outcome is missing, or uncertainty prevents the
  claimed distinction. Explain the concrete gap. The result may still contain
  useful observations, but does not isolate H-T's temperature relation.

These are alternative evidence situations, not a required sequence of status
transitions. If prior support remains and a new ambiguous test adds no relevant
contradiction, retain/qualify that support rather than mechanically downgrade it.
Record why the ambiguous evidence does not settle the claim.

## Worked competition, refinement and a return to analysis

Suppose a candidate attributes a modulus increase to temperature-induced pore
structure while polymer content changed too. A higher-solid-content explanation
also fits the observation. Request matched comparisons through main before
calling either explanation supported by that contrast. Ask analysis which rows
are comparable, which outcomes are reliable and whether stock/bath differences
remain. Hypothesis QA can find this inference gap even if the numeric contrast
was already accepted as descriptive analysis.

If the mechanism cannot be distinguished from a simpler composition explanation,
retain it as tentative where motivated and state the competing prediction. Do
not require a new hypothesis if an existing composition claim already represents
the alternative. If an earlier compound H-C claimed both a local property pattern
and a specific mechanism, preserve H-C and propose linked claims separating those
meanings when that separation matters. Their evidence/status can differ. Do not
let the supported pattern silently certify the mechanistic component.

If new evidence motivates a narrower temperature range or changed bath context,
that changes which observations could refute the claim. Preserve the old claim
and contradiction, give the revised meaning a linked new ID, and assess its
support on the evidence that actually tests it. A clarification of a misspelled
source label without changed meaning can remain under the existing ID.

Send main the revised candidate, evidence/analysis paths, original and changed
judgments, alternatives and the comparison needed to distinguish them. Main
selects a hypothesis after hypothesis QA. Suggest the type of evidence needed,
not exact execution conditions or an unreviewed explore/optimize/repeat decision.

## Keep history usable and know when to stop

Use the hypothesis-update research record and linked earlier revisions to keep
stable claim meaning, prior/current status, evidence, opposing observations and
revision reasons navigable. Flexible prose/tables are sufficient; no whole-report
JSON echo, duplicate result.json or hash gate is required by this target method.
Do not edit previously accepted source records to make the new account consistent.

Return to analysis through main when adjudication depends on a source identity,
comparison, fit exclusion or calculation that has not been resolved. Identify the
specific question and how its answer would change the hypothesis judgment.
When existing evidence cannot decide, an explicit inconclusive or unchanged
judgment can be complete useful work. Do not manufacture a mechanism, new entry
or proof of improvement to finish. Independent hypothesis QA checks the update;
main then chooses a test target or none, followed by prediction/design and final
decision under the workflow.
