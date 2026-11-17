# Polysulfone reproducibility run

Use the existing Python runner and frozen Pareto validation plan, without active
learning. Run the commands below in Git Bash from the repository root. They use
campaign `psf-reproducibility-2026-11-16` and do not change the legacy
active-learning material settings.

From the repository root, preview without contacting devices:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py --batch psf-water
```

Before execution, stop the legacy campaign and deploy the robot-side support
listed in [the protocol runbook](PARETO_VALIDATION.md#deploy-the-robot-side-support).
Load materials matching `protocols/pareto_validation_setup.local.json`: 17 wt%
polysulfone stock, pure PolarClean casting solvent, no additive, and a water
bath. These are existing operator declarations, not a check of installed stocks.
The runner uses camera 2 and the Newton export directory documented in the runbook.

Start physical fabrication explicitly:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --execute --batch psf-water --campaign psf-reproducibility-2026-11-16 \
  --setup protocols/pareto_validation_setup.local.json
```

This runs V1 three times, then V2 three times, V4 three times, and V5 three times:
12 independent fabrications, 24 membrane compression tests, and 24 zero tests.
Each sample uses coupon locations 2 and 4. Exact historical recipes are retained,
including mixing temperature, casting speed, exposure, and immersion time.

After the water batch finishes, prepare the separate **10 wt% PolarClean bath**
and launch the remaining polysulfone condition:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --execute --batch psf-bath-10wt --campaign psf-reproducibility-2026-11-16 \
  --setup protocols/pareto_validation_setup.local.json
```

This adds three V3 fabrications, six membrane tests, and six zero tests. The
runner never switches the physical bath automatically.

To resume, reuse the exact same command and campaign key. Completed samples are
skipped. For a separate new campaign, pass a new `--campaign` key to both batches.
Results and resumable state are under
`data/results/begins_psf-reproducibility-2026-11-16/<batch>/`; raw data are in
separate sample directories under `data/raw/`. Existing measurements are preserved.

After each processed sample, `reproduce.csv` beside `agg.csv` contains one row per
fabricated membrane. It uses the same post-discard preference as `llm.csv`, with
clean sample names and no `LLM_suggestion` column. Aggregate parameter, property,
and report columns are retained; unavailable values remain blank. Samples where
all fits fail remain present. `agg.csv` retains the original pre/post-discard rows.
Collect-only runs defer this export until mechanical processing.

To generate or refresh it from existing results without refitting or device access:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --export-only --batch psf-water --campaign psf-reproducibility-2026-11-16
```

Use `--batch psf-bath-10wt` for the other bath's results. A running Python process
must be restarted to pick up code changes; preserve its campaign checkpoint.

Ctrl+C stops the local runner but does not cancel an accepted robot job. See
the [resume and limits](PARETO_VALIDATION.md#resume-and-limits) instructions for
interrupted jobs. Mocked validation does not establish physical readiness or a
scientific pass/fail threshold for reproducibility.
