# imports
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import piecewise_regression
from pygam import LinearGAM, s
from sklearn.linear_model import LinearRegression

warnings.filterwarnings("ignore")

LOAD_COL = "Ch:Load (N)"
LVDT_COL = "S:LVDT (in)"
SETPOINT_COL = "Set Point ()"

# helper functions
def load_curve_data(file_path):
    return pd.read_csv(file_path)

def find_max_load_index_under_setpoint(
    df,
    load_col=LOAD_COL,
    setpoint_col=SETPOINT_COL,
    setpoint_threshold=1.0,
):
    if setpoint_col is None:
        return int(df[load_col].idxmax())
    mask = df[setpoint_col] < setpoint_threshold
    df_valid = df[mask]
    if df_valid.empty:
        return None
    return int(df_valid[load_col].idxmax())

def find_index_closest_load_under_setpoint(
    df,
    target_load,
    load_col=LOAD_COL,
    setpoint_col=SETPOINT_COL,
    setpoint_threshold=1.0,
):
    if setpoint_col is not None:
        mask = df[setpoint_col] < setpoint_threshold
        df_valid = df[mask]
        if df_valid.empty:
            df_valid = df
    else:
        df_valid = df
    idx = (df_valid[load_col] - target_load).abs().idxmin()
    return int(idx)

def shift_lvdt_to_zero_at_index(
    df,
    idx,
    lvdt_col=LVDT_COL,
    new_col="S:LVDT_shifted (um)",
):
    df = df.sort_index()
    df_trunc = df.loc[:idx].copy()
    lvdt_at_idx = df_trunc.loc[idx, lvdt_col]
    df_trunc[new_col] = (df_trunc[lvdt_col] - lvdt_at_idx) * 25400.0
    return df_trunc

def truncate_and_convert_lvdt_no_shift(
    df,
    idx,
    lvdt_col=LVDT_COL,
    new_col="S:LVDT_shifted (um)",
):
    df = df.sort_index()
    df_trunc = df.loc[:idx].copy()
    df_trunc[new_col] = df_trunc[lvdt_col] * 25400.0
    return df_trunc

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
    lvdt_at_idx = df.loc[anchor_idx, lvdt_col]
    df[new_col] = (df[lvdt_col] - lvdt_at_idx) * 25400.0
    return df

def apply_load_cutoff(df, load_cutoff=1.0, load_col=LOAD_COL):
    return df[df[load_col] >= load_cutoff].copy()

def process_curve_raw(file_path, zero_curve=True, load_cutoff=1.0):
    df = load_curve_data(file_path)
    if zero_curve:
        idx = find_max_load_index_under_setpoint(df)
        if idx is None:
            raise ValueError("No rows found with {} < 1.0".format(SETPOINT_COL))
        df_proc = shift_lvdt_to_zero_at_index(df, idx)
    else:
        df_proc = truncate_sample_keep_creep(df)
    df_proc = apply_load_cutoff(df_proc, load_cutoff=load_cutoff)
    return df_proc

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

def compute_thickness_stress_strain(
    df_corrected,
    load_col=LOAD_COL,
    disp_corrected_col="Disp_corrected (um)",
    area_mm2=19.63,
    load_cutoff=1.0,
):
    df = df_corrected.copy()
    idx_thickness = (df[load_col] - load_cutoff).abs().idxmin()
    disp_at_cutoff_um = df.loc[idx_thickness, disp_corrected_col]
    thickness_um = abs(disp_at_cutoff_um)
    thickness_mm = thickness_um / 1000.0
    if thickness_um == 0:
        raise ValueError("Thickness computed as zero; check corrected displacement.")
    df["Disp_corrected_mm"] = df[disp_corrected_col] / 1000.0
    df["Strain"] = df["Disp_corrected_mm"] / thickness_mm
    stress_mpa = df[load_col] / area_mm2
    df["Stress_bar"] = stress_mpa * 10.0
    min_disp = df[disp_corrected_col].min()
    df["Disp_shifted (um)"] = df[disp_corrected_col] - min_disp
    min_strain = df["Strain"].min()
    df["Strain_shifted"] = df["Strain"] - min_strain
    return df, thickness_um

