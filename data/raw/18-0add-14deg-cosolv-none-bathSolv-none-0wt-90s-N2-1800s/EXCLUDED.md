# Excluded experiment

Excluded on 2026-11-02: disk space was exhausted during raw-file copying on
2026-10-31 at 19:11:49, before processing or a results row was written.
Do not process this run or add it to the campaign results.

The two photographs and two partial-dataset CSVs are preserved in
`data/archive/interrupted-runs/18-0add-14deg-cosolv-none-bathSolv-none-0wt-90s-N2-1800s/`.
Specimen 283 is truncated; specimens 284 through 289 and params.json were not saved.
The original Newton Reports files remain untouched.

This directory reserves the original run ID. A fresh experiment with the same
parameters will be saved with a `_run2` suffix by move_and_rename().

The October 30 campaign's last completed row is
`17p5-0add-13deg-cosolv-none-bathSolv-none-0wt-90s-N2-1800s`.
Its saved recommendation supplies the replacement parameters: Primospire/NMP,
18% polymer, 0% additive, mixing temperature 65 C, bath temperature 14 C,
pullcast speed 10, nitrogen enabled, 90 s coupon wait, and 1800 s NIPS bath wait;
no cosolvent or bath solvent. The second bath remains configured at 30 minutes.

CONTINUE_CAMPAIGN is set to 2026-10-30 so the next manual launch uses that saved
recommendation. No physical experiment was launched while preparing this setup.
After the replacement finishes, verify eight raw CSVs, two images, params.json,
and the new campaign results row before committing its data.
