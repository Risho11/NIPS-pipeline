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

## Stage 2 — Orchestration, Mechanical Testing & Branch Dispatch (`run_loop.py` + `master_processing.py`)

`run_loop.py` runs as an HTTP server on the mini PC and:

1. Kicks off the first experiment (`INITIAL_PARAMS`, or the first step of the additive sweep — see below) via `url_29.run_test()` → robot's `POST /run`.
2. Serves `GET /camera/snapshot` (captures a frame via OpenCV from `CAMERA_INDEX`, saves it into the `images/` folder) and `GET /compressiontester/status` (reads the latest Newton CSV, checks the LVDT column for a safe pin position).
3. On `POST /server/process` (robot reporting a finished batch), runs `_run_pipeline_and_trigger_next()` in a background thread:
   - `move_and_rename()` builds a condition folder name from the params, copies the last 2 camera images + last 6 Newton CSVs into `compression-test-data/<condition>/`, writes `params.json`.
   - Hands off to `master_processing.run_branches()`.
   - Feeds the results through `llm_context.py` into `results_agg_llm.csv`.
   - Gets the next params (LLM suggestion, or the next additive-sweep step) and POSTs them back to the robot.

`master_processing.py` dispatches each enabled entry in `BRANCH_CONFIG` — currently `curve_segmentation` (type `"performance"`) and `image_processing` (type `"quality"`, via `membrane_imaging.py`). Branches are independently toggleable; disabling one is the only thing that skips it — an *enabled* branch that raises is a real failure and stops the loop. If **every** branch is disabled, it's a pure test: no testing, no data collection, and `run_loop.py` just cycles a fixed additive sweep instead of calling anything here (see "Additive Iteration Mode" below).

`membrane_imaging.py`'s `image_processing` branch reads whichever jpg `move_and_rename` dropped into the condition folder. By default (`SEND_RAW_IMAGE = True`) it skips the pixel-math entirely and just hands the image path to a vision LLM (`membrane_quality_llm.Generate_quality_report` — qualitative rubric: presence, coverage, uniformity, wrinkles/bubbles) since the pixel-math approach breaks down on out-of-focus photos. The legacy pixel-math path (`analyze_membrane()` → brightness-difference threshold → integral-image denoise → uniform-region detection → `find_probe_test_point()` for compression-probe placement) still exists behind `SEND_RAW_IMAGE = False`.

Each **batch of 6 Newton CSVs** = 3 zero curves (no membrane, machine compliance only) + 3 sample curves (membrane in place), paired chronologically.

---

## Stage 3 — Curve Processing (`curve_segmentation.py`)

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

Mechanical properties are merged with the fabrication `params.json` for that condition:

- `results_reps.csv` — one row per replicate/specimen
- `results_agg.csv` — aggregated (mean ± SD) per condition, plus each branch's raw `{type}_result` column
- `results_agg_llm.csv` — the LLM-facing subset (`promote_condition()` copies the matching row across); `llm_context.scrub_raw_result_columns()` strips any `{type}_result` blob from this one every round so raw branch output never reaches the LLM directly

---

## LLM Context Layer (`llm_context.py`)

The single place that decides **what** reaches the LLM and **how it's labeled**, grouped by branch **type** (`"performance"` / `"quality"`) rather than by individual branch name — a new branch of an existing type needs no new plumbing.

- `"performance"` reports are built natively by `curve_segmentation.py` (`formatted_parameters` / `final_report` columns) — untouched here.
- Any other type (currently just `"quality"`) goes through `attach_branch_result_to_csv()`: the full JSON-safe result lands in `results_agg.csv` as `{type}_result`; a text summary lands in both CSVs as `{type}_report`. For `"quality"`, that summary is a real vision-LLM call (`generate_quality_report_text` → `membrane_quality_llm.Generate_quality_report`), not just a field dump.
- `ensure_condition_row()` creates a minimal `results_agg_llm.csv` row when `curve_segmentation` didn't run at all (e.g. an image-only campaign), so there's still something for `image_processing`'s report to attach to.
- `generate_reports_and_suggestion()` is the glue `run_loop.py` calls each round: builds `initial_report`/`final_report` via `activeLearning.Generate_report`, joins `performance_observations` across campaign history plus `quality_observations` (joined `quality_report` column), and calls `activeLearning.LLM_AL`.

