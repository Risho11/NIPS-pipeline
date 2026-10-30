# Running an evidence-led campaign inquiry

This guide supports the [campaign-main role](../AGENTS.md), activated only by an
explicit experiment-main assignment. Domain facts and calculations belong in
the shared [data contract](../../../docs/mas/data-contract.md) and
[analysis methods](../../../docs/mas/analysis-methods.md). The
[workflow](../../../docs/mas/workflow.md) defines collaboration and the unmigrated
production boundary. These are target scientific methods, not permission to
start a model call, device or production campaign.

## Recover the question, not just the previous stage

On continuation, follow the current campaign's readable index to the latest
accepted records, artifacts, review findings and open questions. Check whether
new evidence or operator constraints have arrived. Earlier conversation is useful
context, but verify consequential claims against the supplied current sources.
Do not treat the newest file modification time as acceptance or the next numbered
report as the next necessary action.

Connect the latest measured experiment to the prior design's exact conditions,
prediction, comparator and criteria. A suggestion on source row A can propose B;
A's measurements do not test B. If actual execution differed or its identity is
unclear, ask analysis what remains comparable and label the prediction unmatched
where necessary. If no prior prediction exists, begin with a retrospective
observation instead of inventing one.

Ask what evidence could change the decision now. A high modulus with unresolved
fit quality may need original-curve review before another synthesis. A robust
result with unknown between-synthesis variability may need a repeat. A low
result that separates competing explanations may be scientifically valuable.
This question sets the work, rather than a preset optimization/exploration label.

## Give specialists a problem they can solve

A useful delegation describes the question, evidence and its purpose. For example:

> Determine whether the apparent bath-temperature association survives matching
> polymer concentration and bath composition. Use the supplied campaign CSVs,
> original fit evidence and previous prediction at the linked locations. Identify
> comparable observations and important missing controls; choose the calculation
> or figure that resolves the question. Write artifacts only in the assigned
> analysis area. Return a bounded interpretation, source/artifact paths and the
> evidence still needed. This will determine whether a temperature test is
> justified or we should first investigate another explanation.

Pass actual case paths, not unresolved placeholders. Include current material/
stock constraints where relevant, accepted prior hypotheses, existing findings
and the available work-area permissions. Supply the role instructions and stable
shared guides once when starting a fresh specialist; in follow-ups point to
changed inputs and the specific unresolved question. Reuse useful sessions rather
than discarding context at each handoff. A specialist may ask main for another
source, calculation or clarification; main obtains it or records its absence.

Send the corresponding independent reviewer the original evidence and author
artifact paths, the claims at issue, and current constraints. Ask it to verify the
inference and source calculations and seek counterexamples, not merely approve
the wording. It must remain a different agent from the author. Return findings
to the author, inspect the response, and obtain a new judgment on consequential
revisions. No scientific review is completed by switching main's persona.

## Select the hypothesis and the purpose of the test

Have hypothesis maintenance distinguish retained, supported, refuted and
inconclusive explanations using the reviewed observations. Keeping a hypothesis
unchanged is legitimate; a new hypothesis is not required each turn. After its
independent review, main selects the test target and explains its priority over
alternatives. Selection is not an assertion that the hypothesis is already true.

Consider how much the feasible experiment could change belief, whether the
comparison is identifiable, the reliability of existing evidence, the relevance
to the campaign objective, and actual resource constraints supplied by the
operator. Do not invent numerical utilities or weights. If no candidate can be
tested meaningfully, selection can be none, with a request for evidence or hold.

| Purpose | Reason to choose it | Question for design |
| --- | --- | --- |
| Explore | Existing evidence leaves alternatives that a new contrast could separate | Which feasible contrast produces different predicted observations under the competing explanations? |
| Optimize | A sufficiently supported local relation or tradeoff merits a targeted test | What improvement or tradeoff is predicted, relative to which comparator, and what result would challenge the local explanation? |
| Repeat | Independent variability or a proposed validation matters more than moving conditions | What is repeated physically, what controls and stock context are retained, and how will outcomes change our judgment? |

These purposes can overlap. State the primary evidence need rather than force an
exclusive taxonomy. A figure or a feasible point alone does not justify the choice.
Require predictions and support/refutation/inconclusive criteria before endorsing
the final design. Main chooses the next experiment with scientific QA; it does
not silently rewrite the designer's conditions after review.

