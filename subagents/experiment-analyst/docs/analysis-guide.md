# Answering an experimental analysis question

This guide supports the explicitly invoked [analyst role](../AGENTS.md). Use the
shared [data contract](../../../docs/mas/data-contract.md) for actual fields,
units, processing and source identity, and
[analysis methods](../../../docs/mas/analysis-methods.md) for common calculations.
The [workflow](../../../docs/mas/workflow.md) explains main's decisions and
scientific review. These methods describe target/pilot work; actual sandbox and
output requirements still apply.

## Turn the inquiry into an evidence comparison

Restate the uncertainty in a form the supplied data can address. For example,
"did the temperature change behave as predicted?" first requires the previous
prediction, exact proposed conditions, actual execution identity and comparator.
If only a new aggregate row exists, do not assume it is the proposed experiment.
Ask main to resolve that link or limit the comparison to observed records.

Locate numeric outcomes in the original table and inspect its header. Trace
promoted values to the appropriate aggregate version when quality or exclusion
could matter. Use specimen/curve evidence for within-synthesis or fitting claims,
not aggregate SD as a substitute. Treat warm-start history as another source to
assess, not automatically another independent experiment. If source identities
collide, disclose the collision and ask main for provenance before counting both.

Choose comparators that answer the question. Identify which variables are matched,
which changed and which are unknown. An exact condition-name match is a clue,
not proof of physical identity or identical materials. If matched evidence is
absent, describe the joint change and competing explanations rather than force a
single-factor effect. Do not backfill historical material settings from current
operator context.

## Select a calculation or artifact for a reason

When main asks for a process explanation, trace the proposed intermediate rather
than ending at a property ranking. Use the hypothetical concentration competition
in [knowledge.md](../../../docs/mas/knowledge.md): modulus agreement alone fits
both exchange-limited architecture and the defined matrix-state alternative.
H-S needs evidence for its solvent-retention/matrix-response pathway; increased
mass/thickness alone cannot establish increased normalized modulus. Determine
whether original
curves, photos, params or plots address their different predictions; do not treat
a coverage image as cross-sectional evidence. If no such observable exists within
the authorized sources, identify the specific gap and a useful narrower comparison.

Draft evidence for the round's knowledge update, not a canonical status change.
Compare actual outcomes with recorded prior alternative predictions. Preserve
unfavorable observations, source precision and warm-start selection/overlap so
updater and independent QA can assess what changed. Your analysis and scripts
belong to your assigned round; main alone publishes shared knowledge.

If the question concerns a measured difference, calculate the contrast at source
precision and report units, direction, comparator and inclusion choices. A
relative contrast needs a meaningful nonzero denominator. If the question is
repeatability, establish which observations are independent syntheses before
using their variation; show the outcomes when independent coverage is sparse.
Check counts by property where available, not just one count for a whole row.

If the question concerns quality, compare pre/post-discard interpretations and
contributing specimens. Inspect fit breakdowns and original curves where they
could change the conclusion. A missing successful fit means unavailable evidence
for that property, not zero physical performance. If a measurement/fit concern
cannot be resolved from supplied sources, distinguish that from evidence against
the material itself and request the necessary source through main.

Choose the representation that makes the unresolved comparison visible. A
condition table can reveal simultaneous changes or unknown controls. A stratified
scatter can reveal that an apparent trend follows composition groups. Specimen
points plus a source fit overlay can clarify a suspect estimate. Stratification
alone does not remove confounding when there is no matched contrast. Do not make
all of these artifacts by default.

For an authorized script/figure, record its input paths, exact row selectors,
properties, units, processing variants, exclusions and transformations. Inspect
the actual rendered output where possible; verify that missing values were not
plotted as zero, axis/group labels mean what the text claims, and specimen SD was
not relabeled as synthesis uncertainty. Record command outcomes truthfully. If
visual inspection is unavailable, state which conclusions rely only on the table
or computation. Existing deterministic plots are not a substitute for checking
their underlying fields.

