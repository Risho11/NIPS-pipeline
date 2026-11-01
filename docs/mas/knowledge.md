# Shared material and process knowledge

Use the [workflow](workflow.md) for inquiry and
[source/output bindings](workflow.md#source-and-output-bindings), and the
[data contract](data-contract.md) for original evidence and measurement meaning.
Scientific usefulness must be judged from actual inquiry outputs; document QA,
well-formed files and careful uncertainty labels do not establish it. These
contracts introduce no production Python persistence implementation.

## One inquiry, persistent claim records

One main coordinates analysis, knowledge maintenance and experiment selection.
Shared knowledge holds material/process claims across campaigns; a round explains
which observations changed what and why. It is not a separate agent system or
an agent's private operating memory. Main alone publishes scientifically reviewed
changes within its authorized output root.

Use `data/knowledge/<material>/index.md` as navigation and concise current context,
with each stable claim in `data/knowledge/<material>/hypotheses/<stable-ID>.md`.
The index points to those records, their current bounded judgments and open
questions; do not embed all claim bodies or full reports in the index. Each claim
record preserves its meaning/scope, motivation, evidence and counterevidence,
current judgment and revision history, linked to source rounds and actual review.
Internal prose/layout is flexible; this path convention is not a hypothesis quota,
fixed report schema, ontology or hash framework. A material directory name does
not verify chemistry.

Round analysis/update/review/design/decision artifacts live under the authorized
`data/results/<campaign>/mas/rounds/<round-id>/`. Link the round's proposed change
to the shared claim and the accepted claim revision back to its evidence/review.
Do not copy the entire knowledge base into every round. In temporary sessions both
round and shared writes stay beneath the bound temporary root; the project stays
read-only under the task contract and actual permissions must be reported.

If older accepted knowledge embeds claims in its index, preserve that accepted
version/history and relocate exact meanings, evidence and statuses to stable-ID
files before publishing a navigable index. Review semantic preservation; relocation
is not new evidence or permission to rewrite an old claim. A new test root inherits
no acceptance silently; any deliberate seed needs provenance and authorized scope.

## Initialize, then learn from observations

When no applicable bank exists, main asks the same hypothesis author and distinct
QA to initialize it from material/process/measurement constraints, articulated
physical reasoning and scientific sources actually read, before current outcomes
are examined. Reviewed current analysis is not a prerequisite to this bootstrap.
Consider meaningful process stages and interactions beyond the latest temperature/
bath story, without one claim per variable or a prescribed bank size.

Preserve the initial meanings, conditional directions, prerequisites, rival
predictions, sources and actual outcome exposure before revealing data. Do not
follow worked examples containing withheld campaign outcomes, old science/status reports or data-derived
claim files during an outcome-withheld bootstrap; supply allowed definitions or
passages separately. If a participant already knows results, disclose that rather
than claiming an unexposed prior. Existing data-derived claims retain their IDs,
history and retrospective origin; never erase or relabel them as initial theory.

After authorized observations arrive, analysis and distinct review inform updates,
revisions and new ideas. Theory can be wrong; challenge it rather than force-fit
results. Mark data-generated additions as such, distinguish exploratory use from
an independent confirmatory test, and preserve old meanings when revising. Even
an outcome-withheld reveal of historical data remains a retrospective evaluation,
not a new prospective experiment. External-system evidence is not target-system
confirmation, and using the same evidence to propose and assess a claim adds no
independent support.

Reuse an applicable bank across rounds/campaigns. Read its index and relevant or
changed claim records, not the whole bank and bootstrap again each turn. Reconcile
new theory and older retrospective accounts explicitly without hiding origins or
counting duplicate ideas/evidence as corroboration. Initial publication and later
observation updates remain separate from main's next-test selection.

## Reasoning before and after observations

Separate a measured observation, a testable process-effect proposition and a
proposed pathway explaining that effect. A variable → process/structure → property
chain is useful only when the particular links and direction have a reason in
the material/process context. Cite original comparisons, a physical argument with
stated assumptions or an applicable scientific source actually read. Literature
is optional; invented citations and generic remembered mechanisms are not evidence.

Explaining an increased modulus by saying a change “may make the network/matrix
stiffer” merely restates the response unless the account says why that intermediate
and direction deserve attention. Consider process sequence, persistence of a
preparation state, contrary observations and the strongest credible rival. An
unconfirmed mechanism can be worth testing, but proposed/inconclusive labels
alone do not make it a useful selection rationale.

Compare predictions for available or feasibly obtainable observations under the
same contrast. If pathways have the same available property predictions and differ
only in unavailable assays, retain them as unresolved possible accounts. Do not
present a property screen as their mechanistic discriminator. A narrower process-
effect test can still be worthwhile when its result changes a process decision;
state its limited inference and why it takes priority over practical alternatives.
Keep contextual and combined causes possible when supported, without creating a
mandatory hypothesis for each variable or a new mechanism every turn.

Preserve original precision, provenance and inferred chemistry. Compression pore
fraction is not an image of structure; coverage photos do not measure a cross-section.
A numeric modulus and passing fits do not by themselves certify material quality.
Evaluate each claim/endpoint and shared quality dependencies using the data contract.

## Hypothetical pathways illustrate form, not a default answer

For illustration only, suppose a PSf/PolarClean concentration change under fixed
bath/exposure/stock context motivates H-K: changed dope flow resistance → delayed
exchange → a more compact load-bearing architecture → higher modulus/lower
compression-pore estimate. H-S instead proposes changed solidification/retained
solvent → less-plasticized polymer matrix → higher intrinsic matrix slope at
comparable architecture. These directions and intermediates are assumptions, not
repository observations, literature findings or universal concentration laws.
The example supplies no case-specific motivation or priority by itself.

The [producer](../../src/pipeline/curve_segmentation.py) normalizes load by area
and displacement by thickness. In consistent units, `E = k * thickness / area`,
with `k` the load-displacement slope; retain the producer's bar conversion.
More total polymer or thickness alone does not establish increased normalized E.
A structural or matrix-response change must be specified. Within this example
only, “solid-loading account” denotes H-S's defined matrix-state proposal. A real
main's different/undefined meaning requires clarification or an explicitly reviewed
linked revision, never automatic substitution.

Both pathways predict higher modulus, so that outcome alone does not discriminate.
Exchange/architecture evidence at comparable matrix state could favor H-K; retained-
solvent and independently assessed matrix-response evidence at comparable architecture
could favor H-S. A separately authorized conditioning comparison might probe the
matrix account only if architecture and other consequential conditions remain
comparable. Mass/thickness alone is not decisive support. Mixed changes leave
combined causes possible; reliable absence of a pathway's specified changes
challenges that account. No solvent, matrix or morphology measurement is assumed
available or authorized. Without it, a justified concentration-effect screen can
inform a process relation while both pathways stay unresolved.

## Review, publish and preserve history

Bootstrap author/QA can work before current observations; later analysis examines
actual outcomes against the preserved predictions and useful available contrasts.
The updater drafts the round's proposed knowledge changes,
retentions, rationale, rival predictions and recommended question priorities.
Distinct hypothesis QA checks motivation and usefulness as well as source truth,
status and identity. Main reads actual artifacts/findings and makes its own value
judgment before publication/selection; PASS is not a command to choose a claim.

Authors draft only in assigned areas; reviewers keep separate findings and never
repair canonical knowledge or author work. Main publishes accepted changes to
the claim files and index, retaining previous meanings, judgments, negative evidence
and round links. If no shared-write authority exists, return a pending proposal.
Stable meaning retains its ID; a changed mechanism, scope or prediction requires
a linked new claim without silently inherited support. No new measurement means
no fabricated confirmation/refutation. Working priority or a better question can
change with improved reasoning while empirical status remains unchanged.

If design or new evidence invalidates a premise, mark affected judgments as needing
review, suspend dependent run recommendations and return to the appropriate
analysis/author/QA work. Re-review affected reasoning, preserve the correction in
shared history and its round, and retain unaffected evidence. A rejected draft
never becomes current knowledge. Publication, selection and physical execution
are separate decisions; scientific review grants no hardware authority.
