# AUTODIAL Pipeline Overview

This is an **automated membrane fabrication and characterization system** for NIPS (Non-solvent Induced Phase Separation) membranes — polymer membranes made by casting a polysulfone solution and immersing it in a bath to trigger phase separation.

The pipeline has three main stages:

---

## Stage 1 — Fabrication (Robot)

The robot (Opentrons) physically makes each membrane batch. The fabrication parameters live in each condition folder's `params.json`:

| Parameter | Meaning |
|---|---|
| `weight_percent` | Polymer concentration (e.g. 17 wt%) |
| `mixing_temp` | Temperature at which solution is heated/mixed |
| `bath_temp` | Temperature of the NIPS water bath |
| `coupon_to_bath_wait_time` | Seconds between casting and bath immersion |
| `nitrogen` | Whether dry N₂ blows over the cast film during the wait |
| `nips_bath_wait_time` | How long the membrane sits in the bath |
| `pullcast_speed` | Blade casting speed (mm/s) |

`pipette.py` handles liquid-handling (aspirating/dispensing polymer solution) over HTTP to a pipette robot endpoint.

---

## Stage 2 — Mechanical Testing (Compression Tester + Server)

After fabrication, membrane coupons are compression-tested. The condition folder name encodes the parameters (e.g. `17-13deg-60s-N2-1800s` = 17 wt%, 13°C bath, 60s wait, with N₂, 1800s bath time).

Each test produces a CSV per specimen with columns:
- `Ch:Load (N)` — force applied
- `S:LVDT (in)` — displacement from the LVDT sensor
- `Set Point ()` — control signal; goes above 1.0 during the **creep hold** phase

Each **batch of 6 CSVs** = 3 zero curves (no membrane, machine compliance only) + 3 sample curves (membrane in place). These are paired chronologically (first 3 = zeros, last 3 = samples).

`server.py` runs as an HTTP server on the Opentrons PC and:
1. Receives fabrication parameters via POST `/server/process`
2. Copies the latest 6 CSVs + 2 camera images into a new condition folder
3. Writes `params.json` into that folder
4. Immediately calls the curve processing pipeline on all data collected so far
5. Saves results to `output2.csv`

Camera snapshots (pre/post compression) are taken via GET `/camera/snapshot`.

---

## Stage 3 — Curve Processing (`processing2.py`)

This is the core of the analysis. It runs as a pipeline called `process_zero_sample_pairs_pipeline()`.

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

### Step C: Stress-strain construction — `compute_thickness_stress_strain()`

- **Thickness** is read from `Disp_corrected` at the 1 N load cutoff point (the membrane's initial displacement at first contact = its thickness)
- **Strain** = corrected displacement / thickness
- **Stress** = Load / cross-sectional area (19.63 mm²) × 10 → bar

### Step D: Curve segmentation — `interpretData()` ← your work

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
4. **Piecewise regression** (`piecewise_regression`, 4 breakpoints) on everything after `breakpoint1` → finds the plateau-to-densification transition
5. Linear fits on each identified region → plateau slope, densification slope, changepoint
6. A `Good Fit` flag is set based on continuity checks between the region boundaries

**Output properties per specimen:**

| Property | Description |
|---|---|
| Elastic Modulus | Slope of the elastic region (bar) |
| Yield Strength | Stress at end of elastic region (bar) |
| Changepoint | Strain at plateau-to-densification transition |
| Slope Plateau | Slope of plateau region |
| Slope Densification | Slope of densification region |
| Creep Strain | Strain accumulated during creep hold |
| Strain at 50/80/150/500 bar | Strain values at fixed stress levels (from GAM) |
| Good Fit | Boolean quality flag |

### Step E: Output — `save_to_csv()`

All mechanical properties are merged with the fabrication `params.json` for that condition and appended to `output2.csv`, building up a dataset of fabrication parameters vs. mechanical outcomes.

---

## Active Learning Loop (`activeLearning.py`)

After enough data is collected, `LLM_AL()` sends all prior observations to an LLM (Claude via OpenRouter) and asks it to recommend the next set of fabrication parameters to maximize elastic modulus. This closes the loop:

```
Robot fabricates → Compression test → Curve processing → LLM suggests next params → Robot fabricates → ...
```

`Generate_report()` can also translate a raw `params.json` into a short human-readable experimental report using the LLM.

---

## File Map

| File | Role |
|---|---|
| `server.py` | HTTP server on Opentrons PC; triggers data collection and processing after each batch |
| `processing2.py` | Main curve processing pipeline (your focus) |
| `processing.py` | Older version of curve processing (reference only) |
| `activeLearning.py` | LLM-based active learning loop |
| `pipette.py` | Liquid-handling robot control |
| `manualprocess.py` | Manually triggers the processing pipeline (for debugging without the server) |
| `compression-test-data/` | One subfolder per condition; each contains 6 CSVs, 2 images, and `params.json` |
| `output2.csv` | Master results table (fabrication params + mechanical properties) |

---

## Where to Focus for Curve Segmentation

The segmentation logic lives in `interpretData()` in `processing2.py`. The current pain points:

- The **2nd derivative minimum** approach for the elastic boundary is sensitive to noise in the spline — the GAM smoothing level matters a lot
- **Piecewise regression** with fixed `n_breakpoints=4` sometimes fails to converge or picks physically unreasonable breakpoints
- The **Good Fit** check is a loose heuristic (checks slope continuity and boundary alignment within ±3 bar)

These are the areas where improved segmentation logic would have the most impact.