---

## Active Learning Loop (`activeLearning_29.py`)

After enough data is collected, `LLM_AL(performance_observations, ranges, quality_observations=...)` sends prior observations to an LLM (Claude via OpenRouter) and asks it to recommend the next set of fabrication parameters. `run_loop.py` extracts/validates the response against `PARAMS_SCHEMA`, snaps `polymer_wt`/`additive_wt` to the feasible stock triangle via `polymer_additive_bounds.test_target()`, and POSTs the result back to the robot. This closes the loop:

```
Robot fabricates → (compression test) → curve/image processing → LLM suggests next params → Robot fabricates → ...
```

`Generate_report()` translates a raw `formatted_parameters` string into a short human-readable experimental report via the LLM.

### Additive Iteration Mode (`run_loop.py`)

An alternative to LLM-directed search: `ITERATE_ADDITIVES = True` makes `run_loop.py` cycle through a fixed `ADDITIVE_ITERATION_LIST` of `additive_wt` values (at fixed `ITERATION_BASE_PARAMS`) instead of asking the LLM each round — useful for a controlled sweep. Branches still run normally for data collection if enabled. This mode is **forced on** regardless of the toggle whenever zero branches are enabled at all, since a pure test has no data to run active learning on.

---

## File Map

| File | Role |
|---|---|
| `2026-06-11/protocol-multithreaded.py` | Robot-side script (Opentrons + xArm); runs on the lab PC wired to the hardware |
| `2026-06-11/lib/url.py` | Robot-side HTTP client → mini PC (snapshot, compression-tester status, batch handoff) |
| `run_loop.py` | Mini-PC orchestrator/server — main entry point for a campaign |
| `url_29.py` | Mini-PC HTTP client → robot (`POST /run`, coupon/ring/tip/heater-well bookkeeping) |
| `master_processing.py` | Branch dispatcher (`BRANCH_CONFIG` toggles `curve_segmentation` / `image_processing`) |
| `curve_segmentation.py` | Mechanical curve processing pipeline |
| `membrane_imaging.py` | `image_processing` branch — vision-LLM passthrough by default, legacy pixel-math available |
| `membrane_quality_llm.py` | Dedicated vision-LLM call for qualitative membrane judgment |
| `llm_context.py` | Glue: what reaches the LLM, from which branch, into which CSV column |
| `activeLearning_29.py` | `Generate_report` / `LLM_AL` — the active-learning LLM calls |
| `polymer_additive_bounds.py` | Stock-triangle clamping for `polymer_wt`/`additive_wt` |
| `results_reps.csv` / `results_agg.csv` / `results_agg_llm.csv` | Per-rep, aggregated, and LLM-facing results tables |
| `compression-test-data/` | One subfolder per condition: Newton CSVs, camera jpgs, `params.json` |
| `TESTS/` | `test_master.py`, `test_guardrails.py`, `test_processing.py`, `test_imaging.py`, `test_csv.py`, plus fixture folders |

---

## Where to Focus for Curve Segmentation

The segmentation logic lives in `interpretData()` in `curve_segmentation.py`. The current pain points:

- The **2nd derivative minimum** approach for the elastic boundary is sensitive to noise in the spline — the GAM smoothing level matters a lot
- **Piecewise regression** sometimes fails to converge or picks physically unreasonable breakpoints
- The **Good Fit** check is a loose heuristic (checks slope continuity and boundary alignment within ±3 bar)

These are the areas where improved segmentation logic would have the most impact.
