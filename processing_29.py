import sys
import warnings
import json
from pathlib import Path
import datetime

import matplotlib.pyplot as plt
import numpy as np
import copy
import pandas as pd
import piecewise_regression
from pygam import LinearGAM, s
from scipy.signal import find_peaks, peak_prominences ##NEW -- for second deriv analysis
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

warnings.filterwarnings("ignore")

def namestr(obj, namespace):          #read the file name of data
    return [name for name in namespace if namespace[name] is obj][0]

LOAD_COL = "Ch:Load (N)"
LVDT_COL = "S:LVDT (in)"
SETPOINT_COL = "Set Point ()"

# ── Save config ──────────────────────────────────────────────────────────
SAVE_PLOTS = True   # set False to disable saving
# <<< PATH >>> plots saved beside processing_29.py, not beside run_loop.py
_caller = Path(sys.argv[0]).stem if sys.argv else ""
_ts = datetime.datetime.today().strftime('%Y-%m-%d') if "test" in _caller else datetime.datetime.today().strftime('%Y-%m-%d')
_prefix = "test" if "test" in _caller else "run"
SAVE_ROOT  = Path(__file__).parent / "pipeline-plots/pseudo-runs" / f"{_prefix}-{_ts}"
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
    subset = data[data['strain'] <= 0.3]
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
        return bp1_double if bp1_double is not None else bp1_pw
        #return bp1_pw
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

