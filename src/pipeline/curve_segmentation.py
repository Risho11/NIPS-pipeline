import sys
import warnings
import json
from pathlib import Path
import datetime

import matplotlib as _mpl
try:
    import IPython as _ipy
    if _ipy.get_ipython() is None:
        _mpl.use('Agg')
except ImportError:
    _mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import copy
import pandas as pd
import piecewise_regression
from pygam import LinearGAM, s
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

warnings.filterwarnings("ignore")

def namestr(obj, namespace):          #read the file name of data
    return [name for name in namespace if namespace[name] is obj][0]

LOAD_COL = "Ch:Load (N)"
LVDT_COL = "S:LVDT (in)"

# ── Data handling config ───────────────────────────────────────────────────────
EXTENDED_CONTEXT    = False  # include _membrane_outcome_string() in result string
PROMOTE_POSTDISCARD = True  # True=LLM sees postDiscard; False=LLM sees preDiscard
USE_FIT_COUNT       = True  # True=n_fit counts Good Fit flag; False=counts _rep_is_usable()

# Single source of truth for per-condition mech/env columns in the aggregate & LLM CSVs.
# "sd": whether an SD column is computed alongside the Mean column.
# "llm": whether this key is included in the mech_res string sent to the LLM.
# To add a new column here (e.g. a new sensor reading), add one entry — mech_cols,
# no_sd_cols, and LLM_PROP_KEYS in save_to_csv() all derive from this automatically.
MECH_PROP_SCHEMA = {
    "Air Temp":          {"sd": False,  "llm": True},
    "Humidity":          {"sd": False,  "llm": True},
    "Thickness":         {"sd": True,  "llm": False},
    "Elastic Modulus":   {"sd": True,  "llm": True},
    "Yield Strength":    {"sd": True,  "llm": False},
    "Pore Fraction":       {"sd": True,  "llm": False},
    "Slope Plateau":     {"sd": True,  "llm": False},
    "Slope Densification": {"sd": True, "llm": False},
    "Creep Strain":      {"sd": True,  "llm": False},
    "Strain at 50 bar":  {"sd": True,  "llm": True},
    "Strain at 80 bar":  {"sd": True,  "llm": False},
    "Strain at 150 bar": {"sd": True,  "llm": False},
    "Strain at 500 bar": {"sd": True,  "llm": False},
    "CV":                {"sd": False, "llm": True},
}
LLM_PROP_KEYS = [k for k, v in MECH_PROP_SCHEMA.items() if v["llm"]]  # mech props sent to the LLM in mech_res

# Per-rep fields that come from the Opentrons (params.json), not from the curve-fit
# output, pulled into each trial dict. Maps trial-dict key -> (params.json top-level key, sub-key).
# Add an entry here (and to MECH_PROP_SCHEMA above) instead of hand-writing injection code.
OT2_FIELDS = {
    "Air Temp": ("air_data", "temperature"),
    "Humidity": ("air_data", "humidity"),
}

SETPOINT_COL = "Set Point ()"

# ── Save config ──────────────────────────────────────────────────────────
SAVE_PLOTS = True   # set False to disable saving
# <<< PATH >>> Only the real run_loop.py gets a "run-" folder; everything
# else (test scripts, run_loopTest, plot_curves, notebooks, etc.) goes to
# pseudo-runs/test-YYYY-MM-DD so Saturday experiments never pollute run history.
_caller = Path(sys.argv[0]).stem if sys.argv else ""
_ts     = datetime.datetime.today().strftime('%Y-%m-%d')
_prefix = "run" if _caller == "run_loop" else "pseudo-runs/test"
SAVE_ROOT  = Path(__file__).resolve().parent.parent.parent / "data" / "plots" / f"{_prefix}-{_ts}"
# ─────────────────────────────────────────────────────────────────────────


def load_curve_data(file_path):
    return pd.read_csv(file_path)

def apply_load_cutoff(df, load_cutoff=1.0, load_col=LOAD_COL):
    return df[df[load_col] >= load_cutoff].copy()

def truncate_sample_keep_creep(
    df,
    lvdt_col=LVDT_COL,
    setpoint_col=SETPOINT_COL,
    creep_threshold=1.0,
    new_col="S:LVDT_shifted (um)",
):
    df = df.sort_index().copy()
    anchor_idx = df.index[-1]
    if setpoint_col in df.columns:
        mask_creep = df[setpoint_col] >= creep_threshold
        if mask_creep.any():
            anchor_idx = df[mask_creep].index[-1]
            df = df.loc[:anchor_idx].copy()
    df[new_col] = (df[lvdt_col]) * 25400.0


    # Remove data after the first point where 'Set Point ()' > 1
    # first_exceed_index = df[df[setpoint_col] > 1].index.min()
    # if not np.isnan(first_exceed_index):  # Check if such a point exists
    #     df = df.loc[:first_exceed_index - 1]  # Truncate data

    return df


def process_curve_raw(file_path, load_cutoff=1.0):
    df = load_curve_data(file_path)
    df_proc = truncate_sample_keep_creep(df)
    df_proc = apply_load_cutoff(df_proc, load_cutoff=load_cutoff)
    return df_proc


def shift_sample_and_zero_curve(
    df_zero,
    df_sample,
    lvdt_col="S:LVDT_shifted (um)",
):  
    df_zero_shift_value = df_zero[lvdt_col].iloc[-1]
    df_zero[lvdt_col] = df_zero[lvdt_col] - df_zero_shift_value
    df_sample[lvdt_col] = df_sample[lvdt_col] - df_zero_shift_value
    return df_zero, df_sample


def subtract_zero_from_sample(
    df_zero,
    df_sample,
    load_col=LOAD_COL,
    zero_disp_col="S:LVDT_shifted (um)",
    sample_disp_col="S:LVDT_shifted (um)",
    new_col="Disp_corrected (um)",
    keep_full_sample_load_range=True,
):
    z = df_zero.sort_values(load_col)
    s = df_sample.sort_values(load_col).copy()
    if not keep_full_sample_load_range:
        min_load = max(z[load_col].min(), s[load_col].min())
        max_load = min(z[load_col].max(), s[load_col].max())
        mask = (s[load_col] >= min_load) & (s[load_col] <= max_load)
        s = s[mask].copy()
    zero_loads = z[load_col].values
    zero_disp = z[zero_disp_col].values
    sample_loads = s[load_col].values
    zero_disp_interp = np.interp(sample_loads, zero_loads, zero_disp)
    s["Zero_interp (um)"] = zero_disp_interp
    s[new_col] = s[sample_disp_col] - zero_disp_interp
    return s

def stress_GAM(gam, strain):
        idx = np.array([[strain]])
        return gam.predict(idx)

def pure_pw(data):
    d1_peak = data["1st derivative"].max()
    low_thresh = d1_peak * 0.15
    in_plateau = data["1st derivative"] < low_thresh
    plateau_start_approx = data["strain"][in_plateau].iloc[0] if in_plateau.any() else 0.1
    plateau_end_approx   = data["strain"][in_plateau].iloc[-1] if in_plateau.any() else 0.5
    cutoff = (plateau_start_approx + plateau_end_approx) / 2
    region = data[data["strain"] <= cutoff]
    try:
        pw_fit = piecewise_regression.Fit(list(region['strain']), list(region['stress (bar)']), n_breakpoints=1)
    except Exception as e:
        print(f"pure_pw regression failed: {e}")
        return None
    pw_results = pw_fit.get_results()
    if pw_results['estimates']:
        return pw_results['estimates']['breakpoint1']['estimate']
    return None

def double_pw(data, bp1_init, interval):
    tightened = data[(data['strain'] >= bp1_init - interval) & (data['strain'] <= bp1_init + interval)]
    try:
        pw_fit = piecewise_regression.Fit(list(tightened['strain']), list(tightened['stress (bar)']), n_breakpoints=1)
    except Exception as e:
        print(f"double_pw regression failed: {e}")
        return None
    pw_results = pw_fit.get_results()
    if pw_results['estimates']:
        return pw_results['estimates']['breakpoint1']['estimate']
    return None

def elastic_peak(data, predictions):
    #takes in the data, outputs breakpoint1 - useful in case we want to manually change breakpoint
    data['2nd derivative'].idxmin()     
    subset = data[data['strain'] <= 0.3]
    clean_mask = (
        np.isfinite(data['strain']) & 
        np.isfinite(data['1st derivative']) 
    )
    X_clean = data['strain'][clean_mask].values.reshape(-1, 1) #for the GAM
    y_clean = data['1st derivative'][clean_mask].values
    
    gam_d1 = LinearGAM(s(0, n_splines=25, lam=0.5, penalties='derivative')).fit(X_clean, y_clean)
    data['1st derivative'] = gam_d1.predict(data['strain'].values.reshape(-1, 1))
    data['2nd derivative'] = np.gradient(data['1st derivative'], data['strain'])

    #Implement V3 of noise reduction
    spike = data['2nd derivative'].diff().abs()
    data.loc[data['2nd derivative'].abs() > 25000, '2nd derivative'] = np.nan
    data.loc[spike > 150, '2nd derivative'] = np.nan
    data['2nd derivative'] = data['2nd derivative'].interpolate(method='linear')
    subset = data[(data['strain'] <= 0.3) & (data['strain'] > 0)]
    if subset.empty or subset['2nd derivative'].isna().all():
        bp1_pw = pure_pw(data)
        return bp1_pw if bp1_pw is not None else float(data['strain'].quantile(0.25))
    if subset['strain'][subset['2nd derivative'].idxmin()] <= 0.02:
        subset = data[(data['strain'] > 0.03) & (data['strain'] <= 0.3)].copy()
    if subset.empty or subset['2nd derivative'].isna().all():
        bp1_pw = pure_pw(data)
        return bp1_pw if bp1_pw is not None else float(data['strain'].quantile(0.25))
    idx_bottom = subset['strain'][subset['2nd derivative'].idxmin()]

    #get slope ig
    subset['raw_slope'] = subset['2nd derivative'].diff() / subset['strain'].diff()
    subset['smooth_slope'] = subset['raw_slope'].rolling(window=5, center=True).mean()

    idx_bottom = subset['2nd derivative'].idxmin()   # This gets the ROW index (e.g. 452)
    strain_bottom = subset.loc[idx_bottom, 'strain'] # This gets the float strain (0.0741)
    val_bottom = subset.loc[idx_bottom, '2nd derivative']

    # 2. Extract left wall metrics
    left_side = subset.loc[:idx_bottom]
    val_start = left_side['2nd derivative'].max()
    idx_start = left_side['2nd derivative'].idxmax()

    # 3. Extract right wall metrics safely
    right_side = subset.loc[idx_bottom:]

    # Isolate the localized recovery window
    local_window = right_side[right_side['strain'] <= (strain_bottom + 0.05)]

    # SAFE GUARD: Verify the window isn't empty before taking max
    if not local_window.empty:
        val_end_peak = local_window['2nd derivative'].max()
    else:
        val_end_peak = right_side['2nd derivative'].max() # Fallback to full right side if narrow

    total_climb_height = val_end_peak - val_bottom

    # 5. Define target flattening threshold (90% up the climb)
    flattening_target_y = val_bottom + (total_climb_height * 0.90)

    # 6. Locate first crossing index cleanly
    recovery_zone = right_side[right_side['2nd derivative'] >= flattening_target_y]
    idx_end = recovery_zone.index[0] if not recovery_zone.empty else right_side.index[-1]

    strain_start = subset.loc[idx_start, 'strain']
    strain_end = subset.loc[idx_end, 'strain']

    # 8. Compute finalized net vertical delta
    val_start = subset.loc[idx_start, '2nd derivative']
    val_end = subset.loc[idx_end, '2nd derivative']
    net_height_drop = val_start - val_end

    # 9. Dynamic segment correction breakpoint routing
    if net_height_drop > 1500 or val_start - val_bottom > 5000:
        breakpoint1 = (strain_bottom + ((strain_end-strain_bottom) / 2.5))
    else:
        breakpoint1 = strain_bottom

    bp1_pw = pure_pw(data)
    #breakpoint1 = find_drop(subset)
    bp1_double = double_pw(data, bp1_pw, 0.1) if bp1_pw is not None else None  #last parameter should be dynamic
    print(f"PW + Double: {bp1_double}")
    if bp1_pw is not None and bp1_pw >= 0 and abs(bp1_pw-breakpoint1) < 0.1:
        print(f"Piecewise Chosen! {bp1_pw} | Drop Calculation: {breakpoint1}")
        return bp1_double if bp1_double is not None and bp1_double <= 0 else bp1_pw
        #return bp1_pw
    if bp1_pw is not None and bp1_pw < 0.2:
        print(f"Piecewise Chosen! {bp1_pw} | Drop Calculation: {breakpoint1}")
        return bp1_double if bp1_double is not None and bp1_double <= 0 else bp1_pw
    print(f"Drop Chosen! {breakpoint1} | Piecewise Calculation: {bp1_pw}")
    if double_pw(data, breakpoint1, 0.07):
        return double_pw(data, breakpoint1, 0.07)
    return breakpoint1

'''PLATEAU/DENSIFICATION - Returns changepoint, modelPlateau, modelDens'''

