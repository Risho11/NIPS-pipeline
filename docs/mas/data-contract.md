# Experiment evidence and decision contract

## Purpose and implementation boundary

Use this guide to identify what was measured, which observations can be compared,
and what a proposed experiment may change. Use [analysis methods](analysis-methods.md)
to choose calculations and figures for a scientific question. Numeric source
measurements take precedence over generated narrative. Retain their stored
precision for calculations. Missing, nonfinite or unavailable values are unknown,
not zero and not permission to invent a replacement measurement.

The target MAS lets campaign main direct analysis, maintain and select hypotheses,
revisit upstream judgments, and choose run, hold or stop. Specialists and their
independent scientific QA support those decisions. Readable Markdown records cover
integrated inquiry (or split analysis/update), design and final decision, without
a fixed report-file quota. Main applies the workflow's concrete split/rejoin
criteria; unified inquiry `hypothesis-qa` covers both split contributions. Any
additional review uses a fresh instance of that role for a named unresolved issue
under the workflow, not an automatic analysis-QA stage. Report locations and revision reasons trace evidence
without whole-report JSON echoes or report-hash gates.

The [Python runtime](python-runtime.md) binds the existing repository, a campaign
and a material, with one persistent scientific Main and native review/publication.
The caller separates original measurements from current-attempt outputs. It never creates
scientific observations or grades report claims; actual permissions and execution
need independently recorded evidence.