## Worked return: design QA discovers a confounder

Hypothetical inquiry: analysis associates higher bath temperature with higher
modulus, hypothesis maintenance retains a temperature explanation, and main asks
for a warmer-bath test. Design QA discovers that the proposed historical
comparator used a different polymer concentration or bath-solvent content.

Treat this as an analysis/comparability issue, not just a wording repair in the
design. Mark the temperature attribution, its hypothesis support, selection and
dependent design/decision as needing review. Keep the original observations
available; they may remain numerically correct.

Return the confounder to the analyst with the affected row identities and ask
whether a matched comparison exists. Analysis QA checks that revised comparison
against the originals. If no match exists, hypothesis maintenance may qualify
support as inconclusive while retaining the explanation as testable. Hypothesis
QA checks that inference; main then reconsiders selection. A feasible matched
control may still justify exploration, with predictions that distinguish the
explanations and new design QA. Alternatively, hold if the necessary bath context
is unavailable. Preserve previous judgments and why they changed; do not leave
the old run recommendation active.

An editorial correction that changes no evidence, interpretation or conditions
does not reopen all scientific work. A changed comparison, uncertainty estimate,
hypothesis claim or execution value does require review of its affected
dependents. Main explains that scope in the index rather than using hashes to
accept or reject the inquiry automatically.

## Worked choice: repeat instead of chasing a new maximum

Suppose a promising modulus/pore-fraction tradeoff has several specimens but no
confirmed independent synthesis validation. This is a hypothetical decision
situation, not a claim that a particular repository row was validated. Main asks
analysis to establish the sampling units and hypothesis maintenance to distinguish
within-synthesis consistency from reproducibility. Small specimen SD is not
enough to make the latter claim.

Main may retain the existing explanation and select a repeat as its next test.
Design must specify a new physical synthesis with relevant controls, feasible
conditions under current stocks and what agreement or disagreement would mean.
If the historical point is now infeasible, changing it creates a different test;
return the question for redesign and review instead of calling the changed point
an exact repeat. The outcome may reduce confidence or reveal batch sensitivity
even if performance declines. Main should explain why this information is more
useful now than testing another high predicted point.

## Worked hold and reconsideration

Suppose design requires distinguishing 0 wt% from 10 wt% bath-solvent context,
but the supplied current operator context is unresolved. Record hold with no
executable conditions and the concrete resumption condition: obtain the actual
prepared bath identity/concentration and review the affected comparison/design.
Do not infer the physical bath from a source-code constant.

When operator-confirmed evidence arrives, main can reopen the question in the
same campaign's target workflow. Link the new evidence, preserve the held
decision, assess which conclusions change, and obtain the affected scientific
reviews before a new decision. Hold is not automatic stop and does not require
erasing QA history or starting a new campaign. The existing production cache
does not implement this flexibility; do not edit its checkpoints to simulate it.

Stop is appropriate when further work is not justified within the current
objective and feasible space, with reasons such as exhausted informative tests
under supplied constraints. It is not a claim that all possible material/process
conditions have been searched. A later changed objective is a new decision
context to assess explicitly, not a license to overwrite past records.

## Follow artifacts and close the decision

Use a small readable index in the authorized scientific work area to point to
the four accepted report locations, current revisions, supporting calculations/
figures, actual QA findings and outstanding questions. Existing records can serve
this purpose; no separate database, immutable ledger or duplicate result.json is
needed. Drafts are distinguishable from accepted conclusions. Preserve prior
judgments by revision notes or retained earlier versions; choose the organization
that makes the current case easy to follow.

Before run, main should be able to explain what the measurement says, what
hypothesis is selected and why, what is predicted, how the feasible test could
change the judgment, and which distinct scientific reviewers assessed the
relevant current claims. Return the exact reviewed conditions and referenced
reasoning; never claim the proposed performance is measured. If material support
remains unresolved, choose hold or stop with no executable conditions. Ordinary
scientific uncertainty can motivate a run test when the design answers it.

For the isolated pilot, run is a recommendation only: no submission occurs.
Physical execution belongs to the separately authorized system/operator boundary.
