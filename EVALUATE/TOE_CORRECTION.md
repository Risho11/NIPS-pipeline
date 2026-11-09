The default legacy fitting policy only shifts a curve when a toe mask is actually
committed. Detection alone is not a mask, and a failed retry does not authorize
a shift. Fits without a retained toe mask keep their original strain origin and
original pore fraction.

    masked fit: pore fraction = intersection strain - committed mask cutoff
    unmasked fit: pore fraction = intersection strain

The same offset controls the plotted strain origin and pore fraction, once only.
CSV fields `Toe Masked`, `Toe Mask Cutoff`, and `Toe Shift` record what happened.
`Toe Region` may still contain a detected toe on an unmasked fit; it is not
automatically subtracted. `Toe Subtracted` is true only when a nonzero shift
was applied to that fit.

The optional **masked** mode detects the toe using a preliminary spline, excludes
points below the detected toe end, then fits a fresh spline and the mechanical
regions using only the retained points. It keeps the original strain coordinates
during fitting and subtracts the toe exactly once from the resulting pore fraction.
The same procedure applies to replicate and average-curve fits. If fewer than ten
points remain, the fit is recorded as failed rather than silently fitting the toe.

The **legacy** mode is the default for new configurations and retains the previous fitting behavior: toe points are included
initially, with a toe-mask retry only for the existing slope-inversion trigger.
Its default is `--toe-policy masked-only`, saved separately under `conditional/`.
Use `--toe-policy all-detected` to reproduce the earlier subtract-every-detected-toe
policy under `corrected/`. The optional masked-before-fit mode defaults to the
earlier all-detected policy; `--toe-policy masked-only` also works with that mode.
Subtracting the toe does not rescale by thickness or by `1 - toe`, or clamp negative
pore estimates. Existing fit-quality checks still determine which replicates pass.
Aggregate means and
standard deviations are computed from the corrected replicate values, rather than
subtracting an average toe from an already aggregated value.

The fit log shows corrected segmentation and derivative plots by default. Select
**show unsubtracted curves** to switch both to the original strain origin. Default
strain axes are labeled **Strain** and keep a small margin around zero. Curves,
markers, and shaded data are clipped wherever strain or stress is negative, so
the margin contains no negative stress-strain data. Negative derivative values
remain visible. Original-coordinate fit plots are labeled **Strain (toe included)**.
This toggle changes the strain origin
of the same fit; it does not restore the legacy fitting method or change exports.
Dotted stress/strain reference guides still extend to the axes across the margin.
Legends are opaque and drawn above all curves.
The toe-subtracted view has no grey toe band, boundary marker, or toe legend entry.
The original-coordinate view retains the grey masked-toe band and **Toe (masked)**
legend entry, shows the original sample curve, and is labeled **Strain (toe included)**.

Select **show zero / pre/post subtraction plots** to reveal each replicate's
zero-reference and sample curves before alignment, after alignment, and after
zero-reference subtraction. These displacement/load diagnostics are separate from
toe masking. Comparison plots retain their original strain origin.

Rebuild all historical data and the fit log:

Preview changes first. Obtain the user's explicit approval before starting or
resuming a full batch rerun in this workflow.

```powershell
.venv-analysis/Scripts/python.exe EVALUATE/reprocess_toe.py --fit-mode legacy --toe-policy masked-only --workers 6
```

Activate the completed conditional-shift legacy cache, without refitting:

```powershell
.venv-analysis/Scripts/python.exe EVALUATE/reprocess_toe.py --fit-mode legacy --toe-policy masked-only --activate
```

Cached activation restores that cache's plot files too. To apply newer plotting
styles to an older cache, use the full rerun command above after approval; do not
use `--resume` when every previously completed plot needs regeneration.

Retention is **original and latest only**. Intermediate all-detected and
mask-before-fit caches and their generated plots have been removed. Alternate
modes can still be regenerated from the original raw measurements using their
flags, after approval for a full rerun; they are not available for instant cached
activation unless regenerated and retained.

Omit `--resume` to rerun everything. `--condition NAME` generates a single-condition
preview under `data/toe_reprocessing/previews/<mode>/<condition-hash>/preview/`
without changing the mode's full cache, completion journal, or published data.
Add `--unsubtracted` to build a separate cache with the original strain origin.
`--activate` requires a completed validated cache. A failed batch does not publish.
The batch uses a stable per-condition random seed for repeatable piecewise fits.
Raw files remain untouched. Before updating historical CSVs, the script copies
them once to `data/toe_reprocessing/originals/`. The latest batch results are kept
under the active mode's folder in `data/toe_reprocessing/`, with per-condition
logs, completion records, and a failure report. Replicate CSVs retain the
unsubtracted pore fraction and toe so the subtraction can be audited directly.

Switching modes can temporarily stage outgoing CSVs and HTML under `snapshots/`;
cleanup removes these intermediate snapshots. Original raw measurements,
pre-change CSV backups, original run plots, and the active result/plot version
remain. Activating a retained mode updates all
fit measurements, fit classifications, aggregate statistics, warm-start exports,
and the fit log, while retaining historical identity, timestamps, and parameters.
It also saves `settings.json`, which controls the fitting mode and strain-origin
option for newly started live processing sessions. Reload an already imported
processing module after switching modes. The initial defaults are legacy fitting
and toe subtraction. Diagnostic toe and unsubtracted pore values stay out of AL
proposal prompts.

Strain-at-stress CSV measurements retain their existing definition; their plot
annotations move with the translated curve. Refitting can change the spline used
to obtain these measurements. The new fitting mode can change modulus, yield,
pore fraction, pass/fail decisions, and aggregate results; it is not just a plot shift.

After publishing a validated batch, `--cleanup` enforces original-and-latest
retention. To preview or apply the same cleanup independently:

```powershell
.venv-analysis/Scripts/python.exe EVALUATE/cleanup_toe_artifacts.py --original-and-latest
.venv-analysis/Scripts/python.exe EVALUATE/cleanup_toe_artifacts.py --original-and-latest --apply
```

The cleanup verifies resolved target paths are inside their designated workspace
directories before deletion. It preserves both corrected and unsubtracted views
of the latest fits, active report assets, raw input measurements, and original
run/test plot folders. A deletion summary is saved in `cleanup_report.json`.