def extract_sample_thickness_info(condition_label, sample_index, df_ss, thickness_um):
    df = df_ss.copy().sort_index()
    sample_label = "{}_{}".format(condition_label, sample_index)
    initial_thickness = thickness_um
    if SETPOINT_COL in df.columns:
        mask_before = df[SETPOINT_COL] < 1.0
        if mask_before.any():
            df_before = df[mask_before]
            idx_max_before = df_before[LOAD_COL].idxmax()
        else:
            idx_max_before = df[LOAD_COL].idxmax()
    else:
        idx_max_before = df[LOAD_COL].idxmax()
    thickness_at_maxload = abs(df.loc[idx_max_before, "Disp_corrected (um)"])
    stress_at_max = df.loc[idx_max_before, "Stress_bar"]
    if SETPOINT_COL in df.columns:
        mask_creep = df[SETPOINT_COL] >= 1.0
        if mask_creep.any():
            last_idx = df[mask_creep].index[-1]
            final_thickness = abs(df.loc[last_idx, "Disp_corrected (um)"])
        else:
            final_thickness = np.nan
    else:
        final_thickness = np.nan
    return {
        "condition": condition_label,
        "sample_index": sample_index,
        "sample_label": sample_label,
        "initial_thickness_um": initial_thickness,
        "thickness_at_maxload_um": thickness_at_maxload,
        "final_thickness_um": final_thickness,
        "stress_bar_maxload": stress_at_max,
    }

def analyze_thickness_summary(df_summary, out_csv="thickness_summary_summary.csv"):
    df_summary.to_csv(out_csv, index=False)
    grouped = df_summary.groupby("condition")
    stats = grouped.agg({
        "initial_thickness_um": ["mean", "std"],
        "thickness_at_maxload_um": ["mean", "std"],
        "final_thickness_um": ["mean", "std"],
        "stress_bar_maxload": ["mean", "std"],
    })
    print(stats)
    def plot_stat(y_col, title):
        means_y = grouped[y_col].mean()
        stds_y = grouped[y_col].std()
        means_x = grouped["stress_bar_maxload"].mean()
        conditions = means_x.index.tolist()
        x_vals = means_x.values
        y_vals = means_y.values
        y_errs = stds_y.values
        plt.figure(figsize=(7, 5))
        plt.errorbar(x_vals, y_vals, yerr=y_errs, fmt="o", capsize=4, markersize=8)
        for x_val, y_val, cond in zip(x_vals, y_vals, conditions):
            plt.text(x_val, y_val, cond, fontsize=8, ha="center", va="bottom")
        plt.xlabel("Stress at max load (bar)")
        plt.ylabel("{} (µm)".format(y_col))
        plt.title(title)
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.show()
    plot_stat("initial_thickness_um", "Initial thickness vs Stress")
    plot_stat("thickness_at_maxload_um", "Thickness at max load vs Stress")
    plot_stat("final_thickness_um", "Final thickness after creep vs Stress")

# more helper functions?
def build_interpretation_ready_sample(
    df_processed,
    corrected_disp_col="Disp_corrected (um)",
    corrected_disp_in_col="Disp_corrected (in)",
):
    df_export = df_processed.copy()
    if corrected_disp_col not in df_export.columns:
        raise KeyError("{} not found in processed sample DataFrame".format(corrected_disp_col))
    if LVDT_COL in df_export.columns:
        df_export["S:LVDT_raw (in)"] = df_export[LVDT_COL]
    df_export[corrected_disp_in_col] = df_export[corrected_disp_col] / 25400.0
    df_export[LVDT_COL] = df_export[corrected_disp_in_col]
    df_export["S:LVDT (um)"] = df_export[corrected_disp_col]
    return df_export

def load_processed_sample_csvs(csv_paths):
    data_list = []
    for csv_path in csv_paths:
        df = pd.read_csv(csv_path)
        df.attrs["name"] = Path(csv_path).stem
        df.attrs["source_path"] = str(csv_path)
        data_list.append(df)
    return data_list

def namestr(obj, namespace):
    matches = [name for name in namespace if namespace[name] is obj]
    if matches:
        return matches[0]
    return obj.attrs.get("name", "processed_sample")