def find_changepoint_old(data, regions):
    try:
        pw_fit = piecewise_regression.Fit(list(regions['strain']), list(regions['stress (bar)']), n_breakpoints=4)
    except Exception as e:
        print(f"Piecewise regression fitting failed: {e}")
        return None, None
    
    pw_results = pw_fit.get_results()
    
    if pw_results['estimates'] != None:
        breakpoint2 = pw_results['estimates']['breakpoint1']['estimate']
        breakpoint3 = pw_results['estimates']['breakpoint4']['estimate']
        return breakpoint2, breakpoint3
    
    else:
        return None, None
def find_breakpoints(data, regions):
    for n_bp in [4, 2]:
        try:
            pw_fit = piecewise_regression.Fit(list(regions['strain']), list(regions['stress (bar)']), n_breakpoints=n_bp)
        except Exception as e:
            print(f"pw regression failed (n_bp={n_bp}): {e}")
            continue

        pw_results = pw_fit.get_results()
        if pw_results['estimates'] is None:
            continue  # try fewer breakpoints

        if n_bp == 4:
            breakpoint2      = pw_results['estimates']['breakpoint1']['estimate']
            breakpoint3      = pw_results['estimates']['breakpoint4']['estimate']
            breakpoint_extra2 = pw_results['estimates']['breakpoint2']['estimate']
            breakpoint_extra3 = pw_results['estimates']['breakpoint3']['estimate']

            bp2 = (breakpoint_extra2 - 0.05) if breakpoint2 - regions['strain'].iloc[0] < 0.1 else breakpoint2 + 0.01
            bp3 = (breakpoint_extra3 + 0.01) if regions['strain'].iloc[-1] - breakpoint3 < 0.05 else breakpoint3 - 0.03
        else:
            bp2 = pw_results['estimates']['breakpoint1']['estimate']
            bp3 = pw_results['estimates']['breakpoint2']['estimate']

        return bp2, bp3

    return None, None

### RELIES ON THE BP2/BP3 METHOD -- MAY BE SCRAPPED AS NEW METHODS ARE DEVISED
def find_changepoint_fit(data, bp1, bp2, bp3, creep_level):
    plateauRegion = data[(bp1 <= data['strain']) & (data['strain'] <= bp2)]
    densificationRegion = data[bp3 <= data['strain']]
    
    if len(plateauRegion) < 2 or len(densificationRegion) < 2:
        raise ValueError(
            f"fit region too small - plateau = {len(plateauRegion)} pts, densification={len(densificationRegion)} pts"
        )
    #calculate the plateau region slope
    modelPlateau = LinearRegression() 
    modelPlateau.fit(plateauRegion['strain'].values.reshape(-1, 1), plateauRegion['stress (bar)'].values)
    slopePlateau = modelPlateau.coef_[0] #oh so mx + b, coef[0] is the m and intercept is the b
    interceptPlateau = modelPlateau.intercept_

    #calculate the densification region slope
    modelDensification = LinearRegression()
    modelDensification.fit(densificationRegion['strain'].values.reshape(-1, 1), densificationRegion['stress (bar)'].values)
    slopeDensification = modelDensification.coef_[0]
    interceptDensification = modelDensification.intercept_

    #calculate the changepoint between the plateau and densification region
    changepoint = (interceptDensification - interceptPlateau) / (slopePlateau - slopeDensification) #(b2-b1)/(m1-m2)
    xPlateau = data[(bp1 <= data['strain']) & (data['strain'] <= changepoint)]
    xDensification = data[changepoint <= data['strain']]
    ### wait what is this
    predPlateau = None
    predDensification = None
    if len(xDensification) > 0 and len(xPlateau) > 0:
            
        predPlateau = modelPlateau.predict(xPlateau[['strain']])
        predDensification = modelDensification.predict(xDensification[['strain']])
        # replace values in predDensification that are greater than the predictions[-1] with predictions[-1]
        if creep_level is not None:
            predDensification[predDensification > creep_level] = creep_level
    return xPlateau, xDensification, predPlateau, predDensification, changepoint, slopePlateau, slopeDensification, modelPlateau
    
##unused
def create_fit_week3(data, bp1, changepoint, creep_level, bp2=None, bp3=None):
    pass

def validData_eval(thickness):
    # thickness <= 50 (or negative) means membrane didn't dispense
    return thickness > 50


def _partial_props(prop):
    """Properties a bad-fit valid-thickness rep contributes to preDiscard aggregation.
    Edit this when the subset of useful-but-unfitted properties changes."""
    return {"Strain at 50 bar": prop.get("Strain at 50 bar")}


def _rep_is_usable(prop):
    """Counts as a usable rep for n_fit when USE_FIT_COUNT=False.
    Edit this when the 'enough data' criterion changes."""
    v = prop.get("Strain at 50 bar")
    return v is not None and not (isinstance(v, float) and np.isnan(v))


def _outcome_interpretation(n_membrane, n_fit, total, mech_res=""):
    """
    Returns a human+LLM-readable outcome string for a single membrane condition.
    Edit this function as hardware matures — all scenario text lives here.

    n_membrane : int  — replicates where validData_eval passed (membrane detected)
    n_fit      : int  — of those, replicates where Good Fit == True
    total      : int  — total replicates run
    mech_res   : str  — pre-computed mechanical properties string (empty if none)
    """
    measured_line = f"MEASURED: {mech_res}" if mech_res and n_fit > 0 else ""

    if n_membrane == 0:
        return (
            f"OUTCOME: NO_MEMBRANE\n"
            f"INTERPRETATION: Zero replicates detected a membrane ({n_membrane}/{total}). "
            f"The blade likely scraped off all dispensed solution (too much humidity on the substrate surface), "
            f"condensation formed on the coupon before immersion, or the Opentrons failed to dispense. "
            f"This result carries NO information about polymer chemistry or NIPS phase-separation kinetics. "
            f"Do NOT adjust chemical or thermal parameters based on this. "
            f"Check hardware: blade cleanliness, ambient humidity, solution volume in the bottle, and Opentrons tip seal."
        )

    if n_membrane == 1:
        if n_fit == 1:
            return (
                f"OUTCOME: PARTIAL_SINGLE_GOOD_FIT\n"
                f"INTERPRETATION: Only 1/{total} replicate detected a membrane. "
                f"The casting solution most likely ran out before covering the full coupon, or there was a large "
                f"positional offset during the compression test. "
                f"Single-replicate data has no statistical validity — CV and averages are meaningless with N=1. "
                f"Use the measured modulus and strain directionally only to infer a broad trend. "
                f"A wide parameter change is warranted; do not make fine-tuning moves. Low confidence.\n"
                + (measured_line if measured_line else "")
            )
        else:  # n_fit == 0
            return (
                f"OUTCOME: PARTIAL_SINGLE_BAD_FIT\n"
                f"INTERPRETATION: Only 1/{total} replicate detected a membrane AND that single measurement "
                f"failed the fit quality check. No usable mechanical data whatsoever. "
                f"The membrane that formed (if any) was spatially isolated and mechanically degenerate. "
                f"These parameters likely produce an inconsistent, very thin, or structurally collapsed film. "
                f"A major parameter change is needed."
            )

    # 2 <= n_membrane < total  (partial coverage, multiple reps detected)
    if n_membrane < total:
        missing = total - n_membrane
        if n_fit == n_membrane:
            return (
                f"OUTCOME: PARTIAL_COVERAGE_GOOD_FIT\n"
                f"INTERPRETATION: {n_membrane}/{total} replicates detected a membrane; {missing} missed. "
                f"This suggests a minor positional offset during compression testing or a slight solution volume "
                f"shortage that left part of the coupon uncovered. "
                f"The {n_membrane} valid measurements are mechanically reliable but CV should NOT be the primary "
                f"metric here (low N from partial coverage). Focus on strain and modulus for parameter guidance. "
                f"These conditions likely produce a real membrane but with some spatial inconsistency — "
                f"a small adjustment to solution volume or casting speed may improve full-coupon coverage.\n"
                + (measured_line if measured_line else "")
            )
        elif n_fit > 0:
            return (
                f"OUTCOME: PARTIAL_COVERAGE_MIXED_FIT\n"
                f"INTERPRETATION: {n_membrane}/{total} replicates detected a membrane and {n_fit}/{n_membrane} "
                f"of those passed the fit. Partial coverage plus inconsistent fits suggests the membrane is "
                f"near a phase boundary — possibly inadequate evaporation time creating a non-uniform skin layer, "
                f"or humidity interference disrupting phase separation at the surface. "
                f"Use the {n_fit} passing fit(s) directionally but do not over-weight the result. "
                f"A larger parameter change is warranted.\n"
                + (measured_line if measured_line else "")
            )
        else:  # n_fit == 0
            return (
                f"OUTCOME: PARTIAL_COVERAGE_NO_FIT\n"
                f"INTERPRETATION: {n_membrane}/{total} replicates detected a membrane but none passed the "
                f"fit quality check. The membrane that did form was structurally unacceptable — likely a very "
                f"thin skin layer, a collapsed asymmetric structure, or a degenerate sponge with no defined "
                f"elastic/plateau/densification regime. "
                f"These parameters sit near a phase boundary where only poor structures form. "
                f"A major parameter change is needed — consider adjusting polymer concentration, "
                f"evaporation time, or bath temperature significantly."
            )

    # n_membrane == total  (full coverage)
    if n_fit == total:
        return (
            f"OUTCOME: GOOD\n"
            f"INTERPRETATION: All {total}/{total} replicates detected a membrane and all passed quality checks. "
            f"High-confidence result — CV is statistically valid, averages are meaningful. "
            f"Use all measured properties to make precise parameter refinements toward the optimization target "
            f"(maximize modulus). Small, targeted adjustments are appropriate.\n"
            + (measured_line if measured_line else "")
        )
    elif n_fit == total - 1:
        return (
            f"OUTCOME: MOSTLY_GOOD\n"
            f"INTERPRETATION: Full membrane coverage ({n_membrane}/{total}), {n_fit}/{total} fits passed. "
            f"One replicate likely had a localized morphological defect, an edge effect on the coupon, "
            f"or a minor environmental fluctuation during the compression test. "
            f"Reliable result overall — use strain and modulus for parameter guidance but treat CV with caution "
            f"(one outlier was removed in the postDiscard pass). Moderate parameter refinement is appropriate.\n"
            + (measured_line if measured_line else "")
        )
    elif n_fit > 0:
        return (
            f"OUTCOME: POOR_FIT\n"
            f"INTERPRETATION: Full membrane coverage ({n_membrane}/{total}) but only {n_fit}/{total} fit(s) passed. "
            f"The membrane forms consistently but is mechanically inconsistent across the coupon — likely near a "
            f"morphological transition (e.g., spongy vs. finger-like pore structure, or partial skin-layer collapse). "
            f"Most replicates show anomalous compression curves (catastrophic slope, poor junction continuity, "
            f"or inconsistent elastic region). "
            f"Use the {n_fit} passing fit(s) to infer a directional change, but a significant parameter adjustment "
            f"is needed. Do not make fine-tuning moves.\n"
            + (measured_line if measured_line else "")
        )
    else:  # n_fit == 0
        return (
            f"OUTCOME: NO_FIT\n"
            f"INTERPRETATION: A membrane was detected in all {total}/{total} replicates but zero fits passed "
            f"quality checks. This strongly indicates the current parameters produce a structurally degenerate "
            f"membrane — likely a fully collapsed asymmetric structure, a pure sponge morphology with no "
            f"well-defined mechanical phases, or an extremely brittle/weak skin layer that fails before exhibiting "
            f"a normal elastic-plateau-densification response. "
            f"These parameters are mechanically unacceptable. "
            f"A major shift in parameter space is required — significantly change at least one of: "
            f"evaporation time, polymer concentration, or bath temperature."
        )


def _membrane_outcome_string(all_props, mech_res=""):
    """
    Computes membrane/fit counts from all_props and calls _outcome_interpretation.
    all_props : list of per-rep dicts with 'Thickness' and 'Good Fit' keys.
    mech_res  : pre-computed mechanical properties string from _build_agg_row.
    """
    total = len(all_props)
    if total == 0:
        return "OUTCOME: NO_DATA\nINTERPRETATION: No replicate data available for this condition."
    membrane_reps = [p for p in all_props if validData_eval(p.get("Thickness", 0) or 0)]
    n_membrane = len(membrane_reps)
    n_fit = (
        sum(1 for p in membrane_reps if p.get("Good Fit", False))
        if USE_FIT_COUNT
        else sum(1 for p in membrane_reps if _rep_is_usable(p))
    )
    header = f"MEMBRANE DETECTION: {n_membrane}/{total} replicates detected a membrane.\n"
    header += (
        f"FIT DETECTION: {n_fit}/{n_membrane} of detected membranes passed quality checks.\n"
        if n_membrane > 0 else "FIT DETECTION: N/A — no membrane detected.\n"
    )
    return header + _outcome_interpretation(n_membrane, n_fit, total, mech_res)


