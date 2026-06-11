#!/usr/bin/env python3
"""
generate_pipeline_fake_data.py — creates two fake conditions for pipeline-specific CI tests.

Run from this directory:
    python generate_pipeline_fake_data.py

Conditions created:
  pipeline-all-pass  : 3 pairs, all membranes pass Good Fit
  pipeline-some-fail : 3 pairs, 2 membranes pass Good Fit, 1 fails (inverted slope ordering)
                       The failing specimen triggers the catastrophic slopePlateau > elasticModulus
                       flag in goodFit_eval, halving the score below the 70/100 threshold.

CSV format matches the Newton compression tester output.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

AREA_MM2 = 19.635             # specimen area in mm²
COMPLIANCE_UM_PER_N = 0.5     # machine frame compliance (µm/N)
THICKNESS_UM = 200.0          # membrane thickness in µm (well above 50 µm threshold)

# ── stress-strain curves (shifted strain space: 0 = first contact, >0 = compressed) ──

def strain_clean(stress_bar):
    """
    Clean 3-phase elastic→plateau→densification curve.
    Good Fit score > 90.
      elastic:      slope E = 200 bar/unit, strain 0 → 0.15 (stress 0 → 30 bar)
      plateau:      slope   =  20 bar/unit, strain 0.15 → 0.60 (stress 30 → 39 bar)
      densification:slope   = 500 bar/unit, strain 0.60 → 0.83 (stress 39 → 153 bar)
    """
    if stress_bar <= 30:
        return stress_bar / 200.0
    elif stress_bar <= 39:
        return 0.15 + (stress_bar - 30) / 20.0
    else:
        return 0.60 + (stress_bar - 39) / 500.0

def strain_fail(stress_bar):
    """
    Inverted-slope curve: elastic region with low modulus (30 bar), then steep
    post-elastic slope (200 bar). This triggers the catastrophic
    slopePlateau > elasticModulus flag in goodFit_eval, halving the score.
    Good Fit score < 70 (FAIL).
      "elastic":      slope =  30 bar/unit, strain 0 → 0.167 (stress 0 → 5 bar)
      "post-elastic": slope = 200 bar/unit, strain 0.167 → 0.91 (stress 5 → 153 bar)
    """
    if stress_bar <= 5:
        return stress_bar / 30.0
    else:
        return 0.167 + (stress_bar - 5) / 200.0


# ── load profile ──

def make_load_profile():
    """
    Returns (time_arr, load_arr, setpoint_arr) for a single compression test.
    10 Hz, ~550 rows total:
      approach (10 rows):       near-zero load, Set Point -8 → 0
      compression (290 rows):   load 0 → 300 N, Set Point 0 → 1.5
      creep hold (150 rows):    load 300 N, Set Point = 1800
      unload (100 rows):        load 300 → 0 N, Set Point 1800 → 0
    """
    dt = 0.1
    t_list, l_list, sp_list = [], [], []

    for i in range(10):
        t_list.append(round(0.1 + i * dt, 1))
        l_list.append(0.0)
        sp_list.append(-8.0 + i * 0.9)

    n_ramp = 290
    for i in range(n_ramp):
        t_list.append(round(1.1 + i * dt, 1))
        l_list.append(300.0 * i / (n_ramp - 1))
        sp_list.append(1.5 * i / (n_ramp - 1))

    for i in range(150):
        t_list.append(round(30.1 + i * dt, 1))
        l_list.append(300.0)
        sp_list.append(1800.0)

    n_unload = 100
    for i in range(n_unload):
        t_list.append(round(45.1 + i * dt, 1))
        l_list.append(300.0 * (1 - i / (n_unload - 1)))
        sp_list.append(1800.0 * (1 - i / (n_unload - 1)))

    return np.array(t_list), np.array(l_list), np.array(sp_list)


# ── LVDT calculation ──

def zero_lvdt(load_arr):
    """LVDT profile for the zero reference specimen (no membrane, machine compliance only)."""
    return -0.033 + load_arr * COMPLIANCE_UM_PER_N / 25400.0

def specimen_lvdt(load_arr, z_lvdt, strain_fn, thickness=THICKNESS_UM):
    """
    LVDT profile for a membrane specimen.
    Disp_corrected = (shifted_strain - 1) * thickness
    LVDT_sample = LVDT_zero + Disp_corrected / 25400
    """
    lvdt = np.zeros_like(load_arr)
    for i, load in enumerate(load_arr):
        stress = load / AREA_MM2 * 10.0  # N → bar
        s = strain_fn(stress)
        disp_corr = (s - 1.0) * thickness  # µm
        lvdt[i] = z_lvdt[i] + disp_corr / 25400.0
    return lvdt


# ── CSV builder ──

def build_csv(time_arr, load_arr, sp_arr, lvdt_arr, seed=0):
    """Assemble one specimen CSV DataFrame with realistic sensor noise."""
    rng = np.random.default_rng(seed)
    n = len(time_arr)

    load_n = load_arr + rng.normal(0, 0.3, n)
    lvdt_in = lvdt_arr + rng.normal(0, 1e-5, n)
    hl1 = -780.0 + rng.normal(0, 0.05, n)
    sp_n = sp_arr + rng.normal(0, 0.005, n)

    return pd.DataFrame({
        "Time (sec)":       time_arr,
        "S:Load (lbs)":     load_n / 4.44822,
        "S:HL1 (DIM)":      hl1,
        "S:LVDT (in)":      lvdt_in,
        "S:Position (in)":  lvdt_in,
        "Ch:Position (mm)": lvdt_in * 25.4,
        "Ch:Load (N)":      load_n,
        "Ch:Stress (MPa)":  load_n / AREA_MM2,
        "Ch:Strain (mm/mm)": np.zeros(n),
        "Ch:HL1 (DIM)":     hl1,
        "Set Point ()":     sp_n,
        "Cycles ()":        np.zeros(n),
    })


# ── condition creator ──

def create_condition(name, zero_times, mem_times, mem_strain_fns, date="12062026"):
    """
    Build one fake-data condition directory.

    Parameters:
        name           : condition folder name
        zero_times     : list of (h, m, s) tuples for zero-reference specimens
        mem_times      : list of (h, m, s) tuples for membrane specimens
        mem_strain_fns : list of strain functions, one per membrane
        date           : DDMMYYYY string used in filenames
    """
    out_dir = Path(__file__).parent / name
    out_dir.mkdir(exist_ok=True)

    time_arr, load_arr, sp_arr = make_load_profile()
    z_lvdt = zero_lvdt(load_arr)

    # Write zero specimens
    for i, (h, m, s) in enumerate(zero_times):
        df = build_csv(time_arr, load_arr, sp_arr, z_lvdt, seed=i)
        fname = f"Specimen_{i+1}_{date}_{h:02d}{m:02d}{s:02d}.csv"
        df.to_csv(out_dir / fname, index=False)

    # Write membrane specimens
    n_zeros = len(zero_times)
    for j, ((h, m, s), strain_fn) in enumerate(zip(mem_times, mem_strain_fns)):
        mem_lvdt = specimen_lvdt(load_arr, z_lvdt, strain_fn)
        df = build_csv(time_arr, load_arr, sp_arr, mem_lvdt, seed=100 + j)
        fname = f"Specimen_{n_zeros + j + 1}_{date}_{h:02d}{m:02d}{s:02d}.csv"
        df.to_csv(out_dir / fname, index=False)

    params = {
        "mixing_temp": 25,
        "bath_temp": 13,
        "weight_percent": 17,
        "volume": 1000,
        "pullcast_speed": 10,
        "nitrogen": False,
        "coupon_to_bath_wait_time": 120,
        "nips_bath_wait_time": 1800,
    }
    (out_dir / "params.json").write_text(json.dumps(params, indent=2))
    print(f"Created {name}/ ({len(zero_times)} zeros + {len(mem_times)} membranes)")


if __name__ == "__main__":
    # Zero specimens: 10:00, 10:05, 10:10
    # Membrane specimens: 10:40, 10:45, 10:50
    # Gap (30 min) > cluster_gap for nips_bath=1800s (19 min) → correct 2-cluster split
    zero_times = [(10, 0, 0), (10, 5, 0), (10, 10, 0)]
    mem_times  = [(10, 40, 0), (10, 45, 0), (10, 50, 0)]

    create_condition(
        "pipeline-all-pass",
        zero_times,
        mem_times,
        [strain_clean, strain_clean, strain_clean],
    )

    create_condition(
        "pipeline-some-fail",
        zero_times,
        mem_times,
        [strain_clean, strain_clean, strain_fail],   # 3rd membrane fails Good Fit
    )

    print("\nDone. Run validate_fake_data.py to verify file structure.")