def process_zero_and_samples_multi(
    zero_file,
    sample_file_groups,
    load_cutoff=1.0,
    area_mm2=19.63,
    group_labels=None,
    return_processed=False,
    save_processed_dir=None,
    interpretation_ready=True,
):
    df_zero_raw = load_curve_data(zero_file)
    if group_labels is None:
        group_labels = ["group{}".format(i + 1) for i in range(len(sample_file_groups))]
    fig_overlay, ax_overlay = plt.subplots(figsize=(9, 6))
    summary_rows = []
    processed_samples = {}
    saved_paths = []
    output_dir = None if save_processed_dir is None else Path(save_processed_dir)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    for samples, prefix in zip(sample_file_groups, group_labels):
        for i, sample_path in enumerate(samples):
            sample_idx = i + 1
            sample_label = "{}_{}".format(prefix, sample_idx)
            df_sample_raw = load_curve_data(sample_path)
            idx_sample_max = find_max_load_index_under_setpoint(df_sample_raw)
            if idx_sample_max is None:
                raise ValueError(
                    "Sample {} has no rows with {} < 1.0".format(sample_path, SETPOINT_COL)
                )
            target_load = df_sample_raw.loc[idx_sample_max, LOAD_COL]
            df_sample = process_curve_raw(sample_path, zero_curve=False, load_cutoff=load_cutoff)
            idx_zero_target = find_index_closest_load_under_setpoint(
                df_zero_raw,
                target_load,
                load_col=LOAD_COL,
                setpoint_col=SETPOINT_COL,
                setpoint_threshold=1.0,
            )
            df_zero_for_sample = shift_lvdt_to_zero_at_index(df_zero_raw, idx_zero_target)
            df_zero_for_sample = apply_load_cutoff(df_zero_for_sample, load_cutoff=load_cutoff)
            df_corr = subtract_zero_from_sample(
                df_zero_for_sample,
                df_sample,
                keep_full_sample_load_range=True,
            )
            df_ss, thickness_um = compute_thickness_stress_strain(
                df_corr,
                load_col=LOAD_COL,
                disp_corrected_col="Disp_corrected (um)",
                area_mm2=area_mm2,
                load_cutoff=load_cutoff,
            )
            df_zero_raw_plot = df_zero_raw[df_zero_raw[LOAD_COL] >= load_cutoff]
            df_sample_raw_plot = df_sample_raw[df_sample_raw[LOAD_COL] >= load_cutoff]
            zero_raw_disp_um = df_zero_raw_plot[LVDT_COL] * 25400.0
            sample_raw_disp_um = df_sample_raw_plot[LVDT_COL] * 25400.0
            ax_overlay.plot(
                zero_raw_disp_um,
                df_zero_raw_plot[LOAD_COL],
                linestyle=":",
                linewidth=1.3,
                alpha=0.8,
                label="{} | zero raw".format(sample_label),
            )
            ax_overlay.plot(
                df_zero_for_sample["S:LVDT_shifted (um)"],
                df_zero_for_sample[LOAD_COL],
                linestyle="--",
                linewidth=1.6,
                alpha=0.9,
                label="{} | zero shifted".format(sample_label),
            )
            ax_overlay.plot(
                sample_raw_disp_um,
                df_sample_raw_plot[LOAD_COL],
                linestyle=":",
                linewidth=1.3,
                alpha=0.8,
                label="{} | sample raw".format(sample_label),
            )
            ax_overlay.plot(
                df_ss["Disp_shifted (um)"],
                df_ss[LOAD_COL],
                linestyle="-",
                linewidth=2.0,
                label="{} | sample processed ({:.2f} um)".format(sample_label, thickness_um),
            )
            summary_rows.append(extract_sample_thickness_info(prefix, sample_idx, df_ss, thickness_um))
            df_export = build_interpretation_ready_sample(df_ss) if interpretation_ready else df_ss.copy()
            df_export["sample_label"] = sample_label
            df_export["condition"] = prefix
            df_export["sample_index"] = sample_idx
            df_export.attrs["name"] = sample_label
            processed_samples[sample_label] = df_export
            if output_dir is not None:
                output_path = output_dir / "{}_processed.csv".format(sample_label)
                df_export.to_csv(output_path, index=False)
                saved_paths.append(str(output_path))
    ax_overlay.set_xlabel("Displacement [um]")
    ax_overlay.set_ylabel("Load [N]")
    ax_overlay.set_title("Zero/Sample Load-Displacement (Raw vs Processed)")
    ax_overlay.grid(True, alpha=0.3)
    ax_overlay.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2, frameon=False, fontsize=8)
    fig_overlay.tight_layout()
    fig_overlay.subplots_adjust(bottom=0.28)
    plt.show()
    df_summary = pd.DataFrame(summary_rows)
    if return_processed or output_dir is not None:
        return {
            "summary": df_summary,
            "processed_samples": processed_samples,
            "saved_paths": saved_paths,
        }
    return df_summary

