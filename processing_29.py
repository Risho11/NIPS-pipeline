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

warnings.filterwarnings("ignore")

def namestr(obj, namespace):          #read the file name of data
    return [name for name in namespace if namespace[name] is obj][0]

LOAD_COL = "Ch:Load (N)"
LVDT_COL = "S:LVDT (in)"
SETPOINT_COL = "Set Point ()"

# ── Save config ──────────────────────────────────────────────────────────
SAVE_PLOTS = True   # set False to disable saving
SAVE_ROOT  = Path(__file__).parent / f"pipeline_plots_{datetime.date.today().strftime('%Y-%m-%d')}"
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

def elastic_peak(data, predictions):
    #takes in the data, outputs breakpoint1 - useful in case we want to manually change breakpoint



    #identify the elastic region
    # normal way
    data['2nd derivative'].idxmin()     #found the minimum of the 2nd derivative 
    #breakpoint1 = data['strain'][data['2nd derivative'].idxmin()]

    # ORIGINAL PROCESS
    # Restrict search to strain <= 0.3
    subset = data[data['strain'] <= 0.3]
    
   

    #make GAM on the first derivative (wasnt working originally bc of inf and NaN points)
    
    #boolean because there shouldn't be any infinite points in here
    clean_mask = (
        np.isfinite(data['strain']) & 
        np.isfinite(data['1st derivative']) 
        #(data['strain'] > 0.03)  # <-- This strips out the beginning data
    )
    X_clean = data['strain'][clean_mask].values.reshape(-1, 1) #for the GAM
    y_clean = data['1st derivative'][clean_mask].values
    
    
    gam_d1 = LinearGAM(s(0, n_splines=25, lam=0.5, penalties='derivative')).fit(X_clean, y_clean)
    #replace
    data['1st derivative'] = gam_d1.predict(data['strain'].values.reshape(-1, 1))

    
    data['2nd derivative'] = np.gradient(data['1st derivative'], data['strain'])


    
    #Implement V3 of noise reduction
    spike = data['2nd derivative'].diff().abs()
    data.loc[data['2nd derivative'].abs() > 25000, '2nd derivative'] = np.nan
    data.loc[spike > 150, '2nd derivative'] = np.nan
    data['2nd derivative'] = data['2nd derivative'].interpolate(method='linear')
    subset = data[data['strain'] <= 0.3]
    if subset['strain'][subset['2nd derivative'].idxmin()] <= 0.02:
        subset = data[(data['strain'] > 0.03) & (data['strain'] <= 0.3)].copy() 
    #breakpoint1 = subset['strain'][subset['2nd derivative'].idxmin()]
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

    #strain
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

def goodFit_eval(modelPlateau, predPlateau, breakpoint1, elasticModulus, yieldStrength, xPlateau):
    slopePlateau = modelPlateau.coef_[0]
    #evaluate fit
    plateauModel = LinearGAM(s(0))
    plateauModel.fit(xPlateau[['strain']], xPlateau['stress (bar)'])
    plateauSpline = plateauModel.predict(xPlateau[['strain']])

    correlation_coefficient = np.corrcoef(plateauSpline, predPlateau)[0, 1]
    print(f"Correlation_coefficient: {correlation_coefficient:.4f}")
    
    #ensure the linear models align with each other
    rangeStart = yieldStrength - 3     #arbitrary range
    rangeEnd = yieldStrength + 3

    
    if rangeStart <= modelPlateau.predict(breakpoint1.reshape(1, -1)) <= rangeEnd and slopePlateau <= elasticModulus*1.25 and correlation_coefficient <= 0.98:
        eval = True
    else:
        if breakpoint1 <= 0.05: #arbitrary
            eval = False
        eval = True
    return eval

