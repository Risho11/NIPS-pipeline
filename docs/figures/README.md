# NIPS workflow figures

## Minimal overview

The seven-stage overview uses plain rectangular boxes, restrained black/blue styling and explicitly routed arrows. Measurements split into mechanical and visual analysis, merge into the experimental record, and feed recipe selection. Branches show data dependencies rather than simultaneous execution. Hardware and software implementation details remain in the more detailed versions below.

- Paper, **180 × 110 mm**: [PDF](nips_workflow_overview_paper.pdf), [editable SVG](nips_workflow_overview_paper.svg), [PNG](nips_workflow_overview_paper.png).
- Slide, **16:9**: [PDF](nips_workflow_overview_slide.pdf), [editable SVG](nips_workflow_overview_slide.svg), [PNG](nips_workflow_overview_slide.png).
- Source: [generate_overview_workflow.py](generate_overview_workflow.py).

## Recommended: readable workflow

The intermediate-detail version uses **24 short bricks in four lanes**, larger labels and fewer connections. It retains hardware preparation, nitrogen/ambient exposure, both analysis paths, experimental memory and the next-experiment feedback loop.

- Paper: **180 × 150 mm**, [PDF](nips_workflow_readable_paper.pdf), [editable SVG](nips_workflow_readable_paper.svg), [PNG](nips_workflow_readable_paper.png).
- Slide: **16:9**, [PDF](nips_workflow_readable_slide.pdf), [editable SVG](nips_workflow_readable_slide.svg), [PNG](nips_workflow_readable_slide.png).
- Rebuild with `python docs/figures/generate_readable_workflow.py`.

All figure variants now use **four zero curves + four sample curves (eight CSVs)** per run. This agrees with the four positions in the robot protocol's `tests` list and `REPS_PER_CONDITION = 8` in the collector. Older overview prose and a robot-protocol comment still mention three; the executable configuration takes precedence. Only figure sources, documentation and exports were changed.

## Detailed brick-and-branch flowchart

The revised chart contains **68 nodes and 85 connections**, organized into campaign/HTTP, robot preparation, formation/testing, mechanical analysis, vision/memory, and decision/recovery lanes. Individual hardware operations, decisions, artifacts, concurrent preparation tasks and failure/recovery paths are separate bricks.

- Paper/full-page landscape: [PDF](nips_workflow_detailed_paper.pdf), [editable SVG](nips_workflow_detailed_paper.svg), [PNG](nips_workflow_detailed_paper.png). Native dimensions are A4 landscape (297 × 210 mm approximately); use as a full-page or supplementary workflow figure to preserve label readability.
- Widescreen slide, 16:9: [PDF](nips_workflow_detailed_slide.pdf), [editable SVG](nips_workflow_detailed_slide.svg), [PNG](nips_workflow_detailed_slide.png). This is a dense overview suited to zooming or progressive presentation.
- Source: [generate_detailed_workflow.py](generate_detailed_workflow.py). Run `python docs/figures/generate_detailed_workflow.py`.

Solid connectors show control/physical flow; dashed grey connectors show data dependencies; dashed red connectors show failure propagation; dashed gold connectors show recovery. Hardware fork/join paths are concurrent, while analysis branches dispatch sequentially. The raw-image vision path is currently enabled; the legacy image path is included as a configurable branch. The initial schema and recommendation schema checks are the same type of operation at different campaign stages. The chart is a dependency graph; rows across lanes do not represent a shared clock. The LVDT/freshness gate applies after each zero and sample compression measurement. The independent-repeat brick is a model instruction, not a deterministic acceptance gate.

Generated from an inspection of the repository on 2026-11-02. These figures describe the configured active-learning workflow, rather than every supported test or sweep mode. No robot runs or LLM calls were made.

| Intended use | Dimensions | Files |
| --- | --- | --- |
| Paper, full-width figure | 180 × 140 mm (9:7), 400 dpi PNG | [PDF](nips_workflow_paper.pdf), [editable SVG](nips_workflow_paper.svg), [PNG](nips_workflow_paper.png) |
| Widescreen presentation | 16 × 9 in (16:9), 3840 × 2160 PNG | [PDF](nips_workflow_slide.pdf), [editable SVG](nips_workflow_slide.svg), [PNG](nips_workflow_slide.png) |

Use the paper PDF at approximately its native width; shrinking the dense figure to a single journal column will make the labels too small. SVG text remains editable. PDF fonts are embedded. Regenerate with `python docs/figures/generate_workflow.py` using Python with Matplotlib installed.