# interpret it I guess
def interpretData(
    data_list,
    thickness_info=True,
    thickness_list=None,
    creep_info=True,
    cutoff_load_thickness=1,
    cutoff_load_displacement=2,
    area_mm2=19.63,
):
    thickness = []
    if thickness_info:
        thickness = thickness_list
    else:
        for i in range(len(data_list)):
            thickness.append(-data_list[i]["S:LVDT (um)"][data_list[i]["Ch:Load (N)"] > cutoff_load_thickness].iloc[0])

    mechanicalProperties = []
    all_stress_data = []
    
    for i in range(len(data_list)):
        data = data_list[i][data_list[i]["Ch:Load (N)"] > cutoff_load_displacement].copy()
        data = data.reset_index(drop=True)
        all_stress_data.append(data["Stress_bar"].values)
    min_length = min([len(stress) for stress in all_stress_data])
    truncated_stress_data = [stress[:min_length] for stress in all_stress_data]
    avg_standard_deviation = np.mean([np.std(stress) for stress in truncated_stress_data])
    print(f"Average Standard Deviation: {avg_standard_deviation}")
    for i in range(len(data_list)):
        plt.figure(figsize=(8, 5.5))
        data_name = namestr(data_list[i], globals())
        trial = data_name.split("_")[-1]
        data = data_list[i][data_list[i]["Ch:Load (N)"] > cutoff_load_displacement].copy()
        data = data.reset_index(drop=True)
        has_creep_segment = creep_info and (data["Set Point ()"] > 1).any()
        if has_creep_segment:
            fracture_index = data[data["Set Point ()"] > 1].index[0]
        else:
            fracture_index = data["Stress_bar"].idxmax() + 1
        data_original = data.copy()
        data = data.iloc[:fracture_index].copy()
        gam = LinearGAM(s(0))
        gam.fit(data[["Strain_shifted"]], data["Stress_bar"])
        predictions = gam.predict(data[["Strain_shifted"]])
        stress_ceiling = float(data_original["Stress_bar"].max())
        predictions_for_plot = np.minimum(predictions, stress_ceiling)
        creep_level = None
        if has_creep_segment:
            creep_stress_segment = data_original[data_original["Set Point ()"] > 1]["Stress_bar"]
            creep_level = float(creep_stress_segment.mean())
            predictions_for_plot = np.minimum(predictions_for_plot, creep_level)
        plt.plot(data["Strain_shifted"], predictions_for_plot, color="black", label="Spline Model")
        creep_strain = None
        if has_creep_segment:
            creep_segment = data_original[data_original["Set Point ()"] > 1]["Strain_shifted"]
            creep_start = creep_segment.min()
            creep_end = creep_segment.max()
            plt.hlines(creep_level, creep_start, creep_end, color="red", label="Creep Region", linewidth=3)
            creep_strain = creep_end - creep_start
        if has_creep_segment:
            creep_end_index = data_original[data_original["Set Point ()"] > 1].index[-1] + 1
        else:
            creep_end_index = fracture_index
        plt.scatter(
            data_original.iloc[:creep_end_index]["Strain_shifted"],
            data_original.iloc[:creep_end_index]["Stress_bar"],
            color="lightgrey",
            label="Raw Data",
        )
        data["1st derivative"] = np.gradient(predictions, data["Strain_shifted"])
        data["2nd derivative"] = np.gradient(data["1st derivative"], data["Strain_shifted"])
        subset = data[data["Strain_shifted"] <= 0.5]
        breakpoint1 = subset["Strain_shifted"][subset["2nd derivative"].idxmin()]
        elasticRegion = data[data["Strain_shifted"] <= breakpoint1]
        modelElastic = LinearRegression()
        modelElastic.fit(elasticRegion["Strain_shifted"].values.reshape(-1, 1), elasticRegion["Stress_bar"].values)
        elasticModulus = modelElastic.coef_[0]
        yieldStrength = modelElastic.predict(np.array([[breakpoint1]]))
        predElastic = modelElastic.predict(elasticRegion[["Strain_shifted"]])
        predElastic = np.minimum(predElastic, stress_ceiling)
        regions = data[data["Strain_shifted"] >= breakpoint1]
        try:
            pw_fit = piecewise_regression.Fit(list(regions["Strain_shifted"]), list(regions["Stress_bar"]), n_breakpoints=4)
        except Exception as exc:
            print(f"Piecewise regression fitting failed: {exc}")
            continue
        pw_results = pw_fit.get_results()
        eval = None
        if pw_results["estimates"] is not None:
            breakpoint2 = pw_results["estimates"]["breakpoint1"]["estimate"]
            breakpoint3 = pw_results["estimates"]["breakpoint4"]["estimate"]
            plateauRegion = regions[regions["Strain_shifted"] <= breakpoint2]
            densificationRegion = regions[regions["Strain_shifted"] >= breakpoint3]
            modelPlateau = LinearRegression()
            modelPlateau.fit(plateauRegion["Strain_shifted"].values.reshape(-1, 1), plateauRegion["Stress_bar"].values)
            slopePlateau = modelPlateau.coef_[0]
            interceptPlateau = modelPlateau.intercept_
            modelDensification = LinearRegression()
            modelDensification.fit(densificationRegion["Strain_shifted"].values.reshape(-1, 1), densificationRegion["Stress_bar"].values)
            slopeDensification = modelDensification.coef_[0]
            interceptDensification = modelDensification.intercept_
            changepoint = (interceptDensification - interceptPlateau) / (slopePlateau - slopeDensification)
            xPlateau = data[(breakpoint1 <= data["Strain_shifted"]) & (data["Strain_shifted"] <= changepoint)]
            xDensification = data[changepoint <= data["Strain_shifted"]]
            if len(xDensification) > 0 and len(xPlateau) > 0:
                predPlateau = modelPlateau.predict(xPlateau[["Strain_shifted"]])
                predDensification = modelDensification.predict(xDensification[["Strain_shifted"]])
                predPlateau = np.minimum(predPlateau, stress_ceiling)
                predDensification = np.minimum(predDensification, stress_ceiling)
                if has_creep_segment and creep_level is not None:
                    predDensification = np.minimum(predDensification, creep_level)
                plateauModel = LinearGAM(s(0))
                plateauModel.fit(xPlateau[["Strain_shifted"]], xPlateau["Stress_bar"])
                plateauSpline = plateauModel.predict(xPlateau[["Strain_shifted"]])
                correlation_coefficient = np.corrcoef(plateauSpline, predPlateau)[0, 1]
                rangeStart = yieldStrength - 3
                rangeEnd = yieldStrength + 3
                if rangeStart <= modelPlateau.predict(breakpoint1.reshape(1, -1)) <= rangeEnd and slopePlateau <= elasticModulus * 1.25 and correlation_coefficient <= 0.98:
                    eval = True
                else:
                    eval = False
                result = {
                    "name": data_name,
                    "Trial": trial,
                    "Thickness": thickness[i],
                    "Elastic Modulus": elasticModulus,
                    "Yield Strength": yieldStrength[0],
                    "Changepoint": changepoint,
                    "Slope Plateau": slopePlateau,
                    "Slope Densification": slopeDensification,
                    "Creep Strain": creep_strain,
                    "Good Fit": eval,
                    "Average Standard Deviation": avg_standard_deviation,
                }
                mechanicalProperties.append(result)
                plt.plot(elasticRegion["Strain_shifted"], predElastic, color="blue", label="Elastic Region", linewidth=3)
                plt.plot(xPlateau["Strain_shifted"], predPlateau, color="orange", label="Plateau Region", linewidth=3)
                xDensification_plot = xDensification
                predDensification_plot = predDensification
                if has_creep_segment and "Set Point ()" in xDensification.columns:
                    non_creep_mask = xDensification["Set Point ()"] <= 1
                    xDensification_plot = xDensification[non_creep_mask]
                    predDensification_plot = predDensification[non_creep_mask.to_numpy()]
                if len(xDensification_plot) > 0:
                    plt.plot(xDensification_plot["Strain_shifted"], predDensification_plot, color="green", label="Densification Region", linewidth=3)
                print(result)
        plt.xlabel("Strain", fontsize=20)
        plt.ylabel("Stress (bar)", fontsize=20)
        plt.xticks(fontsize=16)
        plt.yticks(fontsize=16)
        plt.show()
        print("Good Fit:", eval)
    return mechanicalProperties

