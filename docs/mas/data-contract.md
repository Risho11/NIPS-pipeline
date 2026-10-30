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
independent scientific QA support those decisions. Four accepted Markdown records
remain: analysis, hypothesis update, experiment design and final decision. Their
layout follows the question; report locations and revision reasons let main follow
evidence without whole-report JSON echoes or report-hash gates.

These documents do not implement that target. The preserved
[Codex adapter](../../src/pipeline/codex_context.py) opens a read-only thread and
requests four fixed schema-bound operations. Its
[record layer](../../src/pipeline/mas_records.py) freezes inputs, caches completed
stages and verifies report hashes. Its existing artifact generator is not the
target question-led analysis workspace. Writing scripts/figures and reopening
judgments require the separately scoped isolated pilot or later integration;
this guide does not grant filesystem permissions or migrate the adapter.

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

The existing adapter's `observation_inputs` freezes campaign `llm.csv`, `agg.csv`
and `reps.csv` when present, optional `warm_start.csv`, and `context.json` with
constraints and original source paths. Non-LLM campaign tables can be absent;
raw curves are not copied by that function. Inspect the actual input directory
and request missing sources through main when a material question needs them.
An aggregate summary does not establish that original curves were inspected.

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
The preserved [MAS figure reader](../../src/pipeline/mas_analysis.py) still reads
`Changepoint Mean`, so its pore-fraction output is not a reliable substitute for
checking the aggregate's actual `Pore Fraction Mean` column.

Known specimen-export limitation: current `rep_col_order` selects `Changepoint`,
while the successful fit dictionary uses `Pore Fraction`. The October specimen
table has a `Changepoint` header with empty values in inspected successful-fit
rows, although corresponding aggregate pore fractions exist. Renaming that empty
column cannot recover values. Do not search for `Changepoint Mean` in an aggregate
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

The eight tunables are `mixing_temp`, `bath_temp`, `pullcast_speed`, `nitrogen`,
`coupon_to_bath_wait_time`, `nips_bath_wait_time`, `polymer_wt`, and `additive_wt`.
Temperatures use °C, speed mm/s, times seconds, and concentrations wt% of final
casting solution. With nitrogen on, pre-bath wait is nitrogen exposure; with it
off, it is ambient exposure. Bath solvent wt% is a separate operator-prepared
bath quantity, not casting-solution additive wt%.

Operator-selected `polymer_type`, `solvent_type`, `cosolvent_type`,
`nips_bath_solvent`, `nips_bath_solvent_wt_percent`, stock compositions and locks
are supplied constraints, not agent choices. Use the case's explicit current
context. Do not fill old rows from current defaults or infer installed stocks
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

In the target workflow, analysis separates observations, interpretations and
uncertainty; hypotheses retain IDs, evidence and revision reasons; design records
predictions, comparators and support/refutation/inconclusive outcomes; main records
the selected hypothesis and final action. Preserve previous judgments, explain
revisions and re-review affected conclusions. Main follows report/artifact paths
and may return upstream. Run adopts exactly the feasible scientifically reviewed
conditions; hold/stop has no executable next conditions. A report-only pilot does
not submit an experiment even when its scientific recommendation is run.

For compatibility only, the preserved adapter generates schemas from
[Pydantic models](../../src/pipeline/mas_schema.py), including
`HypothesisUpdate.hypotheses`, `ExperimentDesign.experiment` and
`ExperimentDecision.next_params`. Python stores returned report prose, attaches
analysis/decision text and paths to the exact current `llm.csv` condition, and
preserves numeric columns. No measurement row is invented at initialization.
Its run result can produce
`data/llm_results/llm_result_<source_condition>.json` with stock metadata; hold/stop
does not create a new executable payload. These are adapter mechanics, not
authority to execute them or requirements to duplicate whole reports in the
target scientific workflow.
