# Polysulfone reproducibility run

## Five membranes in the 10 wt% PolarClean bath (November 23)

The operator requested five independent V3 membranes, using the unchanged recipe:
14.5 wt% polysulfone in PolarClean, 45 C mixing, 10 C bath, casting speed 7,
nitrogen, 200 s exposure and 1500 s immersion. The bath is 10 wt% PolarClean
and 90 wt% water. Compression points are 1 and 3 for both blank and membrane
phases. This is five fabrications, ten zero tests and ten membrane tests.
The original frozen three-repeat plan is retained. Like `--extend-psf-water`,
`--extend-psf-bath` appends repeats 4 and 5 after the original three jobs.
Existing sample IDs and measurements are preserved; resume with the same flag.
The earlier `--sample-repeats 5` remains a compatible alias, and checkpoints
created with it can resume with `--extend-psf-bath`.

Preview without devices:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --batch psf-bath-10wt --extend-psf-bath --test-locations 1 3
```

After preparing the physical bath, checking the existing 17 wt% stock declaration,
and confirming OT2 is ready:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --execute --batch psf-bath-10wt --campaign psf-reproducibility-2026-11-16 \
  --setup protocols/pareto_validation_setup.local.json \
  --test-locations 1 3 --extend-psf-bath
```

Samples are V3 rep1 through rep5. Results, `reproduce.csv` and checkpoint are
separate from the water batch, under
`data/results/begins_psf-reproducibility-2026-11-16/psf-bath-10wt/`.
Do not use `--extend-psf-water` for this batch. The setup declaration does not
verify installed materials or establish physical readiness.

## Current compression locations (November 17 update)

The first nine completed water samples used points **2 and 4**. At the operator's
request and physical clarification that **1 and 3 are the bottom**, the campaign
checkpoint now binds future samples to **1 and 3**, for
both blank-coupon and membrane phases. Completed payloads and measurements retain
their original locations. The interrupted V5 repeat 1 request and metadata are
archived under the campaign's recovery records and `data/raw/`; its OT2 journal
entry is preserved. Do not interpret measurements from the two pairs as the same
spatial sampling.

The remaining launch examples below require **`--test-locations 1 3`** when
resuming this campaign. Stop/reset the interrupted physical job and restart the
OT2 protocol after deploying `lib/compression_plan.py`; an already running
protocol retains its previously imported helper. No calibration coordinates change.

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --execute --batch psf-water --campaign psf-reproducibility-2026-11-16 \
  --setup protocols/pareto_validation_setup.local.json --test-locations 1 3
```

Add `--extend-psf-water` if continuing the additional-repeat schedule described
below. The historical frozen plan and default CLI pair remain 2 and 4; the
explicit override records the operator-selected change for future jobs.

## November 16 water-bath continuation

The saved checkpoint has three completed membranes each for V1, V2, and V4.
The interrupted V5 repeat 1 is archived. The continuation creates a fresh
request ID, finishes V5 repeats 1–3, and then runs repeats 4 and 5 for V1, V2,
and V4. That leaves five membranes each for V1, V2, and V4 and three for V5.

Preview the 18-position schedule offline. During execution, the nine completed
jobs are skipped using the checkpoint.

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py --batch psf-water --campaign psf-reproducibility-2026-11-16 --extend-psf-water --test-locations 1 3
```

With the water bath and stock verified against the existing setup declaration,
use the following command to start or resume the continuation. Reuse the same
command after an interruption.

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py --execute --batch psf-water --campaign psf-reproducibility-2026-11-16 --extend-psf-water --setup protocols/pareto_validation_setup.local.json --test-locations 1 3
```

## Original run procedure

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
  --setup protocols/pareto_validation_setup.local.json --test-locations 1 3
```

This runs V1 three times, then V2 three times, V4 three times, and V5 three times:
12 independent fabrications, 24 membrane compression tests, and 24 zero tests.
Future samples use coupon locations 1 and 3. Exact historical recipes are retained,
including mixing temperature, casting speed, exposure, and immersion time.

After the water batch finishes, prepare the separate **10 wt% PolarClean bath**
and launch the remaining polysulfone condition:

```bash
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py \
  --execute --batch psf-bath-10wt --campaign psf-reproducibility-2026-11-16 \
  --setup protocols/pareto_validation_setup.local.json --test-locations 1 3
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
