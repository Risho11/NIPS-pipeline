# AUTODIAL Pipeline Overview

This is an **automated membrane fabrication and characterization system** for NIPS (Non-solvent Induced Phase Separation) membranes — polymer membranes made by casting a polysulfone solution and immersing it in a bath to trigger phase separation.

Two machines are involved, each running its own server/client pair over HTTP:

- **Robot PC** (Opentrons + xArm) — runs `2026-06-11/protocol-multithreaded.py`, physically fabricates and (optionally) compression-tests each batch.
- **Mini PC** — runs `run_loop.py`, orchestrates the campaign, collects data, drives the analysis pipeline and the active-learning loop.

```
run_loop.py (mini PC, 169.254.230.148:8000)
   -- POST /run (url_29.py) -->        protocol-multithreaded.py (robot PC, 169.254.46.48:8000)
   <-- GET /camera/snapshot --         (lib/url.py client, mid-protocol)
   <-- GET /compressiontester/status --
   <-- POST /server/process --         (fabrication params + protocol log, after the batch finishes)
```

---

## Stage 1 — Fabrication (Robot)

`2026-06-11/protocol-multithreaded.py` runs on the robot PC and drives the physical hardware (`arm.py`/`Arm`, `ot2.py`/`OT2`, `chiller.py`/`BathChiller`, `uno_control.py`/`Uno`). It receives fabrication parameters via its own embedded `POST /run` handler, starts the run on a background thread, and reports back to `run_loop.py` when done.