def _toe_piecewise_knee(data, strain_limit, slope_ratio_max):
    """
    Secondary toe check via piecewise linear regression (1 breakpoint) on raw stress.
    Finds the knee where the curve transitions from a flat pre-contact region to
    elastic loading.

    Validation: slope before breakpoint must be < slope_ratio_max × slope after
    breakpoint. A true flat zone has near-zero first slope; a J-curve has both
    slopes in the same ballpark → fails validation → returns None.
    """
    early = data[data['strain'] <= strain_limit].copy()
    if len(early) < 10:
        return None
    try:
        pw = piecewise_regression.Fit(
            list(early['strain']), list(early['stress (bar)']), n_breakpoints=1
        )
        res = pw.get_results()
    except Exception:
        return None

    if not res or not res.get('estimates'):
        return None

    bp      = res['estimates']['breakpoint1']['estimate']
    alpha1  = res['estimates']['alpha1']['estimate']   # slope of first segment
    beta1   = res['estimates']['beta1']['estimate']    # slope CHANGE at breakpoint

    slope_after = alpha1 + beta1
    if slope_after <= 0:
        return None                     # post-bp slope must be positive (elastic)
    alpha1 = max(alpha1, 0.0)          # treat negative pre-bp slope as 0

    if alpha1 / slope_after >= slope_ratio_max:
        return None                     # first segment not flat enough vs second

    lo = float(early['strain'].iloc[0])
    hi = float(early['strain'].iloc[-1])
    if not (lo < bp < hi):
        return None                     # breakpoint outside valid range

    return float(bp)


