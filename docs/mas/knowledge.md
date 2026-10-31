# Shared material and process knowledge

This guide defines shared material/process knowledge within the independently
reviewed scientific contracts. Actual scientific evaluation is requested; its
revised-contract live result remains **NOT_RUN** until recorded. Human review
will address scientific outputs before DCP. No Python persistence implementation
is introduced. Use the [workflow](workflow.md) for inquiry and
[source/output bindings](workflow.md#source-and-output-bindings).

## One inquiry, two kinds of scientific record

One persistent main coordinates analysis, hypothesis maintenance and design.
Shared knowledge holds material/process explanations that can survive a campaign;
round records explain what this observation changed and why. This is one MAS,
not a separate knowledge-making system or an agent's private operating memory.

Under an explicitly authorized output root, use
`data/knowledge/<material>/` for accepted shared claims and their navigable
history. Use `data/results/<campaign>/mas/rounds/<round-id>/` for the current
analysis, update proposal, scientific reviews, design, decision and useful
artifacts. In the planned test both paths are beneath the temporary test root;
project data and project knowledge are read-only. A material directory name does
not verify chemistry. Retain an inferred identity as inferred within its claims.

A small index can point to current claims, superseded meanings and source rounds;
file organization follows the material/question. No fixed file count, report
table, ontology, whole-report echo or hash framework is required. Link to round
evidence rather than copying entire reports into knowledge. An unchanged claim
needs no duplicate record merely because a new round occurred.

## What a useful claim explains

Connect a controllable process variable to a proposed process or structural
change, then to a property observable, within a stated material and process domain.
For example, an exchange-rate account and a polymer-matrix-state account may both
predict increased modulus but disagree about timing, architecture or matrix state. Name
the competing observable predictions and the evidence that could challenge each.
A rank relation can motivate this inquiry; it does not explain it by itself.

Keep evidence kinds distinguishable in readable prose:

- Original measurements and processing: exact source/condition, units, selection
  and what was actually acquired. Compression pore fraction is not an image of
  pore structure; a surface coverage photo is not a cross-section measurement.
- Published scientific knowledge: a source actually read, its material/conditions,
  what it supports and the limits of transferring it to this system. A citation
  or generic mechanism remembered by an agent is not a verified source.
- Proposed inference: which links are assumptions, why they are plausible enough
  to test, and what observations would distinguish alternatives. An unmeasured
  intermediate stays unmeasured even when its predicted property direction fits.

Preserve source precision, negative evidence, provenance and unknown controls.
Use bounded proposed/supported/refuted/inconclusive judgments, with scope and
reasons rather than truth labels. QA accepts reasoning within that scope; it
does not make a mechanism true. Uncertainty permits a useful explanatory proposal;
it does not justify either invented confirmation or avoiding explanations entirely.

## Worked explanatory competition — hypothetical

The following is an illustrative proposal for a **Polysulfone/PolarClean** system
with a fixed, explicitly specified bath, exposure and stock context. It is not a
repository result, a literature finding, or a universal concentration law. No
viscosity, exchange timing or cross-sectional morphology is asserted measured.

**H-K, proposed exchange-limited architecture:** increasing polymer concentration
from 14 to 16 wt% increases dope flow resistance enough to delay solvent/non-solvent
exchange under the chosen conditions; the resulting load-bearing architecture is
more compact. This proposal predicts higher modulus and lower compression-estimated
pore fraction, together with delayed exchange and a more compact cross-section
if those intermediate observables can be validly acquired.

The [producer](../../src/pipeline/curve_segmentation.py) computes stress from
load/area and strain from corrected displacement/thickness. Its elastic slope
is normalized modulus, not load-displacement stiffness. In a simple linear
comparison in consistent units, `E = k * thickness / area`, where `k` is the
load-displacement slope; retain the producer's unit conversion when using bar.
With unchanged material response and correct geometry, more total polymer or a
thicker specimen alone does not establish higher E. A changed solid fraction or
load-bearing network could change effective modulus, but that structural pathway
must be stated rather than inferred from mass/thickness alone.

**H-S, proposed concentration-driven matrix-state alternative:** under the fixed
post-treatment and test conditions of this illustration, higher initial polymer
concentration changes solidification/solvent retention so the load-bearing polymer
matrix retains less plasticizing solvent. Assume this less-plasticized state has
a higher intrinsic matrix stress-strain slope, even at matched pore architecture
and correctly normalized geometry. This is an explicit hypothetical material
pathway, not an asserted PSf/PolarClean concentration law or measured solvent
effect. Within this worked example only, “solid-loading account” names this
defined H-S matrix-state proposal, not greater total polymer amount by itself.
For a real main's undefined or different claim, request clarification or an
explicit scientifically reviewed linked revision before proceeding. Never
automatically substitute this example's H-S meaning for the selected claim.

H-S predicts lower retained solvent and a higher independently assessed matrix
modulus under matched conditioning, without requiring H-K's delayed exchange or
compact architecture. Neither a mass/thickness increase nor a compression-pore
shift alone tests those material-state predictions; the latter also depends on
curve processing. No residual-solvent assay or local matrix measurement is assumed
available. Valid absence of the specified solvent/matrix changes challenges this
H-S, rather than allowing it to explain any modulus gain.

Both predict higher modulus. Modulus alone therefore cannot distinguish them.
Delayed exchange and independently observed compact architecture, with comparable
matrix state, would favor H-K as the principal driver. Lower retained solvent
and independently higher matrix modulus at comparable architecture would favor
H-S. A separately authorized conditioning contrast that equalizes solvent content
could test whether the bulk-modulus difference diminishes, but only if architecture
and other consequential conditions remain comparable. That is a proposed test,
not an automatic treatment instruction or observation. Mass/thickness are control
metadata, not decisive support for either pathway. Mixed structural and matrix
changes may indicate combined explanations; missing intermediates leave the
pathway unresolved. Retain reliable adverse outcomes and alternative causes.

First search authorized existing curves, images, params and processing sources.
They may settle contact/coverage or actual settings without measuring viscosity
or morphology. If both alternatives still predict the same available outcomes,
request a feasible discriminating observable, refine the claim through review,
or report a narrower property test. New imaging/rheology/acquisition is planned
work requiring its own feasibility and operator authority, not an automatic
addition to the eight tunables. No numerical effect size or sufficient repeat
count follows from this example.

## Updating shared knowledge without erasing a round

Main supplies the current accepted knowledge locations and prior prediction to
analysis/updater. Analysis compares actual execution and outcomes with those
predictions; an unexecuted suggestion remains untested. The updater drafts the
evidence-linked change in the assigned round area: prior/current judgment, exact
new evidence, alternatives, contradiction and revision reason. Hypothesis QA
independently checks the draft against the shared prior meaning and originals.

Main alone accepts and publishes the scientifically reviewed change to the
authorized shared knowledge output. Authors draft; reviewers write only their
own findings and never repair the draft or canonical knowledge. An agent's broad
filesystem capability does not expand this ownership. If the invocation permits
no shared write, return a proposed update and leave publication pending.

The shared claim links to the source round/update and actual review; the round
links back to the accepted shared revision. Preserve the prior statement,
judgment and negative evidence. Stable meaning retains its ID; changed mechanism,
domain or prediction gets a linked new claim without inheriting support silently.
A held decision does not erase its hypothesis. A later campaign can reuse a
claim only within applicable material/process scope and after checking provenance.

If design QA later invalidates a premise, main marks affected shared judgments
as needing review and suspends dependent run recommendations. Return to analysis
and the affected author/QA pair; record the subsequent correction in both shared
history and its round. Unaffected evidence can remain accepted. A rejected draft
must not become the shared current status. Knowledge publication, test selection
and physical execution remain separate decisions.