## Worked handoff: modulus changes with temperature and polymer content

Hypothetical example, not repository measurements:

| Record | Polymer wt% | Bath temperature (°C) | Modulus (bar) |
| --- | --- | --- | --- |
| A | 14 | 8 | 180 |
| B | 16 | 15 | 230 |

Main asks whether higher bath temperature explains the increased modulus. The
observed B-minus-A contrast is 50 bar. Dividing by the 7 °C difference would give
about 7.14 bar/°C, but would falsely attribute the full joint change to temperature.
Both polymer content and temperature changed; bath/material/stock context and
quality also need checking.

Begin with a condition comparison table. Search the supplied evidence for 14 wt%
at both temperatures or 16 wt% at both, holding other consequential context
comparable. If those observations exist, make the matched contrast and, if useful,
a plot grouped by composition to expose whether the earlier pooled trend holds.
If they do not, the defensible result is a combined observed change with no
isolated temperature effect. Specify the missing matched contrast and what
competing explanations it could distinguish, without selecting final conditions.

That conclusion does not prohibit proposed process reasoning. A concentration-
driven exchange account and the explicitly defined matrix-state account can be
motivated while
remaining unconfirmed. State their different predicted process/property outcomes
and ask which source could discriminate them. Search authorized raw directories
and params/plot_source linkage before asking for another measurement; if a source
exists, read or inspect it rather than merely listing it as available.

Send the source row identities, checked controls, comparison/artifact paths and
qualified conclusion to main and analysis QA. Suppose QA notices that A's bath
solvent content is unknown. Return to that source, revise the comparability claim,
and explain whether the contrast remains descriptively valid. Request the bath
record through main if needed. A repair can retain the 50 bar observation while
withdrawing temperature attribution. Main can then reconsider hypotheses/design;
the analyst does not quietly adopt a new test point.

## Worked response to an exclusion finding

Use the shared methods guide's explicitly hypothetical 100, 110, 300 bar case:
pre-discard mean 170 bar, passing-only mean 105 bar after the extreme estimate's
fit failure. If QA finds that a draft compared the first mean against a
post-discard comparator, inspect both source variants and revise the comparison
at a consistent documented processing basis. Show sensitivity where the choice
changes ranking rather than choose the attractive version.

Review other figures/tables that consumed the same selected values. If original
curves cannot be obtained, retain the documented sensitivity and the unresolved
fit explanation. Do not invent a pore-fraction reconstruction from empty specimen
fields or rewrite stored measurements. Main may need processing evidence or
another physical measurement; analysis alone cannot guarantee reproducibility.

## Prediction agreement is different from improvement

Hypothetical prediction: changing a process increases compression-estimated pore
fraction while reducing modulus, with a specified comparator and criteria. If
that pattern is observed, lower modulus is not automatically a failed prediction.
Check execution, quality and criteria first; then report agreement, disagreement
or inconclusive evidence for the predicted observations. Formal hypothesis status
and selection remain with hypothesis maintenance/QA and main. Shared curve-fit
origins and alternative explanations may limit what agreement implies about a
mechanism.

When criteria were never stated, label a retrospective comparison; do not invent
a threshold after seeing the outcome. When the required outcome is missing,
report the relevant part as unassessed rather than borrow a historical value.

## Return a usable bounded answer

Separate what was observed, what interpretations remain plausible and what would
change the conclusion. Link original sources and artifact locations with enough
calculation detail for independent checking; no full-report JSON copy is needed
by the target method. Explain important revisions and which downstream claims
may be affected.

Stop adding analysis when no feasible check of available evidence could change
main's decision. Return the concrete missing evidence instead of generating more
plots to imply certainty. A limited but correct conclusion can be sufficient for
main to request a discriminating design or hold. Unresolved consequential errors
need repair and independent review; honest scientific uncertainty stays visible.