def goodData_eval(data, predictions):
    # Flat pre-contact zone only — J-curve onset is real material response, must NOT be masked.
    #
    # Two-stage strategy:
    #
    # Stage 1 — d1 half-max walk (primary, uses GAM spline):
    #   Gate: if median(d1[:5]) >= FLAT_FRACTION × d1_peak, the curve is already
    #   responding from ε=0 → try Stage 2 instead of immediately returning 0.
    #   Walk: find last index where smoothed d1 < 0.5 × d1_peak ("halfway up the peak")
    #   using N_CONSEC consecutive above-threshold points to confirm exit.
    #
    # Stage 2 — piecewise knee (fallback, uses raw stress):
    #   When d1 gate fires, fit a 1-breakpoint piecewise linear to raw stress in the
    #   early region. If the slope before the breakpoint is much smaller than after
    #   (flat→elastic transition), that breakpoint is the toe end. Catches cases where
    #   the GAM spline smooths out a sharp flat zone, making d1 appear elevated early.
    #
    # FLAT_FRACTION: gate sensitivity (d1 stage) and slope-ratio cap (piecewise stage).
    strains = data['strain'].values
    d1 = np.gradient(predictions, strains)

    mask_early = strains <= 0.15
    if not mask_early.any():
        mask_early = strains <= 0.3
    if not mask_early.any():
        print("goodData_eval: no data below strain 0.3 — returning strain[0]")
        return float(strains[0])

    d1_region      = d1[mask_early]
    strains_region = strains[mask_early]

    window    = max(3, len(d1_region) // 20)
    d1_smooth = (pd.Series(d1_region)
                   .rolling(window, center=True, min_periods=1)
                   .mean().values)

    d1_peak = d1_smooth.max()
    if d1_peak <= 0:
        return float(strains_region[0])

    FLAT_FRACTION = 0.15   # d1 gate threshold AND piecewise slope-ratio cap
    N_CONSEC      = 3      # consecutive above-half-max points to confirm toe exit

    # ── Stage 1 gate ─────────────────────────────────────────────────────────────
    gate_n  = min(5, len(d1_region))
    d1_gate = float(np.median(d1_region[:gate_n]))

    if d1_gate >= FLAT_FRACTION * d1_peak:
        # d1 says curve already responding. Try piecewise knee as secondary check.
        bp = _toe_piecewise_knee(data, float(strains_region[-1]), FLAT_FRACTION)
        if bp is not None:
            print(f"Toe end strain (zero point): {bp:.4f} [knee]")
            return bp
        print(f"Toe end strain (zero point): {strains_region[0]:.4f}")
        return float(strains_region[0])

    # ── Stage 1 half-max walk ─────────────────────────────────────────────────────
    i_peak   = int(np.argmax(d1_smooth))
    half_max = 0.5 * d1_peak

    toe_end_idx = 0
    above_count = 0
    for i in range(i_peak + 1):
        if d1_smooth[i] < half_max:
            above_count = 0
            toe_end_idx = i
        else:
            above_count += 1
            if above_count >= N_CONSEC:
                break

    toe_end_strain = float(strains_region[toe_end_idx])
    if toe_end_strain >= 0.14:
        print(f"goodData_eval: WARNING — toe extends to {toe_end_strain:.4f}, may be overestimated")
    else:
        print(f"Toe end strain (zero point): {toe_end_strain:.4f}")
    return toe_end_strain

def goodFit_eval(
    data, elasticRegion, xPlateau, xDensification,
    predElastic, predPlateau, predDensification,
    modelElastic, modelPlateau,
    gam,
    breakpoint1,
    changepoint,
    yieldStrength,
    elasticModulus,
    slopePlateau,
    slopeDensification,
    creep_level=None,
    pass_threshold=60,
):
    score = 0
    breakdown = {}
    data_flags = {}
    catastrophic = False

    # ── SCORED (100 pts): R²s + yield_accuracy + junction_continuity ─────

    w = 30
    if len(elasticRegion) > 1 and predElastic is not None:
        stress = elasticRegion['stress (bar)'].values
        stress_range = stress.max() - stress.min()
        rmse = np.sqrt(np.mean((stress - predElastic) ** 2))
        nrmse_score = max(0.0, 1.0 - rmse / (stress_range + 1e-9))
        pts = round(w * nrmse_score)
        breakdown['elastic_r2'] = (pts, w, f'NRMSE-score={nrmse_score:.3f} (RMSE={rmse:.2f}, range={stress_range:.2f})')
        score += pts

        n = len(elasticRegion)
        if n >= 6:
            h = n // 2
            r2_first = r2_score(stress[:h], predElastic[:h])
            r2_second = r2_score(stress[h:], predElastic[h:])
            consistency_gap = abs(r2_first - r2_second)
            if consistency_gap > 0.15:
                data_flags['elastic_half_consistency'] = f'first-half R²={r2_first:.3f} vs second-half R²={r2_second:.3f} (gap={consistency_gap:.3f})'
    else:
        breakdown['elastic_r2'] = (0, w, 'insufficient data')

    w = 15
    if xPlateau is not None and len(xPlateau) > 1 and predPlateau is not None:
        cutoff = int(len(xPlateau) * 0.40)
        if cutoff >= 2:
            r2_p = r2_score(xPlateau['stress (bar)'].iloc[:cutoff], predPlateau[:cutoff])
        else:
            r2_p = r2_score(xPlateau['stress (bar)'], predPlateau)
        pts = round(w * max(r2_p, 0))  # clamp to 0 — no negative scores
        breakdown['plateau_r2_start'] = (pts, w, f'R²(first 40%)={r2_p:.3f}')
        score += pts
    else:
        breakdown['plateau_r2_start'] = (0, w, 'insufficient data')

    w = 15
    if xDensification is not None and len(xDensification) > 1 and predDensification is not None:
        r2_d = r2_score(xDensification['stress (bar)'], predDensification)
        pts = round(w * max(r2_d, 0))
        breakdown['densification_r2'] = (pts, w, f'R²={r2_d:.3f}')
        score += pts
    else:
        breakdown['densification_r2'] = (0, w, 'insufficient data')

    # yield_accuracy: does the elastic linear fit overshoot/undershoot the raw data near bp1?
    # checks the last 25% of the elastic region (the tail closest to bp1)
    w = 25
    if len(elasticRegion) >= 4 and predElastic is not None:
        tail_start = int(len(elasticRegion) * 0.75)
        tail_actual = elasticRegion['stress (bar)'].values[tail_start:]
        tail_pred = predElastic[tail_start:]
        mean_residual = float(np.mean(tail_actual - tail_pred))  # negative = linear overshoots data
        elastic_stress_range = elasticRegion['stress (bar)'].max() - elasticRegion['stress (bar)'].min()
        overshoot_frac = abs(mean_residual) / (elastic_stress_range + 1e-9)
        direction = "overshoots" if mean_residual < 0 else "undershoots"
        if overshoot_frac > 0.5:
            pts = 0
        elif overshoot_frac > 0.2:
            pts = 20   # -5
        elif overshoot_frac > 0.1:
            pts = 24   # -1
        else:
            pts = 25
        breakdown['yield_accuracy'] = (pts, w, f'elastic tail {direction} data by {overshoot_frac*100:.1f}% of elastic range')
        score += pts
    else:
        breakdown['yield_accuracy'] = (0, w, 'insufficient elastic data for tail check')

    w = 15
    if modelPlateau is not None:
        plateau_at_bp1 = float(modelPlateau.predict([[breakpoint1]])[0])
        junction_err_pct = abs(plateau_at_bp1 - float(yieldStrength)) / (abs(float(yieldStrength)) + 1e-9)
        pts = round(w * max(0, 1 - junction_err_pct / 0.15))
        breakdown['junction_continuity'] = (pts, w, f'gap={junction_err_pct*100:.1f}%')
        score += pts
    else:
        breakdown['junction_continuity'] = (0, w, 'no plateau model')

    # ── PENALTIES (subtracted — bad fit indicators) ───────────────────────

    if xPlateau is not None and len(xPlateau) > 1 and predPlateau is not None:
        r2_full = r2_score(xPlateau['stress (bar)'], predPlateau)
        # only penalise genuinely bad plateau fits — R² < 0.5
        penalty = -10 if r2_full < 0.5 else 0
        breakdown['plateau_r2_full_penalty'] = (penalty, 0, f'R²(full)={r2_full:.3f}')
        score += penalty

    if not (10 < elasticModulus < 5000):
        breakdown['elastic_modulus_penalty'] = (-5, 0, f'E={elasticModulus:.1f} bar out of range')
        score -= 5
    elif elasticModulus <= 0:
        breakdown['elastic_modulus_penalty'] = (-20, 0, f'E={elasticModulus:.1f} not possible')
        score -= 20
    else:
        breakdown['elastic_modulus_penalty'] = (0, 0, f'E={elasticModulus:.1f} bar ok')

    # bp1_accuracy: two sub-checks
    # (A) early-plateau derivative drop — is the GAM still actively bending just after bp1?
    #     a real yield point has the spline settling to a flat slope quickly;
    #     a too-early bp1 keeps losing slope across the first half of the plateau
    bp1_penalty = 0
    bp1_notes = []
    if (changepoint is not None and changepoint > breakpoint1 + 0.05
            and xPlateau is not None and len(xPlateau) > 1):
        window_end = breakpoint1 + (changepoint - breakpoint1) * 0.45
        strain_samples = np.linspace(breakpoint1, window_end, 50)
        gam_preds = gam.predict(strain_samples.reshape(-1, 1)).ravel()
        d1 = np.gradient(gam_preds, strain_samples)
        # smooth noisy GAM derivatives
        d1_smooth = pd.Series(d1).rolling(3, center=True, min_periods=1).mean().values
        d1_start = float(d1_smooth[2])   # a few samples in, past edge noise
        d1_end   = float(d1_smooth[-3])
        if d1_start > 0:
            drop_frac = (d1_start - d1_end) / (d1_start + 1e-9)
            if drop_frac > 0.70:
                bp1_penalty += -20
                bp1_notes.append(f'GAM slope drops {drop_frac*100:.0f}% in early plateau — bp1 too early')
            elif drop_frac > 0.40:
                bp1_penalty += -5
                bp1_notes.append(f'GAM slope drops {drop_frac*100:.0f}% in early plateau — bp1 suspect')
            else:
                bp1_notes.append(f'GAM slope stable in early plateau (drop={drop_frac*100:.0f}%) — ok')
        else:
            bp1_notes.append('GAM already flat at bp1 — ok')

    # (B) remaining-stress safeguard (geometrically extreme cases)
    if xPlateau is not None and len(xPlateau) > 1:
        plateau_strain_range = xPlateau['strain'].max() - xPlateau['strain'].min()
        plateau_stress_rise = slopePlateau * plateau_strain_range
        remaining_stress = data['stress (bar)'].max() - float(yieldStrength)
        rise_fraction = plateau_stress_rise / (remaining_stress + 1e-9)
        if rise_fraction > 0.5:
            bp1_penalty += -30
            bp1_notes.append(f'plateau spans {rise_fraction*100:.0f}% of remaining stress — elastic peak likely wrong')
        else:
            bp1_notes.append(f'plateau spans {rise_fraction*100:.0f}% of remaining stress — ok')

    breakdown['bp1_accuracy_penalty'] = (bp1_penalty, 0, ' | '.join(bp1_notes))
    score += bp1_penalty

    # changepoint_curvature: d² of GAM at changepoint — near-zero means changepoint
    # landed in a linear (densification) region rather than at the true inflection
    if (gam is not None and xDensification is not None and len(xDensification) >= 5
            and abs(slopeDensification) > 1e-3):
        x_start = float(changepoint)
        x_end   = xDensification['strain'].values[-1]
        plateau_width = float(changepoint) - float(breakpoint1) + 1e-9
        expected_d2   = abs(slopeDensification - slopePlateau) / plateau_width
        if expected_d2 >= 1e-3:
            h = max((x_end - x_start) * 0.05, 1e-6)
            x_probe = np.array([[x_start - h], [x_start], [x_start + h]])
            g_probe = gam.predict(x_probe).ravel()
            d1_cp = (g_probe[2] - g_probe[0]) / (2 * h)
            d2_cp = (g_probe[2] - 2 * g_probe[1] + g_probe[0]) / (h ** 2)
            normalized_d2 = max(0.0, d2_cp / (expected_d2 + 1e-9))

            x_scan  = np.linspace(x_start, x_end, 30)
            g_scan  = gam.predict(x_scan.reshape(-1, 1)).ravel()
            d1_scan = np.gradient(g_scan, x_scan)
            d1_ref  = abs(d1_cp) + 1e-9
            still_linear = np.abs(d1_scan - d1_cp) / d1_ref < 0.30
            nonlinear    = np.where(~still_linear)[0]
            linear_frac  = nonlinear[0] / len(x_scan) if len(nonlinear) > 0 else 1.0

            severity = max(0.0, 1.0 - min(normalized_d2, 1.0)) * linear_frac
            cp_pts   = round(-10 * severity)
            cp_note  = f'd2_norm={normalized_d2:.2f}, linear_stretch={linear_frac:.0%}'
            breakdown['changepoint_curvature_penalty'] = (cp_pts, 0, cp_note)
            score += cp_pts

    # slope_ratio: plateau nearly as steep as elastic → no real transition visible
    slope_ratio = slopePlateau / (elasticModulus + 1e-9)
    if slope_ratio < 0.6:
        breakdown['slope_ratio_penalty'] = (0, 0, f'plateau/elastic slope ratio={slope_ratio:.2f} — good separation')
    elif slope_ratio < 0.95:
        # gradient: -5 at 0.6 → -20 at 0.95
        _sr_pen = int(round(-5 - 15 * (slope_ratio - 0.6) / 0.35))
        breakdown['slope_ratio_penalty'] = (_sr_pen, 0, f'plateau/elastic slope ratio={slope_ratio:.2f} — nearly parallel ({_sr_pen} pts)')
        score += _sr_pen

    # ── CATASTROPHICS (bad DATA indicators — future: route to goodData_eval)

    # plateau within 5% of elastic slope → no meaningful transition exists
    if slopePlateau > elasticModulus or slope_ratio >= 1:
        catastrophic = True
        breakdown['catastrophic_slope_vs_modulus'] = (0, 0, f'slope ratio={slope_ratio:.2f} — plateau slope ≥95% of elastic')

    if slopeDensification <= slopePlateau:
        catastrophic = True
        breakdown['catastrophic_slope_ordering'] = (0, 0, f'densif={slopeDensification:.1f} <= plateau={slopePlateau:.1f}')

    pre_catastrophic_score = score
    if catastrophic:
        score = round(score * 0.5)

    breakdown['_score_final'] = (score, 100, 'after catastrophic halving' if catastrophic else 'no catastrophic applied')

    good = score >= pass_threshold
    for k, (pts, max_pts, note) in breakdown.items():
        if k.startswith('_'):
            continue
        print(f"  {k:35s} {pts:2d}/{max_pts}  {note}")
    if catastrophic:
        print(f"  CATASTROPHIC HALVING: {pre_catastrophic_score} → {score}")
    if data_flags:
        print("  DATA FLAGS (no score impact — route to goodData_eval):")
        for k, note in data_flags.items():
            print(f"    {k}: {note}")
    print(f"Score: {score}/100 → {'PASS' if good else 'FAIL'}")
    return good, breakdown

def goodFit_eval_old(modelPlateau, predPlateau, breakpoint1, elasticModulus, yieldStrength, xPlateau):
    slopePlateau = modelPlateau.coef_[0]
    plateauModel = LinearGAM(s(0))
    plateauModel.fit(xPlateau[['strain']], xPlateau['stress (bar)'])
    plateauSpline = plateauModel.predict(xPlateau[['strain']])
    try:
        correlation_coefficient = np.corrcoef(plateauSpline, predPlateau)[0, 1]
    except IndexError:
        correlation_coefficient = 0
    #print(f"Correlation_coefficient: {correlation_coefficient:.4f}")
    rangeStart = yieldStrength - 3
    rangeEnd = yieldStrength + 3
    if rangeStart <= modelPlateau.predict(breakpoint1.reshape(1, -1)) <= rangeEnd and slopePlateau <= elasticModulus*1.25 and correlation_coefficient <= 0.98:
        eval = True
    else:
        if breakpoint1 <= 0.05:
            eval = False
        eval = True
    return eval

def plot_average_curve(processed_curves, valid_curves, cutoff_load_displacement=2, condition_name="", save_dir=None, label=""):
    """
    Call once per condition (after all reps processed) to show average stress-strain + CV.
    Creep region excluded from plot and CV. Returns (cv, avg_df) where avg_df is a
    DataFrame with 'strain' and 'stress (bar)' of the average curve (creep-excluded).
    """
    stress_nc = []
    strain_nc = []
    # full data (with creep) for avg_df return value — strain-indexed
    stress_full = []
    strain_full = []
    creep_starts = []
    creep_ends = []

    for df in valid_curves:
        d_all = df[df['Ch:Load (N)'] > cutoff_load_displacement].copy()
        if 'stress (bar)' not in d_all.columns or 'strain' not in d_all.columns:
            continue

        # full curve sorted by strain
        d_f = d_all.sort_values('strain').reset_index(drop=True)
        d_f['strain'] = d_f['strain'] - d_f['strain'].iloc[0]
        stress_full.append(d_f['stress (bar)'].values)
        strain_full.append(d_f['strain'].values)

        # record creep strain bounds from this rep
        if 'Set Point ()' in d_f.columns and (d_f['Set Point ()'] > 1).any():
            creep_rows = d_f[d_f['Set Point ()'] > 1]
            creep_starts.append(float(creep_rows['strain'].min()))
            creep_ends.append(float(creep_rows['strain'].max()))

        # creep-stripped for CV
        d_nc = d_all[d_all['Set Point ()'] <= 1].copy() if (
            'Set Point ()' in d_all.columns and (d_all['Set Point ()'] > 1).any()
        ) else d_all.copy()
        d_nc = d_nc.sort_values('stress (bar)').reset_index(drop=True)
        d_nc['strain'] = d_nc['strain'] - d_nc['strain'].iloc[0]
        stress_nc.append(d_nc['stress (bar)'].values)
        strain_nc.append(d_nc['strain'].values)

    cv = np.nan
    avg_df = None
    plt.figure(figsize=(8, 5.5))

    if stress_nc:
        # stress-indexed alignment for CV (creep-stripped)
        common_min = max(s[0]  for s in stress_nc)
        common_max = min(s[-1] for s in stress_nc)
        n_pts      = min(len(s) for s in stress_nc)
        common_stress = np.linspace(common_min, common_max, n_pts)
        aligned = np.array([
            np.interp(common_stress, stress, strain)
            for stress, strain in zip(stress_nc, strain_nc)
        ])
        avg_strain = np.mean(aligned, axis=0)
        std_strain = np.std(aligned, axis=0, ddof=1)
        overall_avg = np.mean(avg_strain)
        overall_std = np.mean(std_strain)
        cv = overall_std / overall_avg if overall_avg != 0 else np.nan

        # avg_df: stress-indexed (horizontal) average — same approach as CV averaging
        n_pts_full = max(len(s) for s in stress_nc)
        common_stress_h = np.linspace(common_min, common_max, n_pts_full)
        aligned_h = np.array([
            np.interp(common_stress_h, stress, strain)
            for stress, strain in zip(stress_nc, strain_nc)
        ])
        avg_strain_h = np.mean(aligned_h, axis=0)
        avg_df = pd.DataFrame({
            'strain': avg_strain_h,
            'stress (bar)': common_stress_h,
        })

        for i, (stress, strain) in enumerate(zip(stress_nc, strain_nc)):
            plt.plot(strain, stress, alpha=0.35, linewidth=1, label=f"Rep {i+1}")
        plt.plot(avg_strain, common_stress, color='black', linewidth=2.5, label='Average')
        plt.fill_betweenx(common_stress,
                          avg_strain - std_strain,
                          avg_strain + std_strain,
                          color='grey', alpha=0.3, label='+/-1 SD')
        title = f"{condition_name} — {label}" if label else condition_name
        plt.plot([], [], label=f'CV = {cv}')
        plt.title(title, fontsize=14)
    else:
        _colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        for j, df in enumerate(processed_curves):
            d = df[df['Ch:Load (N)'] > cutoff_load_displacement].copy()
            if 'stress (bar)' not in d.columns or 'Disp_corrected (um)' not in d.columns:
                continue
            plt.scatter(d['Disp_corrected (um)'], d['stress (bar)'],
                        color=_colors[j % len(_colors)], s=1, alpha=0.5, label=f"Rep {j+1}")
        title = f"{condition_name} — {label} — NO VALID CURVES" if label else condition_name + " — NO VALID CURVES"
        plt.title(title, fontsize=14)

    plt.xlabel('Strain', fontsize=16)
    plt.ylabel('Stress (bar)', fontsize=16)
    plt.legend(fontsize=10)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.tight_layout()

    if SAVE_PLOTS and save_dir is not None:
        _sd = Path(save_dir)
        _sd.mkdir(parents=True, exist_ok=True)
        fname = f"Comparison_CV_{label}.png" if label else "Comparison_CV.png"
        plt.savefig(_sd / fname, dpi=150, bbox_inches='tight')
    plt.close()
    tag = f" [{label}]" if label else ""
    print(f"CV ({condition_name}){tag}: {cv}")
    return cv, avg_df


#EXTRACT KNOWLEDGE OF A DATA BATCH
def interpretData(data_list, thickness_info = True, thickness_list = None, creep_info = True, cutoff_load_thickness=1, cutoff_load_displacement=2, save_path=None, skip_preproc=False):
    '''
    Returns mechanical properties of a data batch as a list

    Parameters
    -----
    data_list : list including all the trials read as dataframes
    thickness_info : is True if thickness_list provided and accurate
    thickness_list : if needed, provide manually calculated thickness information
    concentration_true : is True if concentration provided and accurate
    conentration : if needed, provide manually measured concentration

    Returns
    -----
    list - [concentration, heating/no heating, mechanical property dictionaries for each trial]

    see Draft1DerivativeKnowledgeExtraction_AimeeTai.ipynb for example
    '''
    #retrieves thickness information
    thickness = []
    if skip_preproc:
        thickness = [np.nan] * len(data_list)
    elif thickness_info:
        thickness = thickness_list
    else:
        for i in range(len(data_list)):
            thickness.append(-data_list[i]["Disp_corrected (um)"][data_list[i]['Ch:Load (N)'] > cutoff_load_thickness].iloc[0])

    #add concentration and heating to returned list
    mechanicalProperties = []

    #set up stress strain curve
    if not skip_preproc:
        for i in range(len(data_list)):
            data_list[i]['stress (bar)'] = data_list[i]['Ch:Load (N)'] / 19.635 *10      #create stress column which is load / area, the area is 19.635 mm^2
            data_list[i]['strain'] = data_list[i]['Disp_corrected (um)'] / thickness[i]      #create strain column which is displacement / thickness, the thickness is shown above

    # Calculate average standard deviation for all data points
    all_stress_data = []
    for i in range(len(data_list)):
        _d = data_list[i] if skip_preproc else data_list[i][data_list[i]['Ch:Load (N)'] > cutoff_load_displacement]
        _d = _d.copy()
        _d['strain'] = _d['strain'] - _d['strain'].iloc[0]
        _d = _d.reset_index(drop=True)
        all_stress_data.append(_d['stress (bar)'].values)

    min_length = min([len(stress) for stress in all_stress_data])
    truncated_stress_data = [stress[:min_length] for stress in all_stress_data]
    avg_standard_deviation = np.mean([np.std(stress) for stress in truncated_stress_data])
    print("\n\n------------ NEW REP ---------------")
    print(f"Average Standard Deviation: {avg_standard_deviation}")

    #set up for loop for each trial in the batch
    for i in range(len(data_list)):
        #####LOOK HEREE
        plt.figure(figsize=(8, 5.5))
        #retrieve data names
        if 'display_name' in data_list[i].columns and len(data_list[i]['display_name']) > 0:
            data_name = str(data_list[i]['display_name'].iloc[0])
        elif 'name' in data_list[i].columns and len(data_list[i]['name']) > 0:
            data_name = str(data_list[i]['name'].iloc[0])
        elif 'source_file' in data_list[i].columns and len(data_list[i]['source_file']) > 0:
            data_name = str(data_list[i]['source_file'].iloc[0]).rsplit('.', 1)[0]
        else:
            data_name = namestr(data_list[i], globals())
        if 'trial_label' in data_list[i].columns and len(data_list[i]['trial_label']) > 0:
            trial = str(data_list[i]['trial_label'].iloc[0])
        elif 'sample_num' in data_list[i].columns and len(data_list[i]['sample_num']) > 0:
            trial = f"sample {int(data_list[i]['sample_num'].iloc[0])}"
        else:
            trial = data_name.split('_')[-1]

        if not skip_preproc and not validData_eval(thickness[i]):
            print(f"Skipping GAM for {data_name} (thickness={thickness[i]:.1f} µm — no membrane)")
            _raw = data_list[i][data_list[i]['Ch:Load (N)'] > cutoff_load_displacement].copy()
            plt.scatter(_raw['Disp_corrected (um)'], _raw['stress (bar)'],
                        color='lightgrey', s=2, label='Raw Data')
            plt.title(f"{data_name} — no membrane detected", fontsize=12)
            plt.xlabel("Disp_corrected (um)")
            plt.ylabel("stress (bar)")
            plt.legend()
            if SAVE_PLOTS and save_path is not None:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            mechanicalProperties.append({
                'name': data_name,
                'Trial': trial,
                'Thickness': thickness[i],
                'Elastic Modulus': np.nan,
                'Yield Strength': np.nan,
                'Changepoint': np.nan,
                'Slope Plateau': np.nan,
                'Slope Densification': np.nan,
                'Creep Strain': np.nan,
                'Strain at 50 bar': np.nan,
                'Strain at 80 bar': np.nan,
                'Strain at 150 bar': np.nan,
                'Strain at 500 bar': np.nan,
                'Good Fit': False,
                'Good Fit Score': None,
                'Good Fit Breakdown': None,
                'Average Standard Deviation': avg_standard_deviation,
                'Toe Region': np.nan,
            })
            continue

        #adjust data for interpretation
        data = data_list[i].copy() if skip_preproc else data_list[i][data_list[i]['Ch:Load (N)'] > cutoff_load_displacement]
        data['strain'] = data['strain'] - data['strain'].iloc[0]     #shift the data so that the first point is at 0 in 'S:LVDT (in)'
        data = data.reset_index(drop=True)     #resets indexing
        fracture_index = data['stress (bar)'].idxmax()
        has_creep_segment = creep_info and 'Set Point ()' in data.columns and (data['Set Point ()'] > 1).any()
        if has_creep_segment:
            fracture_index = data[data['Set Point ()'] > 1].index[0] #find index of fracture point
            fracture_index += 1
        else:
            fracture_index += 1
        data_original = data.copy()
        data = data.iloc[:fracture_index]     #remove datapoints after fracture point

        creep_strain = None
        creep_level = None
        if has_creep_segment:
            #calculate creep
            creep_segment = data_original[data_original['Set Point ()'] > 1]['stress (bar)']
            creep_level = float(creep_segment.mean())
            #find the data range where set point is greater than 1
            creep_start = data_original[data_original['Set Point ()'] > 1]['strain'].min()
            creep_end = data_original[data_original['Set Point ()'] > 1]['strain'].max()
            # plot a horizontal line between the two points
            plt.hlines(creep_level, creep_start, creep_end, color='red', label='Creep Region', linewidth=3, zorder = 100)
            creep_strain = creep_end - creep_start

        if has_creep_segment:
            # find the index corresponding to the END of creep (last point with Set Point() > 1)
            creep_end_index = data_original[data_original['Set Point ()'] > 1].index[-1] + 1
        else:
            creep_end_index = fracture_index
        

        #generate spline model
        try:
            gam = LinearGAM(s(0))
            gam.fit(data[['strain']], data['stress (bar)'])
            predictions = gam.predict(data[['strain']])
        except Exception as e:
            print(f"  GAM fit failed: {e} — skipping trial")
            mechanicalProperties.append({
                "name": data_name, "Trial": trial, "Thickness": thickness[i],
                "Elastic Modulus": np.nan, "Yield Strength": np.nan, "Changepoint": np.nan,
                "Slope Plateau": np.nan, "Slope Densification": np.nan, "Creep Strain": creep_strain,
                "Strain at 50 bar": np.nan, "Strain at 80 bar": np.nan,
                "Strain at 150 bar": np.nan, "Strain at 500 bar": np.nan,
                "Good Fit": False, "Good Fit Score": 0, "Good Fit Breakdown": None,
                "Average Standard Deviation": avg_standard_deviation,
                "Toe Region": np.nan,
            })
            plt.close()
            continue
        toe_end_strain = goodData_eval(data, predictions)
        # replace values in predictions that are greater than the predictions[-1] with predictions[-1] but make a copy of the predictions for the plot
        predictions_for_plot = predictions.copy()
        _cap = creep_level if creep_level is not None else predictions[-1]
        predictions_for_plot[predictions_for_plot > _cap] = _cap
        #print(gam.summary())
        plt.plot(data['strain'], predictions_for_plot, color='black',label='Spline Model')


        # Compute strain-at-target-stress from GAM predictions on loading segment.
        if 'Set Point ()' in data_original.columns:
            loading_region = data_original[data_original['Set Point ()'] <= 1].copy()
        else:
            loading_region = data_original.copy()

        def strain_at_stress_from_gam(target_stress):
            if loading_region.empty:
                return np.nan
            lr = loading_region[['strain']].dropna().copy()
            if lr.empty:
                return np.nan
            gam_stress = gam.predict(lr[['strain']]).astype(float)
            if target_stress < np.min(gam_stress) or target_stress > np.max(gam_stress):
                return np.nan
            idx = int(np.argmin(np.abs(gam_stress - target_stress)))
            return float(lr['strain'].iloc[idx])
        
        strain_50bar = strain_at_stress_from_gam(50)
        strain_80bar = strain_at_stress_from_gam(80)
        strain_150bar = strain_at_stress_from_gam(150)
        strain_500bar = strain_at_stress_from_gam(500)
        
        # Plot the raw data up to the end of creep region
        plt.scatter(data_original.iloc[:creep_end_index]['strain'], 
                    data_original.iloc[:creep_end_index]['stress (bar)'], 
                    color='lightgrey', label='Raw Data')

        
        #### ELASTIC BREAKPOINT1 STUFF
        #calculate derivative of spline model
        data['1st derivative'] = np.gradient(predictions, data['strain'])
        data['2nd derivative'] = np.gradient(data['1st derivative'], data['strain'])
        subset = data[data['strain'] <= 0.3]
        
        try:
            breakpoint1 = elastic_peak(data, predictions)
        except Exception as e:
            print(f"  elastic_peak failed: {e} — using quantile fallback")
            breakpoint1 = float(data['strain'].quantile(0.25))
        elasticRegion = data[data['strain'] <= breakpoint1]

        if len(elasticRegion) < 2:
            # elastic_peak returned a breakpoint outside the data's strain range
            # (e.g. a degenerate piecewise-regression fit) — retry with a
            # conservative fallback breakpoint before giving up
            breakpoint1 = float(data['strain'].quantile(0.25))
            elasticRegion = data[data['strain'] <= breakpoint1]

        elastic_fit_failed = len(elasticRegion) < 2

        #calculate the elastic modulus and yield strength
        if elastic_fit_failed:
            modelElastic = None
            elasticModulus = 0.0
            yieldStrength = np.array([0.0])
            predElastic = None
        else:
            modelElastic = LinearRegression()
            modelElastic.fit(elasticRegion['strain'].values.reshape(-1, 1), elasticRegion['stress (bar)'].values)
            elasticModulus = modelElastic.coef_[0]
            yieldStrength = modelElastic.predict(np.array([[breakpoint1]]))
            predElastic = modelElastic.predict(elasticRegion[['strain']])

        regions = data[data['strain'] >= breakpoint1]

        bp2, bp3 = find_breakpoints(data, regions)
        if bp2 is None:
            print(f"  find_breakpoints returned None — skipping trial")
            mechanicalProperties.append({
                "name": data_name, "Trial": trial, "Thickness": thickness[i],
                "Elastic Modulus": elasticModulus, "Yield Strength": float(yieldStrength[0]),
                "Changepoint": np.nan, "Slope Plateau": np.nan, "Slope Densification": np.nan,
                "Creep Strain": creep_strain,
                "Strain at 50 bar": strain_50bar, "Strain at 80 bar": strain_80bar,
                "Strain at 150 bar": strain_150bar, "Strain at 500 bar": strain_500bar,
                "Good Fit": False, "Good Fit Score": 0, "Good Fit Breakdown": None,
                "Average Standard Deviation": avg_standard_deviation,
                "Toe Region": toe_end_strain,
            })
            plt.close()
            continue

        try:
            xPlateau, xDensification, predPlateau, predDensification, changepoint, slopePlateau, slopeDensification, modelPlateau = find_changepoint_fit(data, breakpoint1, bp2, bp3, creep_level)
        except ValueError as e:
            print(f"  FIND_CHANGEPOINT_FIT FAILED: {e} - score forced to 0")
            mechanicalProperties.append({
                "name": data_name,
                "Trial": trial,
                "Thickness": thickness[i],
                "Elastic Modulus":elasticModulus,
                "Yield Strength": float(yieldStrength[0]),
                "Changepoint": np.nan,
                "Slope Plateau": np.nan,
                "Slope Densification": np.nan,
                "Creep Strain":creep_strain,
                "Strain at 50 bar":strain_50bar,
                "Strain at 80 bar":strain_80bar,
                "Strain at 150 bar":strain_150bar,
                "Strain at 500 bar":strain_500bar,
                "Good Fit": False,
                "Good Fit Score": 0,
                "Good Fit Breakdown": None,
                "Average Standard Deviation":avg_standard_deviation,
                "Toe Region": toe_end_strain,
            })
            continue
        toe_shaded_end = None
        if True:
            if elastic_fit_failed:
                good = False
                fit_breakdown = {'_score_final': (0, 100, 'elastic region fit failed — no points to fit')}
                print("  ELASTIC FIT FAILED: breakpoint1 outside data range — score forced to 0")
            else:
                try:
                    good, fit_breakdown = goodFit_eval(
                        data, elasticRegion, xPlateau, xDensification,
                        predElastic, predPlateau, predDensification,
                        modelElastic, modelPlateau,
                        gam,
                        breakpoint1,
                        changepoint,
                        float(yieldStrength[0]),
                        elasticModulus,
                        slopePlateau,
                        slopeDensification,
                        creep_level=creep_level,
                        pass_threshold=70,
                    )
                except Exception as e:
                    print(f"  goodFit_eval failed: {e} — score forced to 0")
                    good = False
                    fit_breakdown = {'_score_final': (0, 100, f'goodFit_eval error: {e}')}

            # ── toe-mask retry: if slope inversion detected, mask data before bp1 and refit ──
            if (not skip_preproc
                    and not elastic_fit_failed
                    and 'catastrophic_slope_vs_modulus' in fit_breakdown):
                toe_shaded_end = breakpoint1
                _data_m = data[data['strain'] >= toe_shaded_end].copy().reset_index(drop=True)
                if len(_data_m) >= 10:
                    try:
                        _gam_m = LinearGAM(s(0))
                        _gam_m.fit(_data_m[['strain']], _data_m['stress (bar)'])
                        _pred_m = _gam_m.predict(_data_m[['strain']])
                        _data_m['1st derivative'] = np.gradient(_pred_m, _data_m['strain'])
                        _data_m['2nd derivative'] = np.gradient(_data_m['1st derivative'], _data_m['strain'])
                        try:
                            _bp1_m = elastic_peak(_data_m, _pred_m)
                        except Exception:
                            _bp1_m = float(_data_m['strain'].quantile(0.25))
                        _elR_m = _data_m[_data_m['strain'] <= _bp1_m]
                        if len(_elR_m) < 2:
                            _bp1_m = float(_data_m['strain'].quantile(0.25))
                            _elR_m = _data_m[_data_m['strain'] <= _bp1_m]
                        if len(_elR_m) >= 2:
                            _mE_m = LinearRegression()
                            _mE_m.fit(_elR_m['strain'].values.reshape(-1, 1), _elR_m['stress (bar)'].values)
                            _eMod_m = _mE_m.coef_[0]
                            _ys_m = _mE_m.predict(np.array([[_bp1_m]]))
                            _predE_m = _mE_m.predict(_elR_m[['strain']])
                            _reg_m = _data_m[_data_m['strain'] >= _bp1_m]
                            _bp2_m, _bp3_m = find_breakpoints(_data_m, _reg_m)
                            if _bp2_m is not None:
                                _xPl_m, _xDens_m, _predPl_m, _predDens_m, _cp_m, _slPl_m, _slDens_m, _mPl_m = \
                                    find_changepoint_fit(_data_m, _bp1_m, _bp2_m, _bp3_m, creep_level)
                                _good_m, _bd_m = goodFit_eval(
                                    _data_m, _elR_m, _xPl_m, _xDens_m,
                                    _predE_m, _predPl_m, _predDens_m,
                                    _mE_m, _mPl_m, _gam_m,
                                    _bp1_m, _cp_m, float(_ys_m[0]),
                                    _eMod_m, _slPl_m, _slDens_m,
                                    creep_level=creep_level, pass_threshold=70,
                                )
                                # commit retry results
                                breakpoint1        = _bp1_m
                                elasticRegion      = _elR_m
                                modelElastic       = _mE_m
                                elasticModulus     = _eMod_m
                                yieldStrength      = _ys_m
                                predElastic        = _predE_m
                                bp2, bp3           = _bp2_m, _bp3_m
                                xPlateau           = _xPl_m
                                xDensification     = _xDens_m
                                predPlateau        = _predPl_m
                                predDensification  = _predDens_m
                                changepoint        = _cp_m
                                slopePlateau       = _slPl_m
                                slopeDensification = _slDens_m
                                modelPlateau       = _mPl_m
                                good, fit_breakdown = _good_m, _bd_m
                                toe_end_strain     = toe_shaded_end
                                # recompute strain-at-stress from masked GAM
                                _lr_m = loading_region[loading_region['strain'] >= toe_shaded_end][['strain']].dropna().copy()
                                def _s_at_stress_m(tgt, _lr=_lr_m, _g=_gam_m):
                                    if _lr.empty: return np.nan
                                    gs = _g.predict(_lr[['strain']]).astype(float)
                                    if tgt < gs.min() or tgt > gs.max(): return np.nan
                                    return float(_lr['strain'].iloc[int(np.argmin(np.abs(gs - tgt)))])
                                strain_50bar  = _s_at_stress_m(50)
                                strain_80bar  = _s_at_stress_m(80)
                                strain_150bar = _s_at_stress_m(150)
                                strain_500bar = _s_at_stress_m(500)
                                # overplot masked-region spline (same black, covers toe portion)
                                _cap_m = creep_level if creep_level is not None else _pred_m[-1]
                                _pred_m_plot = _pred_m.copy()
                                _pred_m_plot[_pred_m_plot > _cap_m] = _cap_m
                                plt.plot(_data_m['strain'], _pred_m_plot, color='black', zorder=4)
                                print(f"  toe-mask retry: masked strain < {toe_shaded_end:.4f}, good={_good_m}")
                    except Exception as _e_retry:
                        print(f"  toe-mask retry failed: {_e_retry} — keeping first-pass result")

            '''
            wait why the heck is the dictionary only appended when its like not 0... anyway
            '''
            #dictionary of each trial's mechanical properties
            
            dict = {'name': data_name,
                    #'Auto': Auto,
                    #'Heating': heating,
                    #'Concentration': conc,
                    #'Batch': batch,
                    #'Sample': sample,
                    'Trial': trial,
                    "Thickness": thickness[i],
                    "Elastic Modulus":elasticModulus, 
                    "Yield Strength":yieldStrength[0], 
                    "Pore Fraction":changepoint, 
                    "Slope Plateau":slopePlateau, 
                    "Slope Densification":slopeDensification,
                    "Creep Strain":creep_strain,
                    "Strain at 50 bar":strain_50bar,
                    "Strain at 80 bar":strain_80bar,
                    "Strain at 150 bar":strain_150bar,
                    "Strain at 500 bar":strain_500bar,
                    "Good Fit":good,
                    "Good Fit Score": fit_breakdown.get('_score_final', (None,))[0],
                    "Good Fit Breakdown": json.dumps({k: {'pts': v[0], 'max': v[1], 'note': v[2]} for k, v in fit_breakdown.items()}),
                    "Average Standard Deviation":avg_standard_deviation,
                    "Toe Region": toe_end_strain}
            mechanicalProperties.append(dict)



            #plotted linear models of each region
            if predElastic is not None:
                plt.plot(elasticRegion['strain'], predElastic, color='blue',  label='Elastic Region', linewidth=3, zorder=6)
            #print(xPlateau)
            if xPlateau['strain'] is not None and predPlateau is not None:
                plt.plot(xPlateau['strain'], predPlateau, color='orange', label="Plateau Region", linewidth=3, zorder=6)
            if xDensification['strain'] is not None and predDensification is not None:
                plt.plot(xDensification['strain'], predDensification, color='green', label="Densification Region", linewidth=3, zorder=6)

            # Annotate strain at target stresses (drawn after all data so axis limits are set)
            _ref_points = [
                (50,  strain_50bar,  'mediumpurple'),
                (80,  strain_80bar,  'darkcyan'),
                (150, strain_150bar, 'coral'),
                (500, strain_500bar, 'steelblue'),
            ]
            _ax = plt.gca()
            _xlim, _ylim = _ax.get_xlim(), _ax.get_ylim()
            for stress_val, strain_val, color in _ref_points:
                if strain_val is not None and not np.isnan(strain_val):
                    plt.plot([_xlim[0], strain_val], [stress_val, stress_val], color=color, linestyle=':', linewidth=1, alpha=0.9)
                    plt.plot([strain_val, strain_val], [_ylim[0], stress_val], color=color, linestyle=':', linewidth=1, alpha=0.9,
                             label=f'{stress_val} bar | ε = {strain_val:.3f}')
            _ax.set_xlim(_xlim)
            _ax.set_ylim(_ylim)


            #print(dict)

        
        if toe_shaded_end is not None:
            plt.axvspan(plt.gca().get_xlim()[0], toe_shaded_end,
                        alpha=0.3, color='grey', zorder=0, label='Toe (masked)')
        plt.title(data_name, fontsize=14)
        plt.xlabel('Strain', fontsize=20)
        plt.ylabel('Stress (bar)', fontsize=20)
        plt.legend(loc='upper left', fontsize=11)
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)
        if SAVE_PLOTS and save_path is not None:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()

        # ── derivative plots ──────────────────────────────────────────────────
        if SAVE_PLOTS and save_path is not None:
            _seg_name = Path(save_path).name
            _deriv_name = _seg_name.replace("Segmentation", "Derivatives") if "Segmentation" in _seg_name else "Derivatives_" + _seg_name
            _deriv_path = Path(save_path).parent / _deriv_name
            _bps = {
                "breakpoint1": (breakpoint1, "purple"),
                "bp2":         (bp2,         "blue"),
                "changepoint": (changepoint, "red"),
            }
            if bp3 is not None:
                _bps["bp3"] = (bp3, "orange")
            fig_d, (ax1, ax2) = plt.subplots(2, 1, figsize=(6, 8))
            ax1.plot(data['strain'], data['1st derivative'], color='green', linewidth=1)
            ax1.set_title("1st Derivative", fontsize=12)
            ax1.set_xlabel("Strain"); ax1.set_ylabel("d(stress)/d(strain)")
            ax2.scatter(data['strain'], data['2nd derivative'], color='#e91e8c', s=1)
            ax2.set_title("2nd Derivative", fontsize=12)
            ax2.set_xlabel("Strain"); ax2.set_ylabel("d²(stress)/d(strain²)")
            for _lbl, (_val, _col) in _bps.items():
                if _val is not None and not (isinstance(_val, float) and np.isnan(_val)):
                    ax1.axvline(x=_val, color=_col, linestyle=':', linewidth=1.2, label=_lbl)
                    ax2.axvline(x=_val, color=_col, linestyle=':', linewidth=1.2, label=_lbl)
            ax1.legend(fontsize=8); ax2.legend(fontsize=8)
            fig_d.suptitle(data_name, fontsize=11)
            fig_d.tight_layout()
            fig_d.savefig(_deriv_path, dpi=150, bbox_inches='tight')
            plt.close(fig_d)

        print(f"Good Fit: {good}")

        

                

    return mechanicalProperties