## Suggested caption

Closed-loop workflow for automated non-solvent-induced phase separation (NIPS) membrane fabrication and characterization. Operator-defined material and bath composition, together with historical experimental records, initialize a robotic synthesis campaign. An Opentrons OT-2 and xArm prepare, cast, expose and immerse the polymer film. Compression measurements and photographs are archived with the synthesis parameters. Mechanical analysis pairs sample measurements with machine-compliance zero curves, constructs stress–strain curves, and extracts properties using generalized additive models (GAMs) and regional fits. A vision model assesses the pre-test membrane photograph. Aggregated measurements, fit reliability and visual quality are combined with campaign and warm-start history to recommend a subsequent feasible synthesis. The configured recommendation mode pursues elastic modulus and compression-derived pore fraction with modest exploration and prompt-directed independent validation. Offline fit review and repeatability analysis support interpretation of the campaign.

## Source audit and interpretation

- `src/pipeline/run_loop.py`: campaign initialization, collection, parameter schema, fixed material context, checkpoint recovery and robot submission. The inspected settings use Polysulfone / PolarClean, no cosolvent, 10 wt% PolarClean in the NIPS bath, additive locked to 0 wt%, `double_explore`, and filtered notebook warm-start history. The figures describe these mechanisms without making the selected material system universal.
- `OT2_Server_2026-06-11/protocol-multithreaded.py`: physical fabrication, zero/sample compression operations, snapshots and environmental sensing. Real compression and photographs are enabled in the inspected configuration. Eight CSVs are four zero and four sample curves; these are within-run measurements, not four independent synthesis repeats.
- `src/pipeline/master_processing.py`: both performance and quality branches are enabled. Dispatch is sequential; the figure does not imply concurrent computation. The mechanical call uses 1 N load cleanup, a 3 N thickness fallback cutoff and a 2 N displacement cutoff.
- `src/pipeline/curve_segmentation.py`: compliance correction, GAM and regional fits, contact-thickness estimation, fit scoring and pre/post-discard aggregation. `Pore Fraction` is assigned the fitted changepoint strain; the diagram preserves that computational definition and does not claim an independent porosity measurement. Contact thickness is estimated by extrapolating the 10–40 N displacement/load fit to zero load, with a single-point fallback. Thickness must exceed 50 µm to pass the membrane-presence criterion. Post-discard promotion is enabled; some schema fields retain all-valid-replicate summaries even when fits fail, so post-discard does not mean every reported quantity uses an identical subset.
- `src/pipeline/membrane_imaging.py`, `membrane_quality_llm.py`, `llm_context.py`: the earliest timestamped photograph is used as the pre-test image. Raw-image vision assessment is enabled; the legacy pixel-processing and probe-location path is not the current route. Quality addresses presence, coverage, uniformity and visible defects. It is not a pore-fraction measurement.
- `src/pipeline/activeLearning_29.py`, `system_prompt.py`, `property_context.py`: structured experimental observations, material/bath context, diversity context and a two-objective recommendation. Independent repeat validation is a prompt instruction, not a separate deterministic enforcement gate. Recommendations return eight tunable controls; the operator controls material identities and bath-solvent composition. Parameter schema checking validates keys/types; stock projection and locks are separate operations. The figure does not assert comprehensive numeric-range enforcement in the parser.
- `src/pipeline/polymer_additive_bounds.py`: stock-feasible composition projection. The inspected stock mode is two-bottle; a four-bottle mode is also implemented. Undiluted polymer stock bypasses mixing and is assigned 25 °C.
- `EVALUATE/generate_fit_log.py`, `generate_quality_log.py`, `campaign_repeatability.py`, and the HTML fit-log structure: offline review and descriptive repeatability. Matching uses exact polymer wt%, nitrogen state and bath-solvent wt%, plus the four tolerances printed in the figure. Complete linkage bounds each group's full span. Mixing temperature, immersion time and additive wt% are reported but are not additional matching constraints. Missing matching inputs do not match. Between-sample SD and CV use synthesis-run means, not within-run measurement error bars. These groups are comparable-condition groups, not necessarily exact recipe repeats. No automatic feedback from reviewer flags into the optimizer is asserted.

Alternative modes supported by the repository include single-objective optimization, broader exploration, fixed additive/polymer sweeps, and independently disabled analysis branches. They are omitted from the main loop to keep the configured scientific workflow readable. The older `docs/PIPELINE_OVERVIEW.md` differs from current code in the optimization objective, thickness estimation and some fit logic; the code takes precedence here.
