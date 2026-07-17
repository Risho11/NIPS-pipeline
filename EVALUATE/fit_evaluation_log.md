# Fit Evaluation Log

A living sounding board for reconciling the heuristic `Good Fit Score` with what the segmentation plots actually show.  
Run `TESTS/test_processing.py` to re-process a condition, then update its section below.

**To update a condition:** find its `[CONDITION: name]` marker, delete everything down to `[END CONDITION: name]`, and paste in fresh data. The condition name must match the folder name exactly so nothing gets double-entered.

---

## Heuristic Quick Reference

Pass threshold: **70/100** (called at `processing_29.py:894` as `pass_threshold=70` — note the function's own default at line 374 is 60, which is a misleading mismatch).

| Component | Max pts | What it measures | Known bias |
|---|---|---|---|
| `elastic_r2` | 30 | NRMSE of linear fit on elastic region | Short elastic regions (few points) amplify noise sensitivity |
| `plateau_r2_start` | 15 | R² of linear fit on first 40% of plateau | Rewards linearity, not flatness — a steeply rising plateau can score full marks |
| `densification_r2` | 15 | R² of linear fit on densification region | Generally reliable for dense-phase detection |
| `yield_accuracy` | 25 | % gap between linear-model yield and GAM at bp1 | Structurally biased: soft membranes have concave-up elastic regions, so linear model and GAM always disagree here |
| `junction_continuity` | 15 | % gap between plateau model and yield strength at bp1 | Very sensitive near threshold — 4-5% gap difference changes pass/fail |
| `plateau_r2_full_penalty` | 0 / −10 / −20 | R² of linear fit on full plateau (penalty if < 0.7 / < 0.5) | Correct to flag non-linear plateaus, but conflates "curved plateau" (real physics) with "bad fit" |
| `elastic_modulus_penalty` | 0 / −5 | E must be 10–5000 bar | Range is wide; rarely fires in practice |
| `bp1_accuracy_penalty` | 0 / −15 / −30 | Whether plateau consumes >30% / >50% of remaining stress | Most impactful penalty. Proxies for breakpoint misplacement but fires equally on steep-but-correct plateaus |
| `catastrophic_slope_vs_modulus` | score × 0.5 | Plateau slope > elastic modulus | Reliably catches inverted segmentations |
| `catastrophic_slope_ordering` | score × 0.5 | Densification slope ≤ plateau slope | Reliably catches inverted segmentations |

**Score interpretation (informal):**
- 90–100: Clean segmentation, well-defined regions
- 75–89: Good fit, minor issues (usually yield_accuracy or a small junction gap)
- 70–74: Borderline — examine the plot; score noise at this level is ±5 pts
- 60–69: Likely bp1_accuracy_penalty firing; plot may look fine visually
- < 60: Genuine fitting problem, or pre-processing failure

---

## Known Systemic Issues

These were documented on 2026-06-19 by examining both run folders. They're structural, not one-off bugs.

**Issue 1 — Two distinct failure modes, same CSV encoding**  
`validData_eval` (thickness < 50 µm) and poor scoring both produce `Good Fit = False`. But `Score = None` (pre-processing failure) vs `Score = 0–69` (fit failure) are different problems requiring different fixes. The CSV does not make this distinction explicit; you have to check whether the score is null or numeric.

**Issue 2 — `bp1_accuracy_penalty` is the dominant swing factor**  
The penalty fires when the plateau's linear slope, projected over the full plateau strain range, would consume >30% (→ −15) or >50% (→ −30) of the remaining stress budget. This is a reasonable heuristic for catching cases where the elastic peak was placed too early, but it also fires legitimately when the material simply has a steep plateau. For the 5°C bath conditions explored here, steep non-flat plateaus appear to be a consistent material property, not a fitting artifact. This makes the penalty systematically over-penalize these conditions.

**Issue 3 — Threshold razor: 70 creates false binary near-boundary**  
Multiple condition/rep pairs score 66–69 and fail, while visually identical curves score 70–71 and pass. At this score level, a ±2 point swing in `junction_continuity` or `elastic_r2` determines the outcome. The threshold should be treated as a fuzzy zone (65–75), not a hard gate.

**Issue 4 — `yield_accuracy` is structurally penalized for soft membranes**  
The component compares the linear elastic model's yield stress against the GAM spline's stress at `breakpoint1`. Soft membranes with a gradual concave-up toe region produce a systematic mismatch between these two models at the transition. This is physics, not a fitting error. yield_accuracy rarely reaches 25/25 and the shortfall is structural.

**Issue 5 — `plateau_r2_full_penalty` treats curved plateaus as bad fits**  
Some membranes show a slightly curved plateau (strain-hardening behavior in the plateau zone). A linear model fit to this plateau region will have R² well below 0.5 even if the first 40% fits fine. The −20 penalty fires on physically real behavior, not misfit. Check the first-40% R² (`plateau_r2_start`) alongside the full-plateau R² to tell these apart.

**Issue 6 — Breakpoint placement variance creates score variance between replicates**  
The piecewise regression that places `bp2` (end of plateau) is sensitive to local curve shape. Small differences in where `bp2` falls change: the plateau strain range, the `rise_fraction` for bp1_accuracy_penalty, and the densification slope. This is the main reason three replicates of the same condition can score 52, 66, and 78.

**Issue 7 — Function default threshold (60) vs actual call threshold (70)**  
`goodFit_eval(..., pass_threshold=60)` at line 374 vs `pass_threshold=70` at line 894. Any score 60–69 would pass using the function's own defaults but fails in practice. This is a code maintenance hazard.

**Issue 8 — No plateau flatness check**  
The heuristic has no component that checks whether the plateau slope is small relative to the elastic modulus (i.e., whether it actually looks like a plateau). A curve with a plateau slope that is, say, 60% of the elastic modulus will sail through all R² checks with high scores if the geometry happens to be right. Conversely, `bp1_accuracy_penalty` sometimes catches this indirectly, but it's a geometry ratio, not a slope ratio.

---

## Run Log

---

<!-- CONDITION: 17-5deg-325s-N2-1800s -->
## 17-5deg-325s-N2-1800s

**Run:** 2026-06-18 · **Processed:** 2026-06-18 17:48 · **Plot folder:** `pipeline-plots/run-2026-06-18/17-5deg-325s-N2-1800s/`

### Scores

| Rep | Thickness (µm) | Score | Pass? | Failure mode |
|---|---|---|---|---|
| rep-1 | **−3.6** | None | False | Pre-processing failure — no membrane |
| rep-2 | **−3.7** | None | False | Pre-processing failure — no membrane |
| rep-3 | **−2.9** | None | False | Pre-processing failure — no membrane |

### Score Breakdown

Not applicable — `validData_eval` exited before `goodFit_eval` was called (negative thickness → no membrane detected).

### Visual Assessment

All three segmentation plots show the title "no membrane detected" and display a scatter cloud — no stress-strain curve structure at all. The Pre-Processing plot shows the zero and sample LVDT curves at very different positions (zero at −198 to −188 µm range, sample displaced by ~4 µm after correction), producing complete noise after subtraction.

### Reconciliation Notes

> **Root cause is pre-processing, not fitting.** The zero-subtraction produced negative thickness (~−3 to −4 µm), meaning the sample appears physically thinner than the zero reference at the same load — impossible for a real membrane. Likely explanation: the zero curve and sample curve were mismatched in the pairing step (wrong CSV files paired), or the membrane completely slipped/folded under compression. The CSV records these as `Good Fit = False / Score = None`. To distinguish this failure type from bad fits, check whether the score is `None` (pre-processing) vs numeric (fit failure).

<!-- END CONDITION: 17-5deg-325s-N2-1800s -->

---

<!-- CONDITION: 17-5deg-350s-N2-1800s -->
## 17-5deg-350s-N2-1800s

**Run:** 2026-06-18 · **Processed:** 2026-06-18 16:49 · **Plot folder:** `pipeline-plots/run-2026-06-18/17-5deg-350s-N2-1800s/`

### Scores

| Rep | Thickness (µm) | E (bar) | Yield (bar) | Slope Plateau | Slope Densif | Score | Pass? |
|---|---|---|---|---|---|---|---|
| rep-1 | 140.0 | 399.3 | 18.5 | 167.9 | 629.8 | 70 | **YES** |
| rep-2 | 138.7 | 473.0 | 17.3 | 169.4 | 512.4 | 66 | NO |
| rep-3 | 144.8 | 298.0 | 23.6 | 132.7 | 289.1 | 90 | **YES** |

### Score Breakdown

| Component | rep-1 | rep-2 | rep-3 |
|---|---|---|---|
| elastic_r2 (30) | 26 — NRMSE=0.878 | 25 — NRMSE=0.845 | 28 — NRMSE=0.949 |
| plateau_r2_start (15) | 15 — R²=0.974 | 15 — R²=0.974 | 14 — R²=0.948 |
| densification_r2 (15) | 14 — R²=0.941 | 15 — R²=0.971 | 15 — R²=0.992 |
| yield_accuracy (25) | 16 — err=7.4% | 16 — err=7.2% | 18 — err=5.5% |
| junction_continuity (15) | **14** — gap=0.7% | **10** — gap=5.3% | 15 — gap=0.2% |
| plateau_r2_full_penalty | 0 — R²=0.975 | 0 — R²=0.986 | 0 — R²=0.988 |
| elastic_modulus_penalty | 0 — E=399.3 ok | 0 — E=473.0 ok | 0 — E=298.0 ok |
| bp1_accuracy_penalty | −15 — spans 43% | −15 — spans 43% | 0 — spans 27% |
| **Final** | **70 PASS** | **66 FAIL** | **90 PASS** |

### Visual Assessment

**rep-1:** Short elastic (blue) ending at ~strain 0.02, ~18 bar. Orange plateau rises steeply from ~18 to ~75 bar over a very long strain range (0.02→0.35). Not a flat plateau — continuously hardening. Densification (green) kicks in clearly at ~0.35 with a sharp slope change. Segmentation looks reasonable, but the "plateau" label is a stretch physically.

**rep-2:** Visually near-identical to rep-1. Same shape, same steep rise in the plateau zone, same densification step. The 4-point score difference (70 vs 66) is essentially indistinguishable at the plot level.

**rep-3:** Continuously rising curve with no visible plateau shelf. Elastic ends at ~0.06, orange plateau from 0.06→0.33 rising ~22 to ~60 bar. Then densification from 0.33→0.65. Score of 90 because the bp1_accuracy_penalty doesn't fire (rise fraction = 27%) and all individual fits are clean. But physically this is the same non-plateau behavior as rep-1 and rep-2.

### Reconciliation Notes

> **Key inconsistency: rep-1 (PASS) and rep-2 (FAIL) look identical.** The sole differentiator is `junction_continuity`: 0.7% gap vs 5.3% gap at breakpoint1. This is a 4-point difference at a threshold of 70. The pass/fail decision here should not be trusted as a quality distinction — both reps have the same fundamental issue (steep plateau, bp1 penalty).
>
> **rep-3 scoring 90 is arguably over-generous.** The curve is continuously rising with no plateau, identical in character to rep-1/2, but escapes the bp1 penalty because the piecewise regression happened to place the plateau endpoint earlier. The high score reflects good numerical fits on each individual segment, not good overall segmentation quality.

<!-- END CONDITION: 17-5deg-350s-N2-1800s -->

---

<!-- CONDITION: 17-5deg-50s-NoN2-100s -->
## 17-5deg-50s-NoN2-100s

**Run:** 2026-06-18 · **Processed:** 2026-06-18 14:37 · **Plot folder:** `pipeline-plots/run-2026-06-18/17-5deg-50s-NoN2-100s/`

### Scores

| Rep | Thickness (µm) | E (bar) | Yield (bar) | Slope Plateau | Slope Densif | Score | Pass? |
|---|---|---|---|---|---|---|---|
| rep-1 | 137.2 | 158.0 | 21.4 | 88.0 | 704.5 | 66 | NO |
| rep-2 | 150.2 | 711.6 | 18.8 | 36.8 | 829.5 | 42 | NO |
| rep-3 | 156.5 | 290.0 | 23.7 | 32.1 | 987.8 | 67 | NO |

### Score Breakdown

| Component | rep-1 | rep-2 | rep-3 |
|---|---|---|---|
| elastic_r2 (30) | 22 — NRMSE=0.745 | 25 — NRMSE=0.842 | 28 — NRMSE=0.946 |
| plateau_r2_start (15) | 11 — R²=0.702 | 12 — R²=0.827 | 12 — R²=0.819 |
| densification_r2 (15) | 14 — R²=0.944 | 12 — R²=0.797 | 13 — R²=0.860 |
| yield_accuracy (25) | 17 — err=6.2% | **1** — err=19.6% | 20 — err=3.9% |
| junction_continuity (15) | **2** — gap=13.1% | 12 — gap=3.0% | 14 — gap=0.5% |
| plateau_r2_full_penalty | 0 — R²=0.890 | **−20** — R²=0.359 | **−20** — R²=0.284 |
| elastic_modulus_penalty | 0 — E=158.0 ok | 0 — E=711.6 ok | 0 — E=290.0 ok |
| bp1_accuracy_penalty | 0 — spans 28% | 0 — spans 14% | 0 — spans 11% |
| **Final** | **66 FAIL** | **42 FAIL** | **67 FAIL** |

### Visual Assessment

**rep-1:** Strain axis starts at ~−0.1, stress ~10 bar — the curve doesn't begin at (0,0). This is a contact/thickness artifact: the membrane was already under some compression when the load cutoff was passed. Elastic region (blue) consequently looks very short and the junction gap is large (13.1%) because the plateau model and the yield strength are offset by this artifact. Densification (green) is clearly visible at ~strain 0.47. The segmentation itself is not terrible, but the contact artifact corrupts several score components.

**rep-2:** Clear "S-shaped" compression curve with a very flat plateau (stress barely rises from ~20 to ~38 bar across a huge strain range 0.02→0.55). The plateau is nearly flat, but it's not straight — it curves slightly upward toward the end, so the full-plateau linear R² collapses to 0.359 (−20 penalty). The densification step at ~0.55 is sharp and clear. Elastic modulus of 711.6 bar is suspiciously high given such a soft plateau — likely the elastic region was very short/steep.

**rep-3:** Similar plateau shape to rep-2 (nearly flat, ~23 to ~38 bar over 0.07→0.52 strain) with a clear densification jump. Same issue: plateau is slightly curved so full R² = 0.284 (−20 penalty). The elastic fit is actually good (NRMSE=0.946) and junction is tight (0.5%), but the plateau penalty alone sinks the score to 67.

### Reconciliation Notes

> **rep-1's failure is partially a pre-processing artifact.** The negative strain offset at the start (strain begins at −0.1 instead of 0) inflates the junction gap to 13.1% and limits the elastic_r2 score. The thickness determination or zero-correction placed the contact point incorrectly. This is a data quality issue, not a segmentation issue.
>
> **rep-2 and rep-3 fail because of the plateau_r2_full_penalty, not bad segmentations.** The plateau and densification regions are clearly identifiable in both plots. The penalty fires because the plateau is slightly curved (physically real for these short-bath-time, no-N2 conditions), not because the linear model is placed wrong. The first-40% R² of 0.827 and 0.819 shows the early plateau fits fine. A curved plateau should arguably be flagged with a note, not treated as a score penalty this large.
>
> **E=711.6 bar for rep-2 is a red flag.** That's among the highest in the dataset. Combined with a nearly flat plateau (slope=36.8 bar/strain), this would normally trigger `catastrophic_slope_vs_modulus` — but it doesn't, because `slopePlateau (36.8) < elasticModulus (711.6)`. So the catastrophic guard doesn't catch this structural inconsistency. An elastic modulus ~4× higher than nearby replicates in the same condition with no corresponding change in the rest of the curve deserves manual inspection.

<!-- END CONDITION: 17-5deg-50s-NoN2-100s -->

---

<!-- CONDITION: 17-5deg-550s-N2-1800s -->
## 17-5deg-550s-N2-1800s

**Run:** 2026-06-18 · **Processed:** 2026-06-18 15:46 · **Plot folder:** `pipeline-plots/run-2026-06-18/17-5deg-550s-N2-1800s/`

### Scores

| Rep | Thickness (µm) | E (bar) | Yield (bar) | Slope Plateau | Slope Densif | Score | Pass? |
|---|---|---|---|---|---|---|---|
| rep-1 | 136.6 | 318.6 | 19.9 | 104.2 | 812.6 | 66 | NO |
| rep-2 | 141.7 | 181.6 | 28.6 | 79.7 | 743.5 | 94 | **YES** |
| rep-3 | 147.6 | 334.8 | 23.1 | 80.3 | 869.1 | 71 | **YES** |

### Score Breakdown

| Component | rep-1 | rep-2 | rep-3 |
|---|---|---|---|
| elastic_r2 (30) | 27 — NRMSE=0.907 | 29 — NRMSE=0.968 | 28 — NRMSE=0.929 |
| plateau_r2_start (15) | 14 — R²=0.957 | 14 — R²=0.958 | 14 — R²=0.963 |
| densification_r2 (15) | 14 — R²=0.955 | 14 — R²=0.913 | 14 — R²=0.928 |
| yield_accuracy (25) | **14** — err=8.8% | **22** — err=2.7% | **16** — err=7.2% |
| junction_continuity (15) | **12** — gap=3.2% | **15** — gap=0.4% | **14** — gap=0.9% |
| plateau_r2_full_penalty | 0 — R²=0.950 | 0 — R²=0.828 | 0 — R²=0.925 |
| elastic_modulus_penalty | 0 — E=318.6 ok | 0 — E=181.6 ok | 0 — E=334.8 ok |
| bp1_accuracy_penalty | **−15** — spans 33% | **0** — spans 25% | **−15** — spans 31% |
| **Final** | **66 FAIL** | **94 PASS** | **71 PASS** |

### Visual Assessment

**rep-1:** Elastic ends at ~0.04 strain, ~20 bar. Plateau (orange) runs from 0.04→0.47, rising from 20 to ~65 bar. Densification jump at 0.47 is clear and steep. The curve shape looks physically reasonable — good segmentation. The -15 bp1 penalty fires because the plateau stress rise (104.2 × ~0.43 strain ≈ 45 bar) is 33% of the remaining stress budget.

**rep-2:** Elastic ends at ~0.12 strain (notably longer than rep-1/3), ~30 bar. Plateau from 0.12→0.51, rising 30→58 bar. Densification from 0.51. The longer elastic region means the plateau starts at higher stress, which shifts the rise_fraction calculation below 30% — no bp1 penalty. Visually very similar to rep-1 in terms of curve character, but the breakpoint placement is different.

**rep-3:** Elastic ends at ~0.07 strain, ~23 bar. Plateau from 0.07→0.57, rising 23→63 bar. Similar to rep-1 in character. The bp1 penalty fires (31% rise fraction), same as rep-1, but other components score slightly higher.

### Reconciliation Notes

> **The 28-point gap between rep-1 (66) and rep-2 (94) is not justified by visual quality.** Looking at the plots side-by-side, the segmentation quality is similar — both have a well-defined elastic, a rising plateau, and a sharp densification. The difference is: rep-2's elastic region is longer (ends at strain 0.12 vs 0.04), which shifts the plateau start point and brings the rise_fraction below the 30% threshold. This is almost entirely driven by where `elastic_peak()` placed `breakpoint1`.
>
> **rep-1 (FAIL) vs rep-3 (PASS) is also marginal.** They score 66 vs 71 — both get the same -15 bp1 penalty, but rep-3 edges past 70 by 5 points from slightly better yield_accuracy and junction_continuity. Visually these curves are essentially the same condition.
>
> **Bottom line for this condition:** only rep-2's score (94) genuinely reflects a clean segmentation. rep-1 and rep-3 are borderline and the pass/fail split between them is fragile.

<!-- END CONDITION: 17-5deg-550s-N2-1800s -->

---

<!-- CONDITION: 17-5deg-400s-N2-1807s -->
## 17-5deg-400s-N2-1807s

**Run:** 2026-06-17 · **Processed:** 2026-06-17 16:23 · **Plot folder:** `pipeline-plots/run-2026-06-17/17-5deg-400s-N2-1807s/`

### Scores

| Rep | Thickness (µm) | E (bar) | Yield (bar) | Slope Plateau | Slope Densif | Score | Pass? |
|---|---|---|---|---|---|---|---|
| rep-1 | 143.8 | 652.5 | 17.8 | 146.8 | 295.0 | 60 | NO |
| rep-2 | 150.5 | 377.8 | 17.1 | 147.1 | 983.6 | 52 | NO |
| rep-3 | 144.8 | 341.4 | 29.4 | 68.6 | 932.9 | 78 | **YES** |

### Score Breakdown

| Component | rep-1 | rep-2 | rep-3 |
|---|---|---|---|
| elastic_r2 (30) | 26 — NRMSE=0.858 | 28 — NRMSE=0.918 | 28 — NRMSE=0.922 |
| plateau_r2_start (15) | 15 — R²=0.971 | 15 — R²=0.986 | 14 — R²=0.909 |
| densification_r2 (15) | 14 — R²=0.942 | 14 — R²=0.937 | 14 — R²=0.953 |
| yield_accuracy (25) | 9 — err=13.2% | 14 — err=8.5% | 11 — err=11.1% |
| junction_continuity (15) | 11 — gap=3.9% | 11 — gap=3.8% | 11 — gap=4.2% |
| plateau_r2_full_penalty | 0 — R²=0.992 | 0 — R²=0.910 | 0 — R²=0.938 |
| elastic_modulus_penalty | 0 — E=652.5 ok | 0 — E=377.8 ok | 0 — E=341.4 ok |
| bp1_accuracy_penalty | **−15** — spans 38% | **−30** — spans 57% | **0** — spans 27% |
| **Final** | **60 FAIL** | **52 FAIL** | **78 PASS** |

### Visual Assessment

**rep-1:** Elastic (blue) ends at ~0.03 strain, ~20 bar. Plateau (orange) goes from 0.03→0.35, continuously rising from 20 to ~70 bar. Densification (green) from 0.35 onward, also steeply rising. The transition between plateau and densification is not sharp — the curve just gets slightly steeper. Segmentation is reasonable but the boundary placement is arbitrary on a continuously hardening curve.

**rep-2:** This is the clearest misfit of the three. The orange plateau extends from ~0.03 to ~0.55 — nearly the entire measurement range. The actual data curves upward significantly through this span, so the linear plateau model diverges badly from the data in the upper half. The −30 bp1 penalty is appropriate here: the segmentation placed bp1 too early, making the "plateau" consume 57% of the remaining stress. Looking at the plot, the plateau line (orange) is clearly below the actual data for most of its range, then the densification region (green) is only a tiny sliver at the end. This is a genuine misfit.

**rep-3:** Elastic ends at ~0.09 strain, ~30 bar. Plateau from 0.09→0.56, rising 30→65 bar. Densification from 0.56 onward with a clear jump. The curve character is similar to rep-1, but the elastic endpoint was placed further out (0.09 vs 0.03), which shifts the rise_fraction below 30%. Score 78, passes.

### Reconciliation Notes

> **rep-2 (52) is correctly identified as a poor fit.** The plot shows the orange line clearly underestimating the actual data throughout the plateau zone. The −30 penalty is warranted.
>
> **rep-1 (60, FAIL) and rep-3 (78, PASS) look like the same material behavior.** Both have continuously hardening curves with no classical plateau. rep-3 passes because `elastic_peak()` found `breakpoint1` at higher strain (~0.09 vs ~0.03), compressing the apparent plateau width. This is a segmentation sensitivity issue, not a real quality difference.
>
> **E=652.5 bar for rep-1 is high** relative to rep-2 (377.8) and rep-3 (341.4), despite all being the same condition. The short elastic region (ends at strain 0.03) means E is estimated from very few data points over a small range. Treat this modulus as unreliable.
>
> **`junction_continuity` is identical across all three reps** (all 11/15, gap ~3.8–4.2%). This is the kind of within-condition consistency that suggests this component is measuring a real feature of the condition, not noise. But yield_accuracy varies significantly (9, 14, 11) with no obvious physical reason.

<!-- END CONDITION: 17-5deg-400s-N2-1807s -->

---

<!-- CONDITION: 17-5deg-600s-N2-1800s -->
## 17-5deg-600s-N2-1800s

**Run:** 2026-06-17 · **Processed:** unknown · **Plot folder:** `pipeline-plots/run-2026-06-17/17-5deg-600s-N2-1800s/`

### Scores

| Rep | Score | Pass? | Notes |
|---|---|---|---|
| rep-1 | — | — | Folder exists, no data in results_reps.csv |

### Visual Assessment

Pre-Processing plot exists (`rep-1/Pre-Processing_rep-1.png`) but no Segmentation plot was generated — processing may have terminated early or CSV data was not saved. No score data available.

### Reconciliation Notes

> **This condition has incomplete data.** The plot folder was created (Pre-Processing plot is present) but no segmentation or CSV output exists. Needs to be re-run with `test-processing.py`.

<!-- END CONDITION: 17-5deg-600s-N2-1800s -->

---

## Template for New Runs

Copy this block when adding a new condition. Replace the placeholder text and delete unused rows.

```
<!-- CONDITION: [condition-name] -->
## [condition-name]

**Run:** [date] · **Processed:** [datetime] · **Plot folder:** `pipeline-plots/run-[date]/[condition-name]/`

### Scores

| Rep | Thickness (µm) | E (bar) | Yield (bar) | Slope Plateau | Slope Densif | Score | Pass? |
|---|---|---|---|---|---|---|---|
| rep-1 | | | | | | | |
| rep-2 | | | | | | | |
| rep-3 | | | | | | | |

### Score Breakdown

| Component | rep-1 | rep-2 | rep-3 |
|---|---|---|---|
| elastic_r2 (30) | pts — note | pts — note | pts — note |
| plateau_r2_start (15) | | | |
| densification_r2 (15) | | | |
| yield_accuracy (25) | | | |
| junction_continuity (15) | | | |
| plateau_r2_full_penalty | | | |
| elastic_modulus_penalty | | | |
| bp1_accuracy_penalty | | | |
| catastrophic? | no / halved | | |
| **Final** | **score PASS/FAIL** | | |

### Visual Assessment

**rep-1:** [describe elastic length, plateau flatness, densification clarity, any artifacts]

**rep-2:** [...]

**rep-3:** [...]

### Reconciliation Notes

> [Write your assessment here: does the score match the plot? which components are misleading? any pre-processing artifacts? anything worth fixing in the heuristic?]

<!-- END CONDITION: [condition-name] -->
```

---

## Updating an Existing Condition

When you re-run `test-processing.py` on a condition that already has an entry:

1. Find the `<!-- CONDITION: [name] -->` marker for that condition
2. Delete everything from that line down to and including `<!-- END CONDITION: [name] -->`
3. Paste in a fresh block using the template above with updated scores and plots
4. Update the "Processed" date at the top of the block

This ensures old data is fully replaced, not appended.