#ADD DATA TO A GLOABL LIST
def extract(materialProperties):   
    '''
    adds data from the interpretData function list to global lists

    Parameters
    -----
    materialProperties : the returned list of the interpretData function

    Returns
    -----
    none

    NEEDS EMPTY GLOBAL LISTS IN CODE BEFORE USE
    '''
    for i in range(len(materialProperties)):
        name.append(materialProperties[i]['name'])
        thickness.append(materialProperties[i]['Thickness'])
        conc.append(materialProperties[0])
        trial.append(materialProperties[i]['Trial'])
            
        elasticModulus.append(materialProperties[i]['Elastic Modulus'])
        yieldStrength.append(materialProperties[i]['Yield Strength'])
        creepStrain.append(materialProperties[i]['Creep Strain'])
        strainAt50Bar.append(materialProperties[i]['Strain at 50 bar'])
        strainAt80Bar.append(materialProperties[i]['Strain at 80 bar'])
        strainAt150Bar.append(materialProperties[i]['Strain at 150 bar'])
        strainAt500Bar.append(materialProperties[i]['Strain at 500 bar'])
        slopePlateau.append(materialProperties[i]['Slope Plateau'])
        slopeDensification.append(materialProperties[i]['Slope Densification'])
        changepoint.append(materialProperties[i]['Changepoint'])
        fit.append(materialProperties[i]["Good Fit"])
        avg_standard_deviation.append(materialProperties[i]["Average Standard Deviation"])