def extract(materialProperties):
    for i in range(len(materialProperties)):
        name.append(materialProperties[i]["name"])
        thickness.append(materialProperties[i]["Thickness"])
        conc.append(materialProperties[0])
        trial.append(materialProperties[i]["Trial"])
        elasticModulus.append(materialProperties[i]["Elastic Modulus"])
        yieldStrength.append(materialProperties[i]["Yield Strength"])
        creepStrain.append(materialProperties[i]["Creep Strain"])
        slopePlateau.append(materialProperties[i]["Slope Plateau"])
        slopeDensification.append(materialProperties[i]["Slope Densification"])
        changepoint.append(materialProperties[i]["Changepoint"])
        fit.append(materialProperties[i]["Good Fit"])
        avg_standard_deviation.append(materialProperties[i]["Average Standard Deviation"])

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
slopePlateau = []
slopeDensification = []
changepoint = []
fit = []
avg_standard_deviation = []
conc = []

def propertyDataFile(filename_old, filename_new):
    propertyData = {
        "Name": name,
        "Trial": trial,
        "Thickness": thickness,
        "Elastic Modulus": elasticModulus,
        "Yield Strength": yieldStrength,
        "Creep Strain": creepStrain,
        "Plateau Slope": slopePlateau,
        "Densification Slope": slopeDensification,
        "Changepoint": changepoint,
        "Fit": fit,
        "Average Standard Deviation": avg_standard_deviation,
    }
    propertyData = pd.DataFrame(propertyData)
    df_old = pd.read_csv(filename_old)
    propertyData = pd.concat([df_old, propertyData], ignore_index=True)
    propertyData.to_csv(filename_new, index=False)