Shared material/process claims and their bounded evidence judgments follow
[knowledge.md](knowledge.md); round reports explain the changes rather than
duplicating canonical knowledge. Bind instruction/evidence sources separately
from authorized scientific outputs using the workflow's
[source/output principles](workflow.md#source-and-output-bindings). A temporary
scientific agent writes only its assigned current attempt under
`data/results/<campaign>/mas/rounds/<operation>/attempt-<n>/`. Python publishes
reviewed topics at `data/knowledge/<material>/` and exact adopted records plus the
campaign `.mas-state.json` in the existing Git. Inputs/source/report bindings are
repository-relative and digest-bound. Raw measurements/media are excluded from
MAS publication; no agent stages/commits or edits canonical topics/native state.

For outcome-withheld initialization use only approved protocol/measurement
facts and constraints. The evidence-discovery/history sections and their linked
tables, plots, notebooks and prior reports are for authorized observation turns;
do not follow them to supply old outcomes or causal answers as priors. A supplied
outcome-free context can replace reading outcome-bearing source sections.

## Locate the evidence before interpreting it

Campaign tables live under `data/results/begins_<campaign>/`. Begin with the
supplied campaign and source paths, not whichever CSV looks most recent.

| Evidence | Meaning and useful fields | How to use it |
| --- | --- | --- |
| `reps.csv` | Specimen processing rows: `name`, `Trial`, `Thickness`, `Elastic Modulus`, `Good Fit`, `Good Fit Score`, `Good Fit Breakdown`; pore-field caveat below | Inspect within-synthesis dispersion and fit failures; trace original specimens |
| `agg.csv` | Condition aggregates, potentially `name_preDiscard` and `name_postDiscard`; property `Mean`/`SD`, `Discarded Fit Reasons` | Compare processing variants and what exclusion changes |
| `llm.csv` | Selected aggregate rows with clean condition names, parameters, measurements and narrative/proposals | Use selected versions for campaign comparisons, retaining aggregate provenance |
| `data/raw/<condition>/` | Original `Specimen_*.csv` and, where available, `params.json` | Trace sample/zero pairing, acquisition and recorded conditions |
| `data/plots/` | Processing plots and sometimes `plot_source.json` | Inspect fitting evidence; confirm the producing input condition |
| `data/warm_start/*.csv` | Historical exports; may include `source_csv`, `campaign`, `source_name`, `chemistry`, `validation_status`, stock and time provenance | Retain historical identity, completeness and material limitations |

Concrete schema examples are the
[October LLM table](../../data/results/begins_2026-10-15/llm.csv),
[aggregate table](../../data/results/begins_2026-10-15/agg.csv), and
[specimen table](../../data/results/begins_2026-10-15/reps.csv).
Read them with a CSV-aware reader: quoted narrative and date fields contain
newlines. A physical text line is not a reliable row identifier. Cite the path,
exact `name`, property and processing version; add `Trial` for specimen claims.
Check headers and populated values in the actual supplied file before coding.

## Discover consequential originals within the authorized scope

Before declaring a source missing, follow the selected exact condition/source
identity to `data/raw/<condition>/`, actual `params.json` and specimen filenames;
trace processing plots through `plot_source.json` and input metadata. A plot
directory's date can be a processing date and does not authorize later experiment
inputs. Use warm-start `source_csv`, `source_name` and campaign to resolve aliases.
Do not invent a native path from a label or search unrestricted future evidence.

Record whether evidence was not supplied to an invocation, present but unread,
inaccessible, or absent after a named bounded search. Request authorization before
expanding a scientific model's input scope. A blank quality narrative is not
evidence that raw photos do not exist. Finding source files does not validate
their contents. Read consequential curves/params and inspect rendered
photos/plots before attributing a physical failure or requesting new evidence.

Sample/zero curve pairing, photograph identity, actual settings and processing
selection must remain traceable. A top-surface coverage photograph may answer
placement/tearing questions but cannot establish an unobserved cross-section.
Compression-derived pore fraction does not measure exchange kinetics or image
pore architecture. Keep those proposed intermediates distinct from measured data.

The dynamic caller preserves request-specific CSV input copies under the campaign's
`mas/.inputs/<caller-id>/` and a `provenance.json` naming repository-relative original paths and exact
measurement-content identities. These are pipeline outputs outside scientific Git,
not new measurements. Only shared report annotations are excluded from the
measurement identity; all original scalar strings and rows remain significant.
Originals stay authoritative; copied tables do not establish that raw curves or
photos were inspected. Locate consequential originals through main.

## How SS processing produces the properties

[Curve processing](../../src/pipeline/curve_segmentation.py), especially
`interpretData`, `find_changepoint_fit`, `save_to_csv` and `promote_condition`, is
the producer. It pairs zero/sample curves, corrects displacement and establishes
thickness. In the current non-preprocessed path, stress is load in N divided by
19.635 mm² and multiplied by 10 to obtain bar; strain is corrected displacement
in µm divided by thickness in µm. These are processing assumptions to inspect,
not settings for an agent to change.

The elastic-region regression slope gives elastic modulus. The plateau and
densification regressions give slopes `m_p`, `m_d` and intercepts `b_p`, `b_d`.
Their intersection strain, `(b_d - b_p) / (m_p - m_d)`, is the compression-derived
pore-fraction estimate. Thickness/contact correction, region selection and fit
quality affect it. This is not independent porosimetry, SEM area fraction or
verified three-dimensional porosity. An apparent modulus/pore-fraction association
can also reflect their shared curve-processing origin.

The successful fit dictionary calls this value `Pore Fraction`;
`MECH_PROP_SCHEMA` aggregates it as **`Pore Fraction Mean` / `Pore Fraction SD`**.
Agents interpret these values; they do not fill the columns. A missing point in
a generated figure does not establish a missing source measurement.
Known specimen-export limitation: current `rep_col_order` selects `Changepoint`,
while the successful fit dictionary uses `Pore Fraction`. Check the actual
supplied export; an empty `Changepoint` column cannot recover aggregate pore
fractions by renaming it. Do not search for `Changepoint Mean` in an aggregate
file or reconstruct an empirical SD without underlying per-specimen evidence.
Report the unavailable detail and request original processing evidence. Repairing
this producer/export mismatch is separate implementation work.

| Quantity | Source columns | Units / interpretation |
| --- | --- | --- |
| Elastic modulus; yield strength | `Elastic Modulus`, `Yield Strength`, or `Mean`/`SD` | bar; 10 bar = 1 MPa for a labeled conversion |
| Plateau/densification slopes | `Slope Plateau`, `Slope Densification`, or `Mean`/`SD` | bar per unit dimensionless strain, conventionally reported as bar |
| Thickness | `Thickness`, `Thickness Mean/SD` | µm; affects strain normalization |
| Compression pore fraction | `Pore Fraction Mean/SD` in aggregates | dimensionless estimate; 0.45 corresponds to 45%, not 0.45% |
| Creep and stress-specific strain | `Creep Strain`, `Strain at 50 bar` etc., or `Mean`/`SD` | dimensionless; missing stress-level coverage stays unknown |
| Air/coupon temperature; humidity | `Air Temp Mean`, `Coupon Temp Mean`, `Humidity Mean`, `Coupon Humidity Mean` where present | °C; percent humidity; distinguish measurements from setpoints |
| Curve variability | `CV Mean` | dimensionless aligned-curve summary; not independent-synthesis uncertainty or necessarily modulus SD divided by its mean |

These conventions also appear in
[property_context.py](../../src/pipeline/property_context.py). Prompt copies may
round numbers; use original CSV precision for derived comparisons. Qualitative
image/quality reports provide distinct evidence. They do not replace mechanical
measurements or certify a pore-formation mechanism.

## Aggregation, exclusions and replication

`save_to_csv` computes property means and `np.nanstd` across available specimen
values (current default: population SD, `ddof=0`). Counts can differ by property.
A single finite value can produce SD zero without establishing precision or
repeatability. Aggregate SD is neither a standard error nor a confidence interval.
Do not infer counts from SD or substitute specimen count for synthesis count.

Interpret support, adverse results and inconclusive evidence per question/claim
and endpoint. A missing secondary endpoint alone limits dependent joint-property
or tradeoff claims; it does not erase an independently valid primary contrast.
It also does not certify primary validity: inspect whether shared sample/zero
pairing, contact/thickness correction, fit or selection defects compromise that
measurement too, and classify the affected claims accordingly. Follow the actual
question and quality dependencies without requiring fixed primary/secondary
report fields or inventing acceptance thresholds.

When failures exist, `agg.csv` retains pre/post-discard versions. Current
`PROMOTE_POSTDISCARD=True` selects post-discard when present, and promotion removes
the processing suffix in `llm.csv`. Inspect the corresponding rows to establish
the selected values. The versions are not two syntheses. The same observations
may also appear in a warm-start export.

Post-discard does not mean every column uses only successful fits:

- Most fit-derived properties use passing specimens. If none pass, those
  properties can be missing rather than measurements of poor performance.
- `Thickness` and `Strain at 50 bar` have `always` behavior and can retain values
  from the broader available specimen set. They can remain populated when
  modulus or pore fraction is unavailable.
- Fit scores/reasons explain the discarded set. Invalid thickness, skipped pairs
  and processing exceptions also matter. A fit failure does not mean zero
  modulus or zero pores.

For important comparisons, record the variant and specimen evidence behind each
property. Compare sensitivity to exclusions before explaining a rank change.
Some raw pairs are skipped before a specimen row is emitted; table row count
need not equal the number acquired. Never change stored processing selection to
improve a conclusion.

Separate physical synthesis, tested specimen, processing run and campaign/export
source. Multiple coupons from one synthesis inform within-synthesis variation.
Independent syntheses are needed to assess synthesis reproducibility. `_runN`
can identify another experiment or a processing output collision; the plot writer
supports both meanings. Inspect raw directories, acquisition metadata,
`params.json`, plot source and lab records before assigning independence. If they
do not establish it, preserve that uncertainty.

## Historical context and comparability

Judge comparability using material identities, bath composition, formulation,
casting conditions, nitrogen/exposure, stock batch/age, acquisition time and
processing provenance. Similar names or a common campaign folder are insufficient.
Preserve unknown fields and explicit inference labels: the
[filtered Polysulfone history](../../data/warm_start/polysulfone_polarclean_notebook_filtered_2026-10-15.csv)
has `Polysulfone / PolarClean (inferred)` chemistry with blank material fields in
some rows. That is not operator-confirmed material identity. The
[Primospire history](../../data/warm_start/primospire_nmp.csv) belongs to another
polymer/solvent context and cannot supply a direct Polysulfone performance repeat.

When the filtered PSf/PolarClean history is authorized, read its
[companion selection metadata](../../data/warm_start/polysulfone_polarclean_notebook_filtered_2026-10-15.json)
for cutoff and selection. Its chemistry is inferred,
independent synthesis validation is unknown, and notebook filters exclude some
thin/failed samples; it is not unbiased coverage. Preserve the recorded
thickness/CV/discard/date selection and per-row bath provenance, including linked
historical bath metadata. Do not import Primospire/NMP by default or replace old
bath settings with current defaults. Count records, specimens and syntheses
separately. Zero name overlap with October would not establish independence;
resolve source identity/processing overlap before accumulating confirmation.

The legacy [history merger](../../src/pipeline/llm_context.py) keeps the current
campaign row on a historical `name` match. This is a deduplication rule, not proof
of physical identity. Trace `source_csv`, `source_name` and campaign before
counting overlaps. Preserve distinct experiments where provenance establishes
them; flag unresolved collisions rather than silently merging or double-counting.

`date`/`processed_time` can describe processing; `sample_time` and `time_source`
can trace specimen acquisition. A folder date or row order is not elapsed
experimental time. Missing time/timezone stays unknown. Where history supplies
`stock_solution_batch`, `stock_solution_prepared` or `polymer_solution_age_days`,
retain their recorded basis rather than inventing history from filenames alone.

A source row A's `LLM_suggestion` proposes subsequent point B. It is not A's
measured result or evidence B was performed. Match predictions to actual
subsequent conditions and acquisition evidence; label unlinked execution as
untested or unmatched.

## Conditions, operator authority and decisions

Carry the supplied desired direction or constraint for each endpoint through
inquiry and design, separately from a predicted response. Absence of utility weights
does not imply absence of preference directions. If a material direction/constraint is absent,
request clarification through main while useful independent work proceeds; do
not fill it from source defaults or silently replace the objective with learning.

The eight request fields, subject to current locks and bounds, are `mixing_temp`, `bath_temp`, `pullcast_speed`, `nitrogen`,
`coupon_to_bath_wait_time`, `nips_bath_wait_time`, `polymer_wt`, and `additive_wt`.
Temperatures use °C, speed mm/s, times seconds, and concentrations wt% of final
casting solution. With nitrogen on, pre-bath wait is nitrogen exposure; with it
off, it is ambient exposure. Bath solvent wt% is a separate operator-prepared
bath quantity, not casting-solution additive wt%.

Operator-selected `polymer_type`, `solvent_type`, `cosolvent_type`,
`nips_bath_solvent`, `nips_bath_solvent_wt_percent`, stock compositions and locks
are supplied constraints, not executable agent choices. Fixed settings still
belong in scientific hypothesis/variable coverage and may motivate next-batch
operator comparisons. Use the case's explicit current context. Do not fill old rows from current defaults or infer installed stocks
from historical maximum concentrations.

[run_loop.py](../../src/pipeline/run_loop.py) currently records Polysulfone,
PolarClean, no cosolvent, a PolarClean 10 wt% bath and additive lock 0. This is a
source snapshot, not evidence of current physical bottles. October example rows
record a historical 0 wt% bath with operator-confirmation provenance; do not
overwrite that history with today's source setting. Request operator clarification
through main if current case context is absent or inconsistent.

[current_ranges](../../src/pipeline/activeLearning_29.py) supplies current bounds;
[polymer_additive_bounds.py](../../src/pipeline/polymer_additive_bounds.py) derives
the feasible composition polygon from stock metadata. Its selected source layout
is currently `two_bottle`, with default vertices (17, 0), (17, 4), (0, 0) in
(polymer wt%, additive wt%). Coordinate maxima alone do not describe all feasible
mixtures. Read active metadata rather than applying the example four-bottle
polygon in that module's introductory text. Undiluted polymer stock at its stock
concentration with zero additive requires `mixing_temp=25` because no mixing
occurs; a maximum-polymer blend containing additive is a different case.
Intersect stocks, numeric limits, material restrictions and campaign locks before
scientific design QA. An infeasible historical condition is not permission to
repeat it under changed constraints. Never silently clamp a reviewed design.

Important-variable coverage also considers relevant protocol constants (including
second-bath residence and dispensed volume), recorded air/coupon temperature and
humidity, stock age/batch, acquisition/processing and preparation context. Ground
these in actual source/approved operator facts, retain unknowns and distinguish
setpoints from measurements. Link each important variable to reasoned claims or
an explicit unlinked reason/reconsideration cue in the shared topic documents or
linked context; fixed or unvaried does not mean irrelevant, and unlinked does not
mean linked-but-untested.
Do not infer a causal residence-time effect from constant-time observations.

For hypothesis-grounded optimization, use the workflow's [design deduction](workflow.md#deduce-useful-optimization-and-design).
Consider consequences for both modulus and the fitted compression pore estimate,
with their actual quality dependencies; do not invent objective weights or treat
a property forecast as mechanism confirmation. A gap exposed by design returns
through main to the inquiry author/unified QA, without changing operator settings.
The outcome is at most one exact next request, not an executable batch of future
controls; the source/stock/lock and report-only limits below still apply.

In the target workflow, integrated inquiry or split analysis separates observations,
interpretations and uncertainty; topic documents retain prior meanings, evidence
summaries, historical IDs and revision reasons; design records
predictions, comparators and support/refutation/inconclusive outcomes; main records
the selected question and final action. Preserve previous judgments, explain
revisions and re-review affected conclusions. Main follows report/artifact paths
and may return upstream. Run adopts exactly the feasible scientifically reviewed
conditions; hold/stop has no executable next conditions. A report-only pilot does
not submit an experiment even when its scientific recommendation is run.

## Operator batches and recommendations

An operator batch is an explicitly confirmed grouping of physical work/context,
not automatically a campaign folder or a fixed number of rows. Source
[robot.json](../../OT2_Server_2026-06-11/robot.json) configures nine coupons/rings;
[protocol run_test](../../OT2_Server_2026-06-11/protocol-multithreaded.py) processes
one coupon per request and fixes second-bath residence at `60 * 45` seconds.
The request's `nips_bath_wait_time` is the first-bath time, a different quantity.
Source capacity/constants are not evidence of current loading or completion.
Bath composition is operator-prepared and casting additive may be locked.

The [request journal](../../OT2_Server_2026-06-11/lib/request_server.py) returns
202 for acceptance, then executes asynchronously. Its local failed/completed
state is distinct from the protocol's successful processing callback; a failure
can leave the PC without a completion callback. Silence does not identify depleted
resources, normal batch completion or scientific optimization completion. Report
unresolved execution and request human resource/prepared-setting checks before
the next operation; never retry or alter physical state through this workflow.

Main's current-attempt `batch-summary-<batch-id>.md` links the confirmed
grouping/context, available observations and cumulative learning, unresolved
execution and proposed next-batch comparisons. State a fixed-setting proposal's
scientific reason, competing prediction, controls and required operator decision;
it is not an executable field of the next coupon. Never change locks, baths or
protocol residence from a recommendation. Constant 45-minute data cannot establish
a time effect. An offline historical summary must be labeled report-only/candidate
and must not invent a completed physical batch.

## Current operational records

[Conditions and receipts](../../src/pipeline/mas_contract.py) type only execution
and native handoff boundaries. Readable authored/reviewed Markdown, actual Git
knowledge versions and an accepted decision Markdown record provide navigation.
The pipeline retains shared `initial_report`, `final_report`, `LLM_suggestion`
columns and original numeric strings; no initialization row is fabricated. A
queued reconsideration retains previous accepted decisions and checkpoint stages.
RUN alone is not authority to submit an experiment. The caller's existing physical
request/journal recovery remains separate from scientific reconsideration.
