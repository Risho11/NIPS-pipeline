# %% [markdown]
# # Curve Viewer
# Sandbox — all display logic lives here. curve_segmentation.py untouched.
# Run cells with Shift+Enter.

# %% Imports & setup
from io import BytesIO
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import display, Image
from pygam import LinearGAM, s
from sklearn.linear_model import LinearRegression
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))  # points to project root where curve_segmentation.py lives
import curve_segmentation as p

p.SAVE_PLOTS = False

DATAROOT   = str(Path(__file__).parent.parent)
DATAFOLDER = "compression-test-data"
CUTOFF_LOAD_DISP  = 2
CUTOFF_LOAD_THICK = 1

def show():
    """Render current figure inline, then close it cleanly."""
    buf = BytesIO()
    plt.gcf().savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    plt.close("all")
    display(Image(buf.read()))

# %% Pick condition — edit this, then run the cell below
CONDITION = "17-5deg-7s-NoN2-30s"  # None = all; or e.g. "17-13deg-10s-NoN2-30s"

# %% List conditions
conditions = sorted(
    d.name for d in (Path(DATAROOT) / DATAFOLDER).iterdir()
    if d.is_dir() and not d.name.startswith(".") and d.name not in ("fake-data", "old data")
)
print(f"{'All' if CONDITION is None else CONDITION} — {len(conditions)} available:")
for c in conditions:
    print   (f"  {c}")

# %% Run — segmentation + derivative plots per curve
pairs_by_condition = p.load_zero_sample_pairs_by_condition(
    folder_name=DATAFOLDER, data_root=DATAROOT, load_dataframes=False,
)
if CONDITION:
    pairs_by_condition = {k: v for k, v in pairs_by_condition.items() if k == CONDITION}