def plot_average_curve(processed_curves, cutoff_load_displacement=2, condition_name="", save_dir=None):
    """
    Call once per condition (after all reps processed) to show average stress-strain + CV.
    Comment out the call in process_zero_sample_pairs_pipeline to skip.
    """
    stress_data = []
    strain_data = []

    for df in processed_curves:
        d = df[df['Ch:Load (N)'] > cutoff_load_displacement].copy()
        if 'Set Point ()' in d.columns and (d['Set Point ()'] > 1).any():
            d = d[d['Set Point ()'] <= 1].copy()
        if 'stress (bar)' not in d.columns or 'strain' not in d.columns:
            continue
        d = d.sort_values('stress (bar)').reset_index(drop=True)
        d['strain'] = d['strain'] - d['strain'].iloc[0]
        stress_data.append(d['stress (bar)'].values)
        strain_data.append(d['strain'].values)

    if not stress_data:
        return None

    common_min = max(s[0]  for s in stress_data)
    common_max = min(s[-1] for s in stress_data)
    n_pts      = min(len(s) for s in stress_data)
    common_stress = np.linspace(common_min, common_max, n_pts)

    aligned = np.array([
        np.interp(common_stress, stress, strain)
        for stress, strain in zip(stress_data, strain_data)
    ])
    avg_strain = np.mean(aligned, axis=0)
    std_strain = np.std(aligned,  axis=0)

    overall_avg = np.mean(avg_strain)
    overall_std = np.mean(std_strain)
    cv = overall_std / overall_avg if overall_avg != 0 else np.nan

    plt.figure(figsize=(8, 5.5))
    for i, (stress, strain) in enumerate(zip(stress_data, strain_data)):
        plt.plot(strain, stress, alpha=0.35, linewidth=1, label=f"Rep {i+1}")
    plt.plot(avg_strain, common_stress, color='black', linewidth=2.5, label='Average')
    plt.fill_betweenx(common_stress,
                      avg_strain - std_strain,
                      avg_strain + std_strain,
                      color='grey', alpha=0.3, label='+/-1 SD')
    plt.plot([],[], label=f'CV = {cv}')

    plt.xlabel('Strain', fontsize=16)
    plt.ylabel('Stress (bar)', fontsize=16)
    plt.title(condition_name, fontsize=14)
    plt.legend(fontsize=10)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.tight_layout()
    
    if SAVE_PLOTS and save_dir is not None:
        _sd = Path(save_dir)
        _sd.mkdir(parents=True, exist_ok=True)
        plt.savefig(_sd / "Comparison_CV.png", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"CV ({condition_name}): {cv:.4f}")
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

        #calculate the elastic modulus and yield strength
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
            eval = goodFit_eval(modelPlateau, predPlateau, np.array([[breakpoint1]]), elasticModulus, yieldStrength, xPlateau)

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
                    "Good Fit":eval,
                    "Average Standard Deviation":avg_standard_deviation}
            mechanicalProperties.append(dict)



            #plotted linear models of each region
            plt.plot(elasticRegion['strain'], predElastic, color='blue',  label='Elastic Region', linewidth=3)
            plt.plot(xPlateau['strain'], predPlateau, color='orange', label="Plateau Region", linewidth=3)
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


            print(dict)

        
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

        print("Good Fit:", eval)

        

                

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
from datetime import datetime
SPECIMEN_PATTERN = re.compile(r"^Specimen_(\d+)_(\d{8})_(\d{6})\.csv$")
def _parse_specimen_file_info(csv_path):
    name = Path(csv_path).name
    match = SPECIMEN_PATTERN.match(name)
    if not match:
        return None
    specimen_id = int(match.group(1))
    dt_str = "{}{}".format(match.group(2), match.group(3))
    timestamp = datetime.strptime(dt_str, "%m%d%Y%H%M%S")
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
        cluster_gap = 15  # default fallback (minutes)
        params_file = condition_dir / "params.json"
        if params_file.exists():
            try:
                with open(params_file) as _pf:
                    _p = json.load(_pf)
                nips_s = _p.get("nips_bath_wait_time", 900)
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
        ## MAKE CONDITION NAME FOLDER?

        print("=" * 110)
        print("Condition: {} | pairs: {}".format(condition_name, payload["num_pairs"]))

        condition_processed_curves = []
        condition_properties = []

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
                _rep_dir = SAVE_ROOT / condition_name / f"rep-{replicate}"
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
                save_path=SAVE_ROOT / condition_name / f"rep-{replicate}" / f"Segmentation_rep-{replicate}.png" if SAVE_PLOTS else None,
            )
            condition_properties.extend(interpreted)

        # ---- average curve across replicates  ----
        cv = plot_average_curve(condition_processed_curves, condition_name=condition_name, save_dir=SAVE_ROOT / condition_name if SAVE_PLOTS else None)
       
        if cv is not None:
            for prop in condition_properties:
                prop["CV"] = cv
        
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
        }

    return pipeline_result


def save_to_csv(output, data_root=None, output_path=None):
    data_root = Path(data_root) if data_root is not None else Path(__file__).parent
    all_rows = []
    for condition_key in output:
        for trial in output[condition_key]["mechanical_properties"]:
            row_out = trial.copy()
            condition = trial["name"].split(" ")[0]
            # Search all immediate subdirs of data_root for a folder matching condition.
            params_path = None
            for candidate in data_root.iterdir():
                if candidate.is_dir() and (candidate / condition / "params.json").exists():
                    params_path = candidate / condition / "params.json"
                    break
            if params_path is None:
                params_path = data_root / "compression-test-data" / condition / "params.json"
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

    new_df = pd.DataFrame(all_rows)
    output_path = Path(output_path) if output_path is not None else data_root / "output2.csv"
    if output_path.exists():
        existing = pd.read_csv(output_path)
        new_df = pd.concat([existing, new_df], ignore_index=True)
    new_df.to_csv(output_path, index=False)