#necessary global lists
name = []
auto = []
heating = []
concentration = []
batch = []
sample = []
trial = []
thickness = []
elasticModulus = []
yieldStrength = []
creepStrain = []
strainAt50Bar = []
strainAt80Bar = []
strainAt150Bar = []
strainAt500Bar = []
slopePlateau = []
slopeDensification = []
changepoint = []
fit = []
avg_standard_deviation = []
conc = []

#CREATE PROPERTY DATA CSV FILE
def propertyDataFile(filename_old, filename_new):
    '''
    creates property_data.csv from global lists of the material properties from the extract and interpretData function
    '''
    propertyData = {'Name':name,
                    'Trial':trial,
                    'Thickness':thickness,
                    'Elastic Modulus':elasticModulus,
                    'Yield Strength':yieldStrength,
                    'Creep Strain':creepStrain,
                    'Strain at 50 bar':strainAt50Bar,
                    'Strain at 80 bar':strainAt80Bar,
                    'Strain at 150 bar':strainAt150Bar,
                    'Strain at 500 bar':strainAt500Bar,
                    'Plateau Slope':slopePlateau,
                    'Densification Slope':slopeDensification,
                    'Changepoint':changepoint,
                    'Fit':fit,
                    'Average Standard Deviation':avg_standard_deviation}

    propertyData = pd.DataFrame(propertyData)
    df_old = pd.read_csv(filename_old)
    propertyData = pd.concat([df_old, propertyData], ignore_index=True)
    propertyData.to_csv(filename_new, index=False)

import re
SPECIMEN_PATTERN = re.compile(r"^Specimen_(\d+)_(\d{8})_(\d{6})\.csv$")
def _parse_specimen_file_info(csv_path):
    from datetime import datetime as _datetime
    name = Path(csv_path).name
    match = SPECIMEN_PATTERN.match(name)
    if not match:
        return None
    specimen_id = int(match.group(1))
    dt_str = "{}{}".format(match.group(2), match.group(3))
    timestamp = _datetime.strptime(dt_str, "%m%d%Y%H%M%S")
    return {
        "path": str(Path(csv_path)),
        "name": name,
        "specimen_id": specimen_id,
        "timestamp": timestamp,
    }
def _pair_chronological_zero_sample(specimen_rows, strict=True, cluster_gap_minutes=15):
    rows_sorted = sorted(specimen_rows, key=lambda row: (row["timestamp"], row["specimen_id"]))
    if len(rows_sorted) == 0:
        return []

    # Split into clusters by time gap.
    # Within a cluster (zero phase or membrane phase): tests ~3-5 min apart.
    # Between zero phase and membrane phase: always ≥30 min (NIPS bath).
    # cluster_gap_minutes=15 cleanly separates zero cluster from membrane cluster.
    # Consecutive cluster pairs = one run: (zeros_cluster, membranes_cluster).
    clusters = [[rows_sorted[0]]]
    for prev, curr in zip(rows_sorted, rows_sorted[1:]):
        gap_min = (curr["timestamp"] - prev["timestamp"]).total_seconds() / 60
        if gap_min > cluster_gap_minutes:
            clusters.append([curr])
        else:
            clusters[-1].append(curr)
    if len(clusters) == 1:
        mid = len(clusters[0]) // 2
        clusters = [clusters[0][:mid], clusters[0][mid:]]
        print(f"Single cluster detected — split in half: {len(clusters[0])} zeros, {len(clusters[1])} membranes")
    if strict and len(clusters) % 2 != 0:
        raise ValueError(
            "Expected even number of clusters (zero+membrane pairs), got {}. "
            "Cluster start times: {}".format(
                len(clusters), [c[0]["timestamp"] for c in clusters]
            )
        )

    pairs = []
    replicate = 1
    for i in range(0, len(clusters), 2): 
        zero_cluster    = clusters[i]
        membrane_cluster = clusters[i + 1]
        if strict and len(zero_cluster) != len(membrane_cluster):
            raise ValueError(
                "Zero cluster ({} specimens) and membrane cluster ({} specimens) sizes differ.".format(
                    len(zero_cluster), len(membrane_cluster)
                )
            )
        for zero_row, sample_row in zip(zero_cluster, membrane_cluster):
            pairs.append({
                "replicate": replicate,
                "zero_file": zero_row["path"],
                "sample_file": sample_row["path"],
                "zero_specimen": zero_row["specimen_id"],
                "sample_specimen": sample_row["specimen_id"],
                "zero_time": zero_row["timestamp"],
                "sample_time": sample_row["timestamp"],
            })
            replicate += 1
    return pairs