# pipeline
def _normalize_curve_path(curve_path):
    return str(Path(curve_path))

def _build_single_sample_inputs(sample_curve, condition_label):
    return [[sample_curve]], [condition_label]

def _bundle_to_interpret_inputs(processed_bundle):
    processed_summary = processed_bundle["summary"]
    processed_data_list = list(processed_bundle["processed_samples"].values())
    processed_thickness_list = processed_summary["initial_thickness_um"].tolist()
    return processed_summary, processed_data_list, processed_thickness_list

def run_single_curve_interpretation_pipeline(
    zero_curve,
    sample_curve,
    condition_label="processed",
    load_cutoff=1.0,
    area_mm2=19.63,
    save_processed_dir=None,
    cutoff_load_thickness=1,
    cutoff_load_displacement=2,
    creep_info=True,
    return_details=False,
    interpret_fn=interpretData,
):
    zero_curve = _normalize_curve_path(zero_curve)
    sample_curve = _normalize_curve_path(sample_curve)
    sample_file_groups, group_labels = _build_single_sample_inputs(sample_curve, condition_label)
    processed_bundle = process_zero_and_samples_multi(
        zero_file=zero_curve,
        sample_file_groups=sample_file_groups,
        load_cutoff=load_cutoff,
        area_mm2=area_mm2,
        group_labels=group_labels,
        return_processed=True,
        save_processed_dir=save_processed_dir,
    )
    processed_summary, processed_data_list, processed_thickness_list = _bundle_to_interpret_inputs(processed_bundle)
    mechanical_properties = interpret_fn(
        processed_data_list,
        thickness_info=True,
        thickness_list=processed_thickness_list,
        creep_info=creep_info,
        cutoff_load_thickness=cutoff_load_thickness,
        cutoff_load_displacement=cutoff_load_displacement,
    )
    if return_details:
        return {
            "mechanical_properties": mechanical_properties,
            "processed_summary": processed_summary,
            "processed_data_list": processed_data_list,
            "processed_thickness_list": processed_thickness_list,
            "processed_bundle": processed_bundle,
        }
    return mechanical_properties