for condition_name, payload in pairs_by_condition.items():
    print(f"\n{'='*60}\n{condition_name} | {payload['num_pairs']} pairs\n{'='*60}")

    for pair in payload["pairs"]:
        label = f"{condition_name} | rep {pair['replicate']}"

        # ── process curve ──────────────────────────────────────────────────
        zero_raw   = p.process_curve_raw(pair["zero_file"])
        sample_raw = p.process_curve_raw(pair["sample_file"])
        zero_sh, sample_sh = p.shift_sample_and_zero_curve(zero_raw.copy(), sample_raw.copy())
        curve = p.subtract_zero_from_sample(zero_sh.copy(), sample_sh.copy())

        thickness = -curve["Disp_corrected (um)"][curve["Ch:Load (N)"] > CUTOFF_LOAD_THICK].iloc[0]
        curve["stress (bar)"] = curve["Ch:Load (N)"] / 19.635 * 10
        curve["strain"]       = curve["Disp_corrected (um)"] / thickness

        if not p.validData_eval(thickness):
            print(f"  {label} — no membrane (thickness={thickness:.1f} µm), skipping")
            continue

        data = curve[curve["Ch:Load (N)"] > CUTOFF_LOAD_DISP].copy()
        data["strain"] = data["strain"] - data["strain"].iloc[0]
        data = data.reset_index(drop=True)

        fracture_index = data["stress (bar)"].idxmax() + 1
        has_creep = "Set Point ()" in data.columns and (data["Set Point ()"] > 1).any()
        if has_creep:
            fracture_index = data[data["Set Point ()"] > 1].index[0] + 1
        data_original = data.copy()
        data = data.iloc[:fracture_index]

        creep_strain = creep_level = None
        if has_creep:
            creep_seg   = data_original[data_original["Set Point ()"] > 1]["stress (bar)"]
            creep_level = float(creep_seg.mean())
            creep_start = data_original[data_original["Set Point ()"] > 1]["strain"].min()
            creep_end   = data_original[data_original["Set Point ()"] > 1]["strain"].max()
            creep_strain = creep_end - creep_start

        creep_end_index = (data_original[data_original["Set Point ()"] > 1].index[-1] + 1
                           if has_creep else fracture_index)

        # ── SEGMENTATION PLOT ──────────────────────────────────────────────
        plt.figure(figsize=(8, 5.5))

        if has_creep:
            plt.hlines(creep_level, creep_start, creep_end,
                       color="red", label="Creep Region", linewidth=3, zorder=100)

        gam = LinearGAM(s(0)).fit(data[["strain"]], data["stress (bar)"])
        predictions = gam.predict(data[["strain"]])
        preds_plot = predictions.copy()
        if creep_level is not None:
            preds_plot[preds_plot > creep_level] = creep_level
        plt.plot(data["strain"], preds_plot, color="black", label="Spline Model")

        loading_region = (data_original[data_original["Set Point ()"] <= 1].copy()
                          if "Set Point ()" in data_original.columns else data_original.copy())

        def strain_at_stress(target):
            lr = loading_region[["strain"]].dropna().copy()
            if lr.empty: return np.nan
            gs = gam.predict(lr[["strain"]]).astype(float)
            if target < gs.min() or target > gs.max(): return np.nan
            return float(lr["strain"].iloc[int(np.argmin(np.abs(gs - target)))])

        strain_50  = strain_at_stress(50)
        strain_80  = strain_at_stress(80)
        strain_150 = strain_at_stress(150)
        strain_500 = strain_at_stress(500)

        plt.scatter(data_original.iloc[:creep_end_index]["strain"],
                    data_original.iloc[:creep_end_index]["stress (bar)"],
                    color="lightgrey", label="Raw Data")

        data["1st derivative"] = np.gradient(predictions, data["strain"])
        data["2nd derivative"] = np.gradient(data["1st derivative"], data["strain"])

        breakpoint1 = p.elastic_peak(data, predictions)
        elastic_region = data[data["strain"] <= breakpoint1]
        model_elastic = LinearRegression().fit(
            elastic_region["strain"].values.reshape(-1, 1),
            elastic_region["stress (bar)"].values,
        )
        elastic_modulus = model_elastic.coef_[0]
        yield_strength  = model_elastic.predict(np.array([[breakpoint1]]))
        pred_elastic    = model_elastic.predict(elastic_region[["strain"]])

        regions = data[data["strain"] >= breakpoint1]
        bp2, bp3 = p.find_breakpoints(data, regions)
        if bp2 is None:
            plt.title(label, fontsize=14)
            plt.xlabel("Strain", fontsize=20); plt.ylabel("Stress (bar)", fontsize=20)
            show()
            continue

        xPlateau, xDensification, predPlateau, predDensification, changepoint, \
            slopePlateau, slopeDensification, modelPlateau = \
            p.find_changepoint_fit(data, breakpoint1, bp2, bp3, creep_level)

        eval_result, _ = p.goodFit_eval(
            data, elastic_region, xPlateau, xDensification,
            pred_elastic, predPlateau, predDensification,
            model_elastic, modelPlateau,
            gam,
            breakpoint1,
            changepoint,
            float(yield_strength[0]),
            elastic_modulus,
            slopePlateau,
            slopeDensification,
            creep_level=creep_level,
        )

        plt.plot(elastic_region["strain"], pred_elastic, color="blue", label="Elastic", linewidth=3)
        if predPlateau is not None and len(xPlateau) > 0:
            plt.plot(xPlateau["strain"], predPlateau, color="orange", label="Plateau", linewidth=3)
        if predDensification is not None and len(xDensification) > 0:
            plt.plot(xDensification["strain"], predDensification, color="green", label="Densification", linewidth=3)

        _ax = plt.gca()
        _xlim, _ylim = _ax.get_xlim(), _ax.get_ylim()
        for sv, strv, col in [(50,  strain_50,  "mediumpurple"),
                               (80,  strain_80,  "darkcyan"),
                               (150, strain_150, "coral"),
                               (500, strain_500, "steelblue")]:
            if strv is not None and not np.isnan(strv):
                plt.plot([_xlim[0], strv], [sv, sv],      color=col, linestyle=":", linewidth=1, alpha=0.9)
                plt.plot([strv, strv],      [_ylim[0], sv], color=col, linestyle=":", linewidth=1, alpha=0.9,
                         label=f"{sv} bar | ε={strv:.3f}")
        _ax.set_xlim(_xlim); _ax.set_ylim(_ylim)

        plt.title(label, fontsize=14)
        plt.xlabel("Strain", fontsize=20); plt.ylabel("Stress (bar)", fontsize=20)
        plt.legend(loc="upper left", fontsize=11)
        plt.xticks(fontsize=16); plt.yticks(fontsize=16)
        print(f"  Good Fit: {eval_result}")
        show()

        # ── DERIVATIVE PLOT (V1-5 logic) ───────────────────────────────────
        data["1st derivative"] = np.gradient(predictions, data["strain"])
        clean = np.isfinite(data["strain"]) & np.isfinite(data["1st derivative"])
        gam_d1 = LinearGAM(s(0, n_splines=25, lam=0.5, penalties="derivative")).fit(
            data["strain"][clean].values.reshape(-1, 1),
            data["1st derivative"][clean].values,
        )
        data["1st derivative"] = gam_d1.predict(data["strain"].values.reshape(-1, 1))
        data["2nd derivative"] = np.gradient(data["1st derivative"], data["strain"])

        spike = data["2nd derivative"].diff().abs()
        data.loc[data["2nd derivative"].abs() > 25000, "2nd derivative"] = np.nan
        data.loc[spike > 150, "2nd derivative"] = np.nan
        data["2nd derivative"] = data["2nd derivative"].interpolate(method="linear")

        subset = data[data["strain"] <= 0.3].copy()
        old_min = subset["strain"][subset["2nd derivative"].idxmin()]
        if old_min <= 0.02:
            subset = data[(data["strain"] > 0.03) & (data["strain"] <= 0.3)].copy()

        idx_bottom    = subset["2nd derivative"].idxmin()
        strain_bottom = subset.loc[idx_bottom, "strain"]
        val_bottom    = subset.loc[idx_bottom, "2nd derivative"]
        idx_start     = subset.loc[:idx_bottom, "2nd derivative"].idxmax()
        right_side    = subset.loc[idx_bottom:]
        local_window  = right_side[right_side["strain"] <= strain_bottom + 0.05]
        val_end_peak  = (local_window["2nd derivative"].max() if not local_window.empty
                         else right_side["2nd derivative"].max())
        recovery_zone = right_side[right_side["2nd derivative"] >= val_bottom + (val_end_peak - val_bottom) * 0.90]
        idx_end       = recovery_zone.index[0] if not recovery_zone.empty else right_side.index[-1]
        net_drop      = subset.loc[idx_start, "2nd derivative"] - subset.loc[idx_end, "2nd derivative"]
        bp1_v1        = ((strain_bottom + subset.loc[idx_end, "strain"]) / 2
                         if net_drop > 1500 else strain_bottom)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
        fig.suptitle(f"{label} — derivatives", fontsize=12)
        ax1.set_title("1st Derivative (smoothed GAM)")
        ax1.plot(data["strain"], data["1st derivative"], color="green")
        ax1.axvline(x=bp1_v1, color="purple", linestyle=":", label=f"bp1={bp1_v1:.3f}")
        ax1.set_xlabel("Strain"); ax1.legend()
        ax2.set_title("2nd Derivative (V3 noise removal)")
        ax2.scatter(data["strain"], data["2nd derivative"], color="pink", s=1)
        ax2.axvline(x=old_min, color="red",    linestyle=":", label=f"old min={old_min:.3f}")
        ax2.axvline(x=bp1_v1,  color="green",  linestyle=":", label=f"bp1={bp1_v1:.3f}")
        ax2.set_xlabel("Strain"); ax2.legend()
        plt.tight_layout()
        show()

# %%