def load_zero_sample_pairs_by_condition(folder_name, data_root="Data", strict=True, load_dataframes=False, condition_filter=None):
    base_dir = Path(data_root) / folder_name
    if not base_dir.exists():
        raise FileNotFoundError("Folder not found: {}".format(base_dir))
    result = {}
    for condition_dir in sorted([p for p in base_dir.iterdir() if p.is_dir()]):
        if condition_filter and condition_dir.name != condition_filter:
            continue
        csv_files = sorted(condition_dir.glob("*.csv"))
        specimen_rows = []
        for csv_file in csv_files:
            parsed = _parse_specimen_file_info(csv_file)
            if parsed is not None:
                specimen_rows.append(parsed)
        if len(specimen_rows) == 0:
            continue
        # Derive adaptive cluster gap from params.json so that nips_bath_wait_time
        # short conditions (e.g. 120s → 2min bath → ~8min zero→membrane gap) still
        # get cleanly split into two clusters. Formula: half of NIPS time + 4 min buffer.
        cluster_gap = 15  # default fallback (minutes) MINOR CHANGE
        params_file = condition_dir / "params.json"
        if params_file.exists():
            try:
                with open(params_file) as _pf:
                    _p = json.load(_pf)
                nips_s = _p.get("nips_bath_wait_time", 900)
                if nips_s < 660:
                    cluster_gap = 15
                else:
                    cluster_gap = nips_s / 60 / 2 + 4
            except Exception:
                pass
        pairs = _pair_chronological_zero_sample(specimen_rows, strict=strict, cluster_gap_minutes=cluster_gap)
        if load_dataframes:
            for pair in pairs:
                pair["zero_df"] = pd.read_csv(pair["zero_file"])
                pair["sample_df"] = pd.read_csv(pair["sample_file"])
        result[condition_dir.name] = {
            "condition": condition_dir.name,
            "folder": str(condition_dir),
            "num_files": len(specimen_rows),
            "num_pairs": len(pairs),
            "pairs": pairs,
        }
    return result
def pairs_to_dataframe(pairs_by_condition):
    rows = []
    for condition_name, payload in pairs_by_condition.items():
        for pair in payload["pairs"]:
            rows.append({
                "condition": condition_name,
                "replicate": pair["replicate"],
                "zero_specimen": pair["zero_specimen"],
                "sample_specimen": pair["sample_specimen"],
                "zero_file": pair["zero_file"],
                "sample_file": pair["sample_file"],
                "zero_time": pair["zero_time"],
                "sample_time": pair["sample_time"],
            })
    return pd.DataFrame(rows)

def process_zero_sample_pairs_pipeline(
    folder_name,
    data_root="Data",
    strict=True,
    load_cutoff=1.0,
    thickness_info=False,
    thickness_map=None,
    creep_info=True,
    cutoff_load_thickness=1,
    cutoff_load_displacement=2,
    #-----------#
    condition_filter=None,
    #-----------#
):
    """
    Run the full curve processing pipeline for all paired zero/sample curves in a folder.

    For each pair, this function:
    1) Processes raw curves via process_curve_raw()
    2) Aligns curves via shift_sample_and_zero_curve()
    3) Produces corrected sample via subtract_zero_from_sample()
    4) Shows a diagnostic figure with raw-processed, shifted, and corrected curves
    5) Shows interpretData() output figure for the corrected sample
    """
    pairs_by_condition = load_zero_sample_pairs_by_condition(
        folder_name=folder_name,
        data_root=data_root,
        strict=strict,
        load_dataframes=False,
        condition_filter=condition_filter,
    )

    pipeline_result = {}

    for condition_name, payload in pairs_by_condition.items():
        _cond_base = SAVE_ROOT / condition_name
        if _cond_base.exists():
            _n = 2
            while (SAVE_ROOT / f"{condition_name}_run{_n}").exists():
                _n += 1
            condition_save_dir = SAVE_ROOT / f"{condition_name}_run{_n}"
        else:
            condition_save_dir = _cond_base

        print("=" * 110)
        print("Condition: {} | pairs: {}".format(condition_name, payload["num_pairs"]))

        condition_processed_curves = []
        condition_valid_curves = []
        condition_passing_curves = []
        condition_properties = []
        passing_properties = []

        for pair in payload["pairs"]:
            #MAKE REP FILE?

            zero_file = pair["zero_file"]
            sample_file = pair["sample_file"]
            replicate = pair["replicate"]

            zero_raw_processed = process_curve_raw(zero_file, load_cutoff=load_cutoff)
            sample_raw_processed = process_curve_raw(sample_file, load_cutoff=load_cutoff)

            zero_shifted, sample_shifted = shift_sample_and_zero_curve(
                zero_raw_processed.copy(),
                sample_raw_processed.copy(),
            )

            processed_sample_curve = subtract_zero_from_sample(
                zero_shifted.copy(),
                sample_shifted.copy(),
            )

            display_name = "{} | rep {}".format(condition_name, replicate)
            processed_sample_curve["display_name"] = display_name
            processed_sample_curve["trial_label"] = "sample {}".format(pair["sample_specimen"])
            processed_sample_curve["source_file"] = Path(sample_file).name

            condition_processed_curves.append(processed_sample_curve)

            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            fig.suptitle(display_name, fontsize=14)

            axes[0].plot(
                zero_raw_processed["S:LVDT_shifted (um)"],
                zero_raw_processed[LOAD_COL],
                label="Zero (after process_curve_raw)",
            )
            axes[0].plot(
                sample_raw_processed["S:LVDT_shifted (um)"],
                sample_raw_processed[LOAD_COL],
                label="Sample (after process_curve_raw)",
            )
            axes[0].set_title("Raw Curves (Processed)")
            axes[0].set_xlabel("S:LVDT_shifted (um)")
            axes[0].set_ylabel("Load (N)")
            axes[0].legend(fontsize=8)

            axes[1].plot(
                zero_shifted["S:LVDT_shifted (um)"],
                zero_shifted[LOAD_COL],
                label="Zero (after shift)",
            )
            axes[1].plot(
                sample_shifted["S:LVDT_shifted (um)"],
                sample_shifted[LOAD_COL],
                label="Sample (after shift)",
            )
            axes[1].set_title("Shifted Curves")
            axes[1].set_xlabel("S:LVDT_shifted (um)")
            axes[1].set_ylabel("Load (N)")
            axes[1].legend(fontsize=8)

            axes[2].plot(
                processed_sample_curve["Disp_corrected (um)"],
                processed_sample_curve[LOAD_COL],
                color="black",
                label="Processed sample",
            )
            axes[2].set_title("After subtract_zero_from_sample")
            axes[2].set_xlabel("Disp_corrected (um)")
            axes[2].set_ylabel("Load (N)")
            axes[2].legend(fontsize=8)

            plt.tight_layout()
            if SAVE_PLOTS:
                _rep_dir = condition_save_dir / f"rep-{replicate}"
                _rep_dir.mkdir(parents=True, exist_ok=True)
                fig.savefig(_rep_dir / f"Pre-Processing_rep-{replicate}.png", dpi=150, bbox_inches='tight')
            plt.close()

            if thickness_map is not None and condition_name in thickness_map:
                current_thickness_info = True
                current_thickness_list = [thickness_map[condition_name]]
            else:
                current_thickness_info = thickness_info
                current_thickness_list = None

            #the actual thing
            try:
                interpreted = interpretData(
                    [processed_sample_curve],
                    thickness_info=current_thickness_info,
                    thickness_list=current_thickness_list,
                    creep_info=creep_info,
                    cutoff_load_thickness=cutoff_load_thickness,
                    cutoff_load_displacement=cutoff_load_displacement,
                    save_path=condition_save_dir / f"rep-{replicate}" / f"Segmentation_rep-{replicate}.png" if SAVE_PLOTS else None,
                )
            except Exception as e:
                print(f"  interpretData crashed for rep {replicate}: {e} — recording as Good Fit=False")
                interpreted = [{"name": condition_name, "Trial": str(replicate),
                                "Thickness": np.nan, "Elastic Modulus": np.nan,
                                "Yield Strength": np.nan, "Changepoint": np.nan,
                                "Slope Plateau": np.nan, "Slope Densification": np.nan,
                                "Creep Strain": np.nan, "Strain at 50 bar": np.nan,
                                "Strain at 80 bar": np.nan, "Strain at 150 bar": np.nan,
                                "Strain at 500 bar": np.nan, "Good Fit": False,
                                "Good Fit Score": 0, "Good Fit Breakdown": None,
                                "Average Standard Deviation": np.nan}]
            condition_properties.extend(interpreted)
            if interpreted and validData_eval(interpreted[0].get("Thickness", 0)):
                condition_valid_curves.append(processed_sample_curve)
                if interpreted[0].get("Good Fit", False):
                    condition_passing_curves.append(processed_sample_curve)
                    passing_properties.append(interpreted[0])

        # ---- skip aggregation if no pairs processed ----
        if not condition_properties:
            pipeline_result[condition_name] = {
                "condition": condition_name,
                "processed_curves": condition_processed_curves,
                "mechanical_properties": [],
                "pre_cv": np.nan,
                "post_cv": np.nan,
                "has_failures": False,
                "passing_properties": [],
            }
            continue

        # ---- average curve across replicates ----
        has_failures = len(condition_passing_curves) < len(condition_valid_curves)

        pre_cv, pre_avg_df = plot_average_curve(
            condition_processed_curves, condition_valid_curves,
            condition_name=condition_name,
            label="preDiscard" if has_failures else "",
            save_dir=condition_save_dir if SAVE_PLOTS else None,
        )
        pre_cv = pre_cv if pre_cv is not None else np.nan

        if has_failures:
            post_cv, post_avg_df = plot_average_curve(
                condition_processed_curves, condition_passing_curves,
                condition_name=condition_name,
                label="postDiscard",
                save_dir=condition_save_dir if SAVE_PLOTS else None,
            )
            post_cv = post_cv if post_cv is not None else np.nan
        else:
            post_cv, post_avg_df = pre_cv, pre_avg_df

        # ---- fit average curves ----
        _avg_save_dir = condition_save_dir / "averageFits" if SAVE_PLOTS else None

        # raw average curves saved BEFORE fitting (mirrors pre-processing plot before each rep fit)
        if SAVE_PLOTS and _avg_save_dir is not None and pre_avg_df is not None:
            _panels = [("preDiscard" if has_failures else "average", pre_avg_df, condition_valid_curves)]
            if has_failures and post_avg_df is not None and post_avg_df is not pre_avg_df:
                _panels.append(("postDiscard", post_avg_df, condition_passing_curves))
            n_panels = len(_panels)
            fig, axes = plt.subplots(1, n_panels, figsize=(7 * n_panels, 5.5), squeeze=False)
            _rep_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
            for ax, (_lbl, _df, _reps) in zip(axes[0], _panels):
                for j, _rep_df in enumerate(_reps):
                    _r = _rep_df[_rep_df['Ch:Load (N)'] > cutoff_load_displacement].copy() if 'Ch:Load (N)' in _rep_df.columns else _rep_df.copy()
                    if 'strain' not in _r.columns or 'stress (bar)' not in _r.columns:
                        continue
                    _r = _r.sort_values('strain')
                    _r_strain = _r['strain'] - _r['strain'].iloc[0]
                    ax.plot(_r_strain, _r['stress (bar)'], color=_rep_colors[j % len(_rep_colors)],
                            alpha=0.25, linewidth=1, label=f"Rep {j+1}")
                ax.scatter(_df['strain'], _df['stress (bar)'], s=2, color='black', zorder=5, label='Average')
                if 'Set Point ()' in _df.columns and (_df['Set Point ()'] > 1).any():
                    _cr = _df[_df['Set Point ()'] > 1]
                    _clevel = float(_cr['stress (bar)'].mean())
                    _cstart = float(_cr['strain'].min())
                    _cend   = float(_cr['strain'].max())
                    ax.hlines(_clevel, _cstart, _cend, color='red', linewidth=3, zorder=10, label=f'Creep ~ {_clevel:.1f} bar')
                ax.set_title(f"{condition_name} | {_lbl}", fontsize=12)
                ax.set_xlabel('Strain', fontsize=13)
                ax.set_ylabel('Stress (bar)', fontsize=13)
                ax.legend(fontsize=9)
            fig.tight_layout()
            _avg_save_dir.mkdir(parents=True, exist_ok=True)
            fig.savefig(_avg_save_dir / "raw_average_curves.png", dpi=150, bbox_inches='tight')
            plt.close(fig)

        def _run_avg_fit(avg_df, label, save_dir):
            avg_df["display_name"] = f"{condition_name} | {label}"
            _creep = 'Set Point ()' in avg_df.columns and (avg_df['Set Point ()'] > 1).any()
            result = interpretData(
                [avg_df],
                skip_preproc=True,
                creep_info=_creep,
                save_path=save_dir / f"average_fit_{label}.png" if save_dir is not None else None,
            )
            if result and save_dir is not None:
                _eval = {k: (float(v) if isinstance(v, (int, float, np.floating)) and not (isinstance(v, float) and np.isnan(v)) else (None if isinstance(v, float) and np.isnan(v) else v))
                         for k, v in result[0].items() if k not in ("display_name",)}
                (save_dir / f"average_fit_{label}_eval.json").write_text(json.dumps(_eval))

        if pre_avg_df is not None:
            _label = "preDiscard" if has_failures else "average"
            _run_avg_fit(pre_avg_df, _label, _avg_save_dir)
        if has_failures and post_avg_df is not None:
            _run_avg_fit(post_avg_df, "postDiscard", _avg_save_dir)

        for prop in condition_properties:
            prop["CV"] = pre_cv

        avg_condition_properties = {"name": condition_name, "Trial": "average"}
        numeric_keys = ["Thickness", "Elastic Modulus", "Yield Strength", "Changepoint",
                "Slope Plateau", "Slope Densification", "Creep Strain",
                "Strain at 50 bar", "Strain at 80 bar", "Strain at 150 bar",
                "Strain at 500 bar", "Average Standard Deviation", "CV"]
        for k in numeric_keys:
            vals = [prop[k] for prop in condition_properties if k in prop and prop[k] is not None]
            avg_condition_properties[k] = float(np.nanmean(vals)) if vals else np.nan
        condition_properties.append(avg_condition_properties)
        ## ------- CONDITION_PROPERTIES COMPLETE ----------

        pipeline_result[condition_name] = {
            "condition": condition_name,
            "processed_curves": condition_processed_curves,
            "mechanical_properties": condition_properties,
            "pre_cv": pre_cv,
            "post_cv": post_cv,
            "has_failures": has_failures,
            "passing_properties": passing_properties,
            "pre_avg_df": pre_avg_df,
            "post_avg_df": post_avg_df,
        }

    return pipeline_result