def compare_interpretation_outputs(reference_output, candidate_output, numeric_tol=1e-9):
    reference_df = pd.DataFrame(reference_output).copy()
    candidate_df = pd.DataFrame(candidate_output).copy()
    if reference_df.empty and candidate_df.empty:
        return pd.DataFrame([{"column": "all", "match": True, "detail": "both outputs empty"}])
    if list(reference_df.columns) != list(candidate_df.columns):
        return pd.DataFrame([{"column": "columns", "match": False, "detail": "column mismatch"}])
    comparison_rows = []
    for column in reference_df.columns:
        ref_series = reference_df[column]
        cand_series = candidate_df[column]
        if pd.api.types.is_numeric_dtype(ref_series) and pd.api.types.is_numeric_dtype(cand_series):
            ref_values = ref_series.to_numpy(dtype=float)
            cand_values = cand_series.to_numpy(dtype=float)
            match = np.allclose(ref_values, cand_values, equal_nan=True, atol=numeric_tol, rtol=0.0)
            max_abs_diff = float(np.nanmax(np.abs(ref_values - cand_values))) if len(ref_values) else 0.0
            detail = "max_abs_diff={:.12g}".format(max_abs_diff)
        else:
            match = ref_series.equals(cand_series)
            detail = "exact_match={}".format(match)
        comparison_rows.append({"column": column, "match": bool(match), "detail": detail})
    return pd.DataFrame(comparison_rows)

# wrapper
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
def _pair_chronological_zero_sample(specimen_rows, strict=True):
    rows_sorted = sorted(specimen_rows, key=lambda row: (row["timestamp"], row["specimen_id"]))
    if len(rows_sorted) == 0:
        return []
    if strict and len(rows_sorted) % 2 != 0:
        raise ValueError("Expected an even number of CSV files, got {}.".format(len(rows_sorted)))
    n_pairs = len(rows_sorted) // 2
    zero_rows = rows_sorted[:n_pairs]
    sample_rows = rows_sorted[n_pairs:n_pairs * 2]
    pairs = []
    for i, (zero_row, sample_row) in enumerate(zip(zero_rows, sample_rows), start=1):
        pairs.append({
            "replicate": i,
            "zero_file": zero_row["path"],
            "sample_file": sample_row["path"],
            "zero_specimen": zero_row["specimen_id"],
            "sample_specimen": sample_row["specimen_id"],
            "zero_time": zero_row["timestamp"],
            "sample_time": sample_row["timestamp"],
        })
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
        pairs = _pair_chronological_zero_sample(specimen_rows, strict=strict)
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

# master property extraction
def run_master_property_extraction(
    folder_name="Reproduced-Data",
    data_root="Data",
    output_csv="Data/Processed-Samples/master_property_data_reproduced.csv",
    strict=True,
    suppress_plots=False,
):
    print("Beginning Processing")
    pairs_by_condition = load_zero_sample_pairs_by_condition(
        folder_name=folder_name,
        data_root=data_root,
        strict=strict,
        load_dataframes=False,
)
    all_rows = []
    original_show = plt.show
    if suppress_plots:
        plt.show = lambda *args, **kwargs: None
    try:
        for condition, payload in pairs_by_condition.items():
            for pair in payload["pairs"]:
                props = run_single_curve_interpretation_pipeline(
                    zero_curve=pair["zero_file"],
                    sample_curve=pair["sample_file"],
                    condition_label=condition,
                    load_cutoff=1.0,
                    area_mm2=19.63,
                    save_processed_dir="Data/Processed-Samples/{}/{}".format(folder_name, condition),
                    cutoff_load_thickness=1,
                    cutoff_load_displacement=2,
                    creep_info=True,
                    return_details=False,
)
                if len(props) == 0:
                    continue
                for row in props:
                    row_out = dict(row)
                    row_out["condition"] = condition
                    row_out["replicate"] = pair["replicate"]
                    row_out["zero_file"] = pair["zero_file"]
                    row_out["sample_file"] = pair["sample_file"]
                    row_out["zero_specimen"] = pair["zero_specimen"]
                    row_out["sample_specimen"] = pair["sample_specimen"]
                    all_rows.append(row_out)
    finally:
        if suppress_plots:
            plt.show = original_show
    master_df = pd.DataFrame(all_rows)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    master_df.to_csv(output_path, index=False)
    print("Processing Done!")
    return master_df, str(output_path)

# master_property_df, master_property_csv = run_master_property_extraction(
#     folder_name="Reproduced-Data",
#     data_root="Data",
#     output_csv="Data/Processed-Samples/master_property_data_reproduced_v3.csv",
#     strict=True,
#     suppress_plots=False,
# )
# master_property_csv, master_property_df.shape, master_property_df.head()