def goodData_eval(data, predictions):
    # Toe ends at first extremum (local max OR min) of d1 within strain <= 0.2.
    # Curve shape varies: some toes have rising-then-falling d1, others falling-then-rising.
    d1 = np.gradient(predictions, data['strain'].values)
    mask = data['strain'].values <= 0.3
    if not mask.any():
        print("goodData_eval: no data below strain 0.2")
        return None
    d1_region = d1[mask]
    strains_region = data['strain'].values[mask]
    window = max(5, len(d1_region) // 15)
    d1_smooth = pd.Series(d1_region).rolling(window, center=True, min_periods=1).mean().values
    prominence_thresh = (d1_smooth.max() - d1_smooth.min()) * 0.05
    maxima, max_props = find_peaks(d1_smooth, prominence=prominence_thresh)
    minima, min_props = find_peaks(-d1_smooth, prominence=prominence_thresh)
    if len(maxima) == 0 and len(minima) == 0:
        print("goodData_eval: no toe region detected (d1 monotone in 0-0.3)")
        return float(strains_region[0])
    candidates = []
    for idx, prom in zip(maxima, max_props['prominences']):
        candidates.append((idx, prom))
    for idx, prom in zip(minima, min_props['prominences']):
        candidates.append((idx, prom))
    best_idx = max(candidates, key=lambda x: x[1])[0]
    toe_end_strain = float(strains_region[best_idx])
    if toe_end_strain >= 0.29:
        print(f"goodData_eval: WARNING — toe extends to {toe_end_strain:.4f}, data may be invalid")
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
        if r2_p < 0:
            score -= 15
            breakdown['plateau_r2_start'] = (0, w, f'R²(first 40%)={r2_p:.3f} — negative, -15 penalty applied')
        else:
            pts = round(w * max(r2_p, 0))
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

    w = 25
    gam_stress_at_bp1 = float(gam.predict([[breakpoint1]])[0])
    yield_err_pct = abs(float(yieldStrength) - gam_stress_at_bp1) / (gam_stress_at_bp1 + 1e-9)
    pts = round(w * max(0, 1 - yield_err_pct / 0.20))
    breakdown['yield_accuracy'] = (pts, w, f'linear vs GAM err={yield_err_pct*100:.1f}%')
    score += pts

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
        penalty = -20 if r2_full < 0.5 else (-10 if r2_full < 0.7 else 0)
        breakdown['plateau_r2_full_penalty'] = (penalty, 0, f'R²(full)={r2_full:.3f}')
        score += penalty

    if elasticModulus <= 0 or not (10 < elasticModulus < 5000):
        breakdown['elastic_modulus_penalty'] = (-5, 0, f'E={elasticModulus:.1f} bar out of range')
        score -= 5
    else:
        breakdown['elastic_modulus_penalty'] = (0, 0, f'E={elasticModulus:.1f} bar ok')

    # ── CATASTROPHICS (bad DATA indicators — future: route to goodData_eval)

    if slopePlateau > elasticModulus:
        catastrophic = True
        breakdown['catastrophic_slope_vs_modulus'] = (0, 0, f'slope={slopePlateau:.1f} > E={elasticModulus:.1f}')

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
    Comment out the call in process_zero_sample_pairs_pipeline to skip.
    """
    stress_data = []
    strain_data = []

    for df in valid_curves:
        d = df[df['Ch:Load (N)'] > cutoff_load_displacement].copy()
        if 'Set Point ()' in d.columns and (d['Set Point ()'] > 1).any():
            d = d[d['Set Point ()'] <= 1].copy()
        if 'stress (bar)' not in d.columns or 'strain' not in d.columns:
            continue
        d = d.sort_values('stress (bar)').reset_index(drop=True)
        d['strain'] = d['strain'] - d['strain'].iloc[0]
        stress_data.append(d['stress (bar)'].values)
        strain_data.append(d['strain'].values)

    cv = np.nan
    plt.figure(figsize=(8, 5.5))

    if stress_data:
        common_min = max(s[0]  for s in stress_data)
        common_max = min(s[-1] for s in stress_data)
        n_pts      = min(len(s) for s in stress_data)
        common_stress = np.linspace(common_min, common_max, n_pts)

        aligned = np.array([
            np.interp(common_stress, stress, strain)
            for stress, strain in zip(stress_data, strain_data)
        ])
        avg_strain = np.mean(aligned, axis=0)
        ##############CHEKC
        std_strain = np.std(aligned,  axis=0, ddof=1)

        overall_avg = np.mean(avg_strain)
        overall_std = np.mean(std_strain)
        cv = overall_std / overall_avg if overall_avg != 0 else np.nan

        for i, (stress, strain) in enumerate(zip(stress_data, strain_data)):
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
    return cv


#EXTRACT KNOWLEDGE OF A DATA BATCH
def interpretData(data_list, thickness_info = True, thickness_list = None, creep_info = True, cutoff_load_thickness=1, cutoff_load_displacement=2, save_path=None):
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
    if thickness_info:
        thickness = thickness_list
    else:
        for i in range(len(data_list)):
            thickness.append(-data_list[i]["Disp_corrected (um)"][data_list[i]['Ch:Load (N)'] > cutoff_load_thickness].iloc[0])

    #add concentration and heating to returned list
    mechanicalProperties = []
    
    #set up stress strain curve
    for i in range(len(data_list)): 
        data_list[i]['stress (bar)'] = data_list[i]['Ch:Load (N)'] / 19.635 *10      #create stress column which is load / area, the area is 19.635 mm^2
        data_list[i]['strain'] = data_list[i]['Disp_corrected (um)'] / thickness[i]      #create strain column which is displacement / thickness, the thickness is shown above
    
    # Calculate average standard deviation for all data points
    all_stress_data = []
    for i in range(len(data_list)):
        data = data_list[i][data_list[i]['Ch:Load (N)'] > cutoff_load_displacement]
        data['strain'] = data['strain'] - data['strain'].iloc[0]     #shift the data so that the first point is at 0 in 'S:LVDT (in)'
        data = data.reset_index(drop=True)
        all_stress_data.append(data['stress (bar)'].values)

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

        if not validData_eval(thickness[i]):
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
            })
            continue

        #adjust data for interpretation
        data = data_list[i][data_list[i]['Ch:Load (N)'] > cutoff_load_displacement]      
        data['strain'] = data['strain'] - data['strain'].iloc[0]     #shift the data so that the first point is at 0 in 'S:LVDT (in)'
        data = data.reset_index(drop=True)     #resets indexing
        fracture_index = data['stress (bar)'].idxmax()
        has_creep_segment = creep_info and (data['Set Point ()'] > 1).any()
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
        gam = LinearGAM(s(0))
        gam.fit(data[['strain']], data['stress (bar)'])
        predictions = gam.predict(data[['strain']])
        goodData_eval(data, predictions)
        # replace values in predictions that are greater than the predictions[-1] with predictions[-1] but make a copy of the predictions for the plot
        predictions_for_plot = predictions.copy()
        predictions_for_plot[predictions_for_plot > creep_level] = creep_level if creep_level is not None else predictions[-1]
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
        
        breakpoint1 = elastic_peak(data, predictions)
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
            continue

        xPlateau, xDensification, predPlateau, predDensification, changepoint, slopePlateau, slopeDensification, modelPlateau = find_changepoint_fit(data, breakpoint1, bp2, bp3, creep_level)

        if True:
            if elastic_fit_failed:
                good = False
                fit_breakdown = {'_score_final': (0, 100, 'elastic region fit failed — no points to fit')}
                print("  ELASTIC FIT FAILED: breakpoint1 outside data range — score forced to 0")
            else:
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
                    "Changepoint":changepoint, 
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
                    "Average Standard Deviation":avg_standard_deviation}
            mechanicalProperties.append(dict)



            #plotted linear models of each region
            if predElastic is not None:
                plt.plot(elasticRegion['strain'], predElastic, color='blue',  label='Elastic Region', linewidth=3)
            #print(xPlateau)
            if xPlateau['strain'] is not None and predPlateau is not None:
                plt.plot(xPlateau['strain'], predPlateau, color='orange', label="Plateau Region", linewidth=3)
            if xDensification['strain'] is not None and predDensification is not None:
                plt.plot(xDensification['strain'], predDensification, color='green', label="Densification Region", linewidth=3)

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

def load_zero_sample_pairs_by_condition(folder_name, data_root="Data", strict=True, load_dataframes=False):
    base_dir = Path(data_root) / folder_name
    if not base_dir.exists():
        raise FileNotFoundError("Folder not found: {}".format(base_dir))
    result = {}
    for condition_dir in sorted([p for p in base_dir.iterdir() if p.is_dir()]):
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
    )
    #-----------#
    if condition_filter:
        pairs_by_condition = {k: v for k, v in pairs_by_condition.items() if k == condition_filter}
    #-----------#

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
            interpreted = interpretData(
                [processed_sample_curve],
                thickness_info=current_thickness_info,
                thickness_list=current_thickness_list,
                creep_info=creep_info,
                cutoff_load_thickness=cutoff_load_thickness,
                cutoff_load_displacement=cutoff_load_displacement,
                save_path=condition_save_dir / f"rep-{replicate}" / f"Segmentation_rep-{replicate}.png" if SAVE_PLOTS else None,
            )
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

        pre_cv = plot_average_curve(
            condition_processed_curves, condition_valid_curves,
            condition_name=condition_name,
            label="preDiscard" if has_failures else "",
            save_dir=condition_save_dir if SAVE_PLOTS else None,
        )
        pre_cv = pre_cv if pre_cv is not None else np.nan

        if has_failures:
            post_cv = plot_average_curve(
                condition_processed_curves, condition_passing_curves,
                condition_name=condition_name,
                label="postDiscard",
                save_dir=condition_save_dir if SAVE_PLOTS else None,
            )
            post_cv = post_cv if post_cv is not None else np.nan
        else:
            post_cv = pre_cv

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
        }

    return pipeline_result

def formatted_parameters(row):
    keys = ["mixing_temp", "bath_temp", "weight_percent", "volume", "pullcast_speed",
            "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
    return "; ".join(f"{k}={row.get(k)}" for k in keys if row.get(k) is not None)

def save_to_csv(output, data_root=None, output_path=None, aggregate_path=None):
    data_root = Path(data_root) if data_root is not None else Path(__file__).parent
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
            params_path = matches[0] if matches else data_root / "compression-test-data" / condition / "params.json"
            try:
                with open(params_path, "r", encoding="utf-8") as f:
                    params = json.load(f)
                for key in ("mixing_temp", "bath_temp", "weight_percent", "volume",
                            "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"):
                    row_out[key] = params.get(key)
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
                         "Creep Strain", "Strain at 50 bar", "Strain at 80 bar", "Strain at 150 bar",
                         "Strain at 500 bar", "Good Fit", "Good Fit Score", "Good Fit Breakdown", "Average Standard Deviation", "CV",
                         "mixing_temp", "bath_temp", "weight_percent", "volume",
                         "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
        new_df = new_df.reindex(columns=[c for c in rep_col_order if c in new_df.columns])
        if output_path.exists() and output_path.stat().st_size > 0:
            existing = pd.read_csv(output_path)
            existing = existing.loc[:, ~existing.columns.str.startswith('Unnamed')]
            new_df = pd.concat([existing, new_df], ignore_index=True)
        new_df.to_csv(output_path, index=False)

    # LLM CSV — one row per condition, two rows if some reps failed
    if rep_rows:
        mech_cols = ["Thickness", "Elastic Modulus", "Yield Strength", "Changepoint",
                     "Slope Plateau", "Slope Densification", "Creep Strain",
                     "Strain at 50 bar", "Strain at 80 bar", "Strain at 150 bar",
                     "Strain at 500 bar", "CV"]
        param_cols = ["mixing_temp", "bath_temp", "weight_percent", "volume",
                      "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
        no_sd_cols = {"CV"}

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

            def _build_agg_row(name, props_iter, cv_val):
                agg_row = {"name": name, "date": date_val}
                agg_row.update(params_row)
                for k in mech_cols:
                    if k == "CV":
                        agg_row["CV Mean"] = float(cv_val) if cv_val is not None and not (isinstance(cv_val, float) and np.isnan(cv_val)) else np.nan
                        continue
                    vals = []
                    for prop in props_iter:
                        v = prop.get(k)
                        if v is not None:
                            try:
                                vals.append(float(v))
                            except (TypeError, ValueError):
                                pass
                    agg_row[f"{k} Mean"] = float(np.nanmean(vals)) if vals else np.nan
                    if k not in no_sd_cols:
                        agg_row[f"{k} SD"] = float(np.nanstd(vals)) if vals else np.nan
                mech_res = str({f"{k} Mean": agg_row.get(f"{k} Mean") for k in mech_cols if agg_row.get(f"{k} Mean") is not None})
                agg_row["formatted_parameters"] = formatted_parameters(agg_row)
                agg_row["initial_report"] = ""
                agg_row["formatted_parameters_withProp"] = formatted_parameters(agg_row) + "\n\n" + mech_res
                agg_row["final_report"] = ""
                return agg_row

            all_valid_props = [r for r in payload["mechanical_properties"] if r.get("Trial") != "average"]
            pre_row_name = cond_name if not has_failures else f"{cond_name}_preDiscard"
            computed_agg_rows.append(_build_agg_row(pre_row_name, all_valid_props, pre_cv))

            if has_failures:
                passing_props = payload.get("passing_properties", [])
                if passing_props:
                    computed_agg_rows.append(_build_agg_row(f"{cond_name}_postDiscard", passing_props, post_cv))

        interleaved = [col for k in mech_cols for col in ([f"{k} Mean", f"{k} SD"] if k not in no_sd_cols else [f"{k} Mean"])]
        condition_cols = ["mixing_temp", "bath_temp", "weight_percent", "volume",
                          "pullcast_speed", "nitrogen", "coupon_to_bath_wait_time", "nips_bath_wait_time"]
        col_order = (["date", "name"] + condition_cols + ["formatted_parameters", "initial_report"]
                     + interleaved
                     + ["formatted_parameters_withProp", "final_report"])

        new_df = pd.DataFrame(computed_agg_rows).reindex(columns=col_order)
        if aggregate_path.exists() and aggregate_path.stat().st_size > 0:
            existing = pd.read_csv(aggregate_path)
            new_df = pd.concat([existing, new_df], ignore_index=True)
        new_df.to_csv(aggregate_path, index=False)

def promote_to_main(condition_name, source, agg_path, agg_llm_path):
    """
    source: "preDiscard", "postDiscard", or "" (no-failures case).
    Reads the matching row from agg_path and upserts it (with clean name) into agg_llm_path.
    Call with source="" when the condition had no failures (single row in agg CSV).
    Call with source="postDiscard" (default) or "preDiscard" to choose which version feeds the LLM.
    """
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
    main_df.to_csv(agg_llm_path, index=False)