# Fixed/contextual keys included in the LLM-facing "formatted_parameters" text -- never
# LLM-choosable (see run_loop.py's separate PARAMS_SCHEMA for what the LLM actually sets).
# llm_context.py extends this list (e.g. with Air Temp Mean/Humidity Mean) -- edit there,
# not here.
FORMATTED_PARAMS_KEYS = ["mixing_temp", "bath_temp", "polymer_wt", "additive_wt", "pullcast_speed",
                          "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]

def formatted_parameters(row):
    return "; ".join(f"{k}={row.get(k)}" for k in FORMATTED_PARAMS_KEYS if row.get(k) is not None)

def save_to_csv(output, data_root=None, output_path=None, aggregate_path=None):
    data_root = Path(data_root) if data_root is not None else Path(__file__).resolve().parent.parent.parent
    all_rows = []
    for condition_key in output:
        condition_date = datetime.datetime.now().strftime("%Y-%m-%d\n%H:%M:%S")
        for trial in output[condition_key]["mechanical_properties"]:
            row_out = trial.copy()
            row_out["date"] = condition_date
            condition = trial["name"].split(" ")[0]
            # Search up to 2 levels deep under data_root for {condition}/params.json
            matches = sorted(data_root.glob(f"*/{condition}/params.json")) + \
                      sorted(data_root.glob(f"**/{condition}/params.json"))
            params_path = matches[0] if matches else data_root / "data" / "raw" / condition / "params.json"
            try:
                with open(params_path, "r", encoding="utf-8") as f:
                    params = json.load(f)
                for key in ("mixing_temp", "bath_temp", "polymer_wt", "additive_wt",
                            "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"):
                    row_out[key] = params.get(key)
                for trial_key, (top_key, sub_key) in OT2_FIELDS.items():
                    value = (params.get(top_key) or {}).get(sub_key)
                    trial[trial_key] = value
                    row_out[trial_key] = value
            except FileNotFoundError:
                print(f"params.json not found: {params_path}")
            all_rows.append(row_out)

    if not all_rows:
        return
    rep_rows = [r for r in all_rows if r.get("Trial") != "average"]
    agg_rows = [r for r in all_rows if r.get("Trial") == "average"]
    
    # Main CSV. 
    if rep_rows:
        new_df = pd.DataFrame(rep_rows)
        output_path = Path(output_path) if output_path is not None else data_root / "output2.csv"
        aggregate_path = Path(aggregate_path) if aggregate_path is not None else data_root / "LLM_output.csv"
        rep_col_order = ["date", "name", "Trial", "Thickness", "Elastic Modulus",
                         "Yield Strength", "Changepoint", "Slope Plateau", "Slope Densification",
                         "Creep Strain", "Toe Region", "Strain at 50 bar", "Strain at 80 bar", "Strain at 150 bar",
                         "Strain at 500 bar", "Good Fit", "Good Fit Score", "Good Fit Breakdown", "Average Standard Deviation", "CV",
                         "mixing_temp", "bath_temp", "polymer_wt", "additive_wt",
                         "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
        new_df = new_df.reindex(columns=[c for c in rep_col_order if c in new_df.columns])
        if output_path.exists() and output_path.stat().st_size > 0:
            existing = pd.read_csv(output_path)
            existing = existing.loc[:, ~existing.columns.str.startswith('Unnamed')]
            new_df = pd.concat([existing, new_df], ignore_index=True)
        # deduplicate: keep latest row per (condition-name, trial)
        if "date" in new_df.columns and "name" in new_df.columns and "Trial" in new_df.columns:
            new_df["_date_sort"] = pd.to_datetime(
                new_df["date"].astype(str).str.replace(r"\n", " ", regex=True), errors="coerce"
            )
            new_df = new_df.sort_values("_date_sort").drop_duplicates(
                subset=["name", "Trial"], keep="last"
            ).drop(columns=["_date_sort"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        new_df.to_csv(output_path, index=False)

    # LLM CSV — one row per condition, two rows if some reps failed
    if rep_rows:
        mech_cols = list(MECH_PROP_SCHEMA)
        param_cols = ["mixing_temp", "bath_temp", "polymer_wt", "additive_wt",
                      "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
        no_sd_cols = {k for k, v in MECH_PROP_SCHEMA.items() if not v["sd"]}

        computed_agg_rows = []
        rep_df = pd.DataFrame(rep_rows)
        rep_df["_condition"] = rep_df["name"].str.split(" ").str[0]

        for condition_key, payload in output.items():
            if not payload.get("mechanical_properties"):
                continue
            cond_name = payload["condition"]
            has_failures = payload.get("has_failures", False)
            pre_cv = payload.get("pre_cv", np.nan)
            post_cv = payload.get("post_cv", np.nan)
            cond_group = rep_df[rep_df["_condition"] == cond_name]
            date_val = cond_group["date"].iloc[0] if not cond_group.empty else datetime.datetime.now().strftime("%Y-%m-%d\n%H:%M:%S")
            params_row = {p: cond_group[p].iloc[0] if p in cond_group.columns and not cond_group.empty else None for p in param_cols}

            def _build_agg_row(name, props_iter, cv_val, all_props=None):
                agg_row = {"name": name, "date": date_val}
                agg_row.update(params_row)
                for k in mech_cols:
                    if k == "CV":
                        agg_row["CV Mean"] = float(cv_val) if cv_val is not None and not (isinstance(cv_val, float) and np.isnan(cv_val)) else np.nan
                        continue
                    vals = []
                    for prop in props_iter:
                        v = prop.get(k)
                        if v is None and not prop.get("Good Fit", True) and validData_eval(prop.get("Thickness", 0) or 0):
                            v = _partial_props(prop).get(k)
                        if v is not None:
                            try:
                                vals.append(float(v))
                            except (TypeError, ValueError):
                                pass
                    agg_row[f"{k} Mean"] = float(np.nanmean(vals)) if vals else np.nan
                    if k not in no_sd_cols:
                        agg_row[f"{k} SD"] = float(np.nanstd(vals)) if vals else np.nan
                mech_res = str({f"{k} Mean": agg_row.get(f"{k} Mean") for k in LLM_PROP_KEYS if agg_row.get(f"{k} Mean") is not None})
                agg_row["formatted_parameters"] = formatted_parameters(agg_row)
                agg_row["initial_report"] = ""
                _context = all_props if all_props is not None else list(props_iter)
                if EXTENDED_CONTEXT:
                    outcome = "\n" + _membrane_outcome_string(_context, mech_res)
                    print(outcome)
                else:
                    outcome = "\n\n" + mech_res
                agg_row["formatted_parameters_withProp"] = formatted_parameters(agg_row) + outcome
                agg_row["final_report"] = ""
                return agg_row

            all_valid_props = [r for r in payload["mechanical_properties"] if r.get("Trial") != "average"]
            pre_row_name = cond_name if not has_failures else f"{cond_name}_preDiscard"
            computed_agg_rows.append(_build_agg_row(pre_row_name, all_valid_props, pre_cv))

            if has_failures:
                passing_props = payload.get("passing_properties", [])
                if passing_props:
                    computed_agg_rows.append(_build_agg_row(f"{cond_name}_postDiscard", passing_props, post_cv,
                                                            all_props=all_valid_props))
                else:
                    # all reps had bad fits — write postDiscard with params intact, all mech props NaN
                    nan_row = {"name": f"{cond_name}_postDiscard", "date": date_val}
                    nan_row.update(params_row)
                    for k in mech_cols:
                        nan_row[f"{k} Mean"] = np.nan
                        if k not in no_sd_cols:
                            nan_row[f"{k} SD"] = np.nan
                    nan_row["formatted_parameters"] = formatted_parameters(nan_row)
                    nan_row["initial_report"] = ""
                    nan_row["formatted_parameters_withProp"] = (
                        formatted_parameters(nan_row) + "\n" + _membrane_outcome_string(all_valid_props, "")
                    )
                    nan_row["final_report"] = ""
                    computed_agg_rows.append(nan_row)
                    print(f"  All fits failed for {cond_name} — wrote NaN postDiscard row")

        interleaved = [col for k in mech_cols for col in ([f"{k} Mean", f"{k} SD"] if k not in no_sd_cols else [f"{k} Mean"])]
        condition_cols = ["mixing_temp", "bath_temp", "polymer_wt", "additive_wt",
                          "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
        col_order = (["date", "name"] + condition_cols + ["formatted_parameters", "initial_report"]
                     + interleaved
                     + ["formatted_parameters_withProp", "final_report"])

        new_df = pd.DataFrame(computed_agg_rows).reindex(columns=col_order)
        if aggregate_path.exists() and aggregate_path.stat().st_size > 0:
            existing = pd.read_csv(aggregate_path)
            new_df = pd.concat([existing, new_df], ignore_index=True)
        aggregate_path.parent.mkdir(parents=True, exist_ok=True)
        new_df.to_csv(aggregate_path, index=False)

def promote_to_main(condition_name, source, agg_path, agg_llm_path):
    """
    source: "preDiscard", "postDiscard", or "" (no-failures case).
    Reads the matching row from agg_path and upserts it (with clean name) into agg_llm_path.
    Call with source="" when the condition had no failures (single row in agg CSV).
    Call with source="postDiscard" (default) or "preDiscard" to choose which version feeds the LLM.
    No-ops (prints a warning, doesn't raise) if agg_path doesn't exist yet -- e.g. the very first
    condition ever run, or one whose save_to_csv produced no rows at all, means there's genuinely
    nothing to promote, not a bug.
    """
    agg_path = Path(agg_path)
    if not agg_path.exists() or agg_path.stat().st_size == 0:
        print(f"[promote_to_main] {agg_path} doesn't exist yet -- nothing to promote for {condition_name!r}")
        return
    agg_df = pd.read_csv(agg_path)
    target_name = f"{condition_name}_{source}" if source else condition_name
    row = agg_df[agg_df["name"] == target_name].copy()
    if row.empty:
        raise ValueError(f"promote_to_main: no row named {target_name!r} in {agg_path}")
    row["name"] = condition_name
    agg_llm_path = Path(agg_llm_path)
    if agg_llm_path.exists() and agg_llm_path.stat().st_size > 0:
        main_df = pd.read_csv(agg_llm_path)
        main_df = main_df[main_df["name"] != condition_name]
        main_df = pd.concat([main_df, row], ignore_index=True)
    else:
        main_df = row
    agg_llm_path.parent.mkdir(parents=True, exist_ok=True)
    main_df.to_csv(agg_llm_path, index=False)


def promote_condition(condition_name, agg_path, agg_llm_path):
    """Selects pre vs postDiscard source based on PROMOTE_POSTDISCARD flag.
    No-ops (prints a warning, doesn't raise) if agg_path doesn't exist yet -- see promote_to_main."""
    agg_path = Path(agg_path)
    if not agg_path.exists() or agg_path.stat().st_size == 0:
        print(f"[promote_condition] {agg_path} doesn't exist yet -- nothing to promote for {condition_name!r}")
        return
    agg_df = pd.read_csv(agg_path)
    has_post = (agg_df["name"] == f"{condition_name}_postDiscard").any()
    has_pre  = (agg_df["name"] == f"{condition_name}_preDiscard").any()
    if PROMOTE_POSTDISCARD and has_post:
        source = "postDiscard"
    elif has_pre:
        source = "preDiscard"
    else:
        source = ""
    promote_to_main(condition_name, source, agg_path, agg_llm_path)