Fabrication parameters (as stored in each condition folder's `params.json`):

| Parameter | Meaning |
|---|---|
| `polymer_wt` | Polymer stock weight percent |
| `additive_wt` | Additive weight percent — `polymer_wt`/`additive_wt` are jointly clamped to a feasible triangle by `polymer_additive_bounds.py` (two physical stocks: a pure-polymer stock and a polymer+additive stock) |
| `mixing_temp` | Temperature at which solution is heated/mixed |
| `bath_temp` | Temperature of the NIPS water bath |
| `coupon_to_bath_wait_time` | Seconds between casting and bath immersion |
| `nitrogen` | Whether dry N₂ blows over the cast film during the wait |
| `nips_bath_wait_time` | How long the membrane sits in the bath |
| `pullcast_speed` | Blade casting speed (mm/s) |

Two module-level toggles at the top of `protocol-multithreaded.py` control what actually happens during the run, independent of each other:

- `simulate_compression_tests` — `True` runs a simulated (no-op) compression cycle; `False` calls `run_compression_tests()` against the real Newton/compression tester.
- `take_picture` — gates both `url.take_snapshot()` calls (pre-test and post-test). When `False`, no snapshot request is even sent to the mini PC.

`2026-06-11/lib/url.py` is the robot-side HTTP client used mid-protocol: `take_snapshot()` (→ mini PC `GET /camera/snapshot`), `get_compressiontester_status()` (→ `GET /compressiontester/status`), and `start_processing()` (→ `POST /server/process`, handing fabrication params + the protocol log back to `run_loop.py`).

---

## Stage 2 — Orchestration, Mechanical Testing & Branch Dispatch (`src/pipeline/run_loop.py` + `src/pipeline/master_processing.py`)

`run_loop.py` runs as an HTTP server on the mini PC and:

1. Kicks off the first experiment (`INITIAL_PARAMS`, or the first step of the additive sweep — see below) via `url_29.run_test()` → robot's `POST /run`.
2. Serves `GET /camera/snapshot` (captures a frame via OpenCV from `CAMERA_INDEX`, saves it into the `images/` folder) and `GET /compressiontester/status` (reads the latest Newton CSV, checks the LVDT column for a safe pin position).
3. On `POST /server/process` (robot reporting a finished batch), runs `_run_pipeline_and_trigger_next()` in a background thread:
   - `move_and_rename()` builds a condition folder name from the params, copies the last 2 camera images + last 6 Newton CSVs into `data/raw/<condition>/`, writes `params.json`.
   - Hands off to `master_processing.run_branches()`.
   - Feeds the results through `llm_context.py` into that campaign's `llm.csv`.
   - Gets the next params (LLM suggestion, or the next additive-sweep step) and POSTs them back to the robot.

`master_processing.py` dispatches each enabled entry in `BRANCH_CONFIG` — currently `curve_segmentation` (type `"performance"`) and `image_processing` (type `"quality"`, via `membrane_imaging.py`). Branches are independently toggleable; disabling one is the only thing that skips it — an *enabled* branch that raises is a real failure and stops the loop. If **every** branch is disabled, it's a pure test: no testing, no data collection, and `run_loop.py` just cycles a fixed additive sweep instead of calling anything here (see "Additive Iteration Mode" below).

`membrane_imaging.py`'s `image_processing` branch reads whichever jpg `move_and_rename` dropped into the condition folder. By default (`SEND_RAW_IMAGE = True`) it skips the pixel-math entirely and just hands the image path to a vision LLM (`membrane_quality_llm.Generate_quality_report` — qualitative rubric: presence, coverage, uniformity, wrinkles/bubbles) since the pixel-math approach breaks down on out-of-focus photos. The legacy pixel-math path (`analyze_membrane()` → brightness-difference threshold → integral-image denoise → uniform-region detection → `find_probe_test_point()` for compression-probe placement) still exists behind `SEND_RAW_IMAGE = False`.

Each **batch of 6 Newton CSVs** = 3 zero curves (no membrane, machine compliance only) + 3 sample curves (membrane in place), paired chronologically.

### Campaign output location (`CONTINUE_CAMPAIGN`)

`run_loop.py` writes every round's CSVs to `data/results/begins_<d>/{reps,agg,llm}.csv`, where `<d>` is today's date unless `CONTINUE_CAMPAIGN` (near the top of the file) is set to a specific date string — set it to resume appending to a prior campaign's folder instead of starting a fresh one each day. These per-campaign paths (`CSV_REPS`/`CSV_AGG`/`CSV_AGG_LLM`) are passed explicitly into `master_processing.run_branches()`; the flat `data/results/results_*.csv` names are only a fallback used when a caller (e.g. a standalone dev/test script) doesn't pass `csv_paths` at all — a real campaign run never touches them. Historical data that had accumulated at the flat paths before this convention was in the file map has since been moved to `data/archive/results-legacy/`.

Each raw condition also has an atomic `.pipeline_state.json` checkpoint. On startup, the server
checks only the latest campaign row and resumes it when its next-parameter JSON or downstream
stages are incomplete. Completed mechanical processing is reused; missing quality/report stages
are retried against the existing images. Robot submission is checkpointed before the network
call. If a restart finds `submission_started` without `next_run_submitted`, it stops for operator
verification instead of risking a duplicate physical experiment.

---

## Stage 3 — Curve Processing (`src/pipeline/curve_segmentation.py`)

This is the core mechanical-property analysis, run via `process_zero_sample_pairs_pipeline()`.

### Step A: Raw curve cleanup — `process_curve_raw()`

- Loads a CSV
- **Zero curves**: truncates at the point of max load (before setpoint crosses 1.0), then zeroes the LVDT at that point. Unit conversion: inches → µm (×25400).
- **Sample curves**: truncates at the end of the creep hold (last point where `Set Point ≥ 1.0`), LVDT similarly converted.
- Applies a **load cutoff** (drops rows below 1 N) to remove noise at the start.

### Step B: Zero subtraction — `subtract_zero_from_sample()`

The zero curve captures machine frame compliance (the machine itself deflects under load). This step removes it from the sample signal:

1. The zero's LVDT is interpolated onto the sample's load values
2. Corrected displacement = sample LVDT − zero LVDT → `Disp_corrected (um)`

This gives the **true membrane displacement** at each load level.

### Step C: Stress-strain construction

- **Thickness** is read from `Disp_corrected` at the 1 N load cutoff point (the membrane's initial displacement at first contact = its thickness)
- **Strain** = corrected displacement / thickness
- **Stress** = Load / cross-sectional area (19.63 mm²) × 10 → bar

### Step D: Curve segmentation — `interpretData()`

This is where the stress-strain curve is segmented into three physical regions:

```
Stress
  |           /  <- densification (stiffening, cells fully collapsed)
  |__________/   <- plateau (cell wall buckling, relatively flat)
  |/              <- elastic (linear, small deformation)
  +-----------> Strain
```

The current approach:

1. A **GAM spline** (`pygam.LinearGAM`) is fit to smooth the raw curve
2. The **2nd derivative** of the spline is computed — the minimum of the 2nd derivative (restricted to strain ≤ 0.3) marks `breakpoint1` (end of elastic region)
3. **Linear regression** on the elastic region → Elastic Modulus and Yield Strength
4. **Piecewise regression** (`piecewise_regression`) on everything after `breakpoint1` → finds the plateau-to-densification transition
5. Linear fits on each identified region → plateau slope, densification slope, changepoint
6. A `Good Fit` flag is set based on continuity checks between the region boundaries

**Output properties per specimen** (schema lives in `llm_context.MECH_PROP_SCHEMA`, single source of truth for what becomes a CSV column and whether it's sent to the LLM):

| Property | Description |
|---|---|
| Elastic Modulus | Slope of the elastic region (bar) |
| Yield Strength | Stress at end of elastic region (bar) |
| Changepoint | Strain at plateau-to-densification transition |
| Slope Plateau | Slope of plateau region |
| Slope Densification | Slope of densification region |
| Creep Strain | Strain accumulated during creep hold |
| Strain at 50/80/150/500 bar | Strain values at fixed stress levels (from GAM) |
| Air Temp / Humidity | Environmental sensor readings, folded in per-condition |
| Good Fit | Boolean quality flag |

### Step E: Output — `save_to_csv()` / `promote_condition()`

Mechanical properties are merged with the fabrication `params.json` for that condition, written to that campaign's `data/results/begins_<d>/` folder (see "Campaign output location" above):

- `reps.csv` — one row per replicate/specimen
- `agg.csv` — aggregated (mean ± SD) per condition, plus each branch's raw `{type}_result` column, plus `formatted_parameters` and `formatted_parameters_withProp` (see below)
- `llm.csv` — the LLM-facing subset (`promote_condition()` copies the matching row across); `llm_context.scrub_raw_result_columns()` strips any `{type}_result` blob from this one every round so raw branch output never reaches the LLM directly

`formatted_parameters_withProp` is `formatted_parameters` (the bare fabrication-params string) with the round's mechanical outcome appended — either a narrative (`_membrane_outcome_string()`, when `EXTENDED_CONTEXT` is on) or a raw mean-properties dict, plus `Discarded Fit Quality Mean`/`Discarded Fit Reasons` notes when some reps got discarded. `curve_segmentation.py` is the only thing that ever writes it — `llm_context.py` treats it as fragile: `_clear_stale_performance_outcome()` resets it back to bare `formatted_parameters` for any round where the performance branch didn't run (so last round's outcome text can't leak into a report where no fit check actually happened), and `generate_reports_and_suggestion()` rebuilds it idempotently (strips the params prefix before re-concatenating) so re-running the same round never double-appends the outcome text.

---

## LLM Context Layer (`src/pipeline/llm_context.py`)

The single place that decides **what** reaches the LLM and **how it's labeled**, grouped by branch **type** (`"performance"` / `"quality"`) rather than by individual branch name — a new branch of an existing type needs no new plumbing.

- `"performance"` reports are built natively by `curve_segmentation.py` (`formatted_parameters` / `formatted_parameters_withProp` / `final_report` columns, see Step E above) — untouched here except for the stale-outcome guard.
- Any other type (currently just `"quality"`) goes through `attach_branch_result_to_csv()`: the full JSON-safe result lands in `agg.csv` as `{type}_result`; a text summary lands in both CSVs as `{type}_report`. For `"quality"`, that summary is a real vision-LLM call (`generate_quality_report_text` → `membrane_quality_llm.Generate_quality_report`), not just a field dump.
- `ensure_condition_row()` creates a minimal `llm.csv` row when `curve_segmentation` didn't run at all (e.g. an image-only campaign), so there's still something for `image_processing`'s report to attach to.
- `generate_reports_and_suggestion()` is the glue `run_loop.py` calls each round: builds `initial_report`/`final_report` via `activeLearning.Generate_report`, joins `performance_observations` across campaign history plus `quality_observations` (joined `quality_report` column), and calls `activeLearning.LLM_AL`.

---

## Active Learning Loop (`src/pipeline/activeLearning_29.py`)

After enough data is collected, `LLM_AL(performance_observations, ranges, quality_observations=...)` sends prior observations to an LLM (Claude via OpenRouter) and asks it to recommend the next set of fabrication parameters. `run_loop.py` extracts/validates the response against `PARAMS_SCHEMA`, snaps `polymer_wt`/`additive_wt` to the feasible stock triangle via `polymer_additive_bounds.test_target()`, and POSTs the result back to the robot. This closes the loop:

```
Robot fabricates → (compression test) → curve/image processing → LLM suggests next params → Robot fabricates → ...
```

`Generate_report()` translates a raw `formatted_parameters` string into a short human-readable experimental report via the LLM. The system-prompt text both `Generate_report` and `LLM_AL` send is not inline in this file — it's centralized in `src/pipeline/system_prompt.py` (see File Map).

### Additive Iteration Mode (`run_loop.py`)

An alternative to LLM-directed search: `ITERATE_ADDITIVES = True` makes `run_loop.py` cycle through a fixed `ADDITIVE_ITERATION_LIST` of `additive_wt` values (at fixed `ITERATION_BASE_PARAMS`) instead of asking the LLM each round — useful for a controlled sweep. Branches still run normally for data collection if enabled. This mode is **forced on** regardless of the toggle whenever zero branches are enabled at all, since a pure test has no data to run active learning on.

---

## File Map

| File | Role |
|---|---|
| `2026-06-11/protocol-multithreaded.py` | Robot-side script (Opentrons + xArm); runs on the lab PC wired to the hardware |
| `2026-06-11/lib/url.py` | Robot-side HTTP client → mini PC (snapshot, compression-tester status, batch handoff) |
| `src/pipeline/run_loop.py` | Mini-PC orchestrator/server — main entry point for a campaign |
| `src/pipeline/url_29.py` | Mini-PC HTTP client → robot (`POST /run`, coupon/ring/tip/heater-well bookkeeping) |
| `src/pipeline/master_processing.py` | Branch dispatcher (`BRANCH_CONFIG` toggles `curve_segmentation` / `image_processing`) |
| `src/pipeline/curve_segmentation.py` | Mechanical curve processing pipeline |
| `src/pipeline/membrane_imaging.py` | `image_processing` branch — vision-LLM passthrough by default, legacy pixel-math available |
| `src/pipeline/membrane_quality_llm.py` | Dedicated vision-LLM call for qualitative membrane judgment |
| `src/pipeline/llm_context.py` | Glue: what reaches the LLM, from which branch, into which CSV column |
| `src/pipeline/activeLearning_29.py` | `Generate_report` / `LLM_AL` — the active-learning LLM calls |
| `src/pipeline/system_prompt.py` | Single source of truth for all three LLM system prompts (report, active-learning, quality-checker) |
| `src/pipeline/polymer_additive_bounds.py` | Stock-triangle clamping for `polymer_wt`/`additive_wt` |
| `src/pipeline/polymer_additive_mixing_calculator.py` | Computes stock volumes to physically prepare a target casting dope |
| `src/pipeline/cameras.py` | Standalone multi-camera preview utility (not wired into `run_loop.py`) |
| `src/server/server.py` | Compression-tester safety-check HTTP handler; manually copied to the lab PC, not auto-deployed (see root README) |
| `data/raw/` | One subfolder per condition: Newton CSVs, camera jpgs, `params.json` |
| `data/results/begins_<d>/{reps,agg,llm}.csv` | Per-campaign per-rep, aggregated, and LLM-facing results tables (see "Campaign output location" above) |
| `data/archive/` | Retired data kept for history: `compression-test-data-legacy/` (pre-reorg name for `data/raw/`), `results-legacy/` (pre-campaign-folder flat CSVs), `old_csv/`, `Image Processing/` |
| `tests/` | `test_master.py`, `test_guardrails.py`, `test_processing.py`, `test_imaging.py`, `test_csv.py`, `test_quality_recovery.py`, `run_tests.py`, `run_loopTest.py`, `plot_curves.py`, plus fixture folders (`csv_tests/`, `image_tests/`, `quality_test/`) |

---

## Where to Focus for Curve Segmentation

The segmentation logic lives in `interpretData()` in `curve_segmentation.py`. The current pain points:

- The **2nd derivative minimum** approach for the elastic boundary is sensitive to noise in the spline — the GAM smoothing level matters a lot
- **Piecewise regression** sometimes fails to converge or picks physically unreasonable breakpoints
- The **Good Fit** check is a loose heuristic (checks slope continuity and boundary alignment within ±3 bar)

These are the areas where improved segmentation logic would have the most impact.
