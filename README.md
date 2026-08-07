# Auto-Membranes

Automated membrane fabrication and characterization system for NIPS (Non-solvent
Induced Phase Separation) membranes — polymer membranes made by casting a
polysulfone solution and immersing it in a bath to trigger phase separation.

An Opentrons robot fabricates each batch, a compression tester measures its
mechanical properties, and an LLM active-learning loop suggests the next set of
fabrication parameters to try. See [`docs/PIPELINE_OVERVIEW.md`](docs/PIPELINE_OVERVIEW.md)
for the stage-by-stage mechanics of the curve-processing pipeline — note that doc
predates the current file layout/names below and hasn't been fully reconciled with
this reorg; treat the file map here as authoritative for "what's actually called what."

## Repo layout

```
src/pipeline/     main pipeline: run_loop.py (entry point), curve_segmentation.py,
                   master_processing.py, activeLearning_29.py, llm_context.py,
                   system_prompt.py, membrane_imaging.py, membrane_quality_llm.py,
                   polymer_additive_bounds.py, polymer_additive_mixing_calculator.py,
                   url_29.py, cameras.py
src/server/        HTTP server that runs on the Opentrons PC (was minipc/) — manually
                   copied out to the lab machine, not deployed automatically from here
tests/             CI-run tests + local (no-hardware) dev scripts — see below
data/
  raw/             one subfolder per condition: 6 specimen CSVs, 2 photos, params.json
  results/         results_reps.csv, results_agg.csv, results_agg_llm.csv (master tables)
  llm_results/     per-condition next-params JSON written by run_loop.py
  plots/           segmentation plots (real runs + pseudo-runs/ for test/dev, gitignored)
prompts/            quality_checker_prompt.txt (LLM-refined prompt cache, tracked in git)
notebooks/          exploratory/dev notebooks
docs/               PIPELINE_OVERVIEW.md
installation/       driver/labware installer files (was "Installation Files/")
EVALUATE/           generate_fit_log.py — builds fit_evaluation_log.html quality report
2026-06-11/         robot-arm protocol scripts (untouched, own thing)
logs/               run_loop.py session logs (gitignored)
```

## Running it

```
pip install -r requirements.txt
python src/pipeline/run_loop.py          # full active-learning loop — needs real hardware
python tests/run_tests.py                # CI test suite, mocked LLM, fake-data fixtures
python tests/test_csv.py                 # unit tests for save_to_csv edge cases
python tests/test_guardrails.py          # degenerate-input robustness tests
python tests/test_processing.py          # run the real pipeline on one real condition (Mac, no hardware)
python tests/test_master.py              # run the full branch dispatcher on one condition (Mac, no hardware)
```

`run_loop.py` has hardcoded Windows paths (`CSV_RAW_PATH`, `IMAGES_PATH`) and a
hardcoded robot IP (`SERVER_IP`) near the top — it's meant to run on the lab PC next
to the compression tester, not from an arbitrary machine. Same story for `src/server/`
(the Opentrons-PC HTTP server): it's manually copied to that machine, this repo's copy
is the source of truth but isn't auto-deployed.

## CI

`.github/workflows/ci.yml` gates on: syntax check (compiles every `.py` file),
`validate_structure.py` (checks every `<<< IMPORT >>>` / `<<< FOLDER NAME >>>`-marked
reference in the code actually resolves on disk — run this after any future file
move), `validate_params.py` / `validate_fake_data.py` (data integrity), and the real
test suite (`tests/run_tests.py`, `tests/test_csv.py`, `tests/test_guardrails.py`),
gated to only run when relevant files change.

Known pre-existing gap: `validate_params.py`'s required-keys schema still expects
`weight_percent`, but current `params.json` files use `polymer_wt`/`additive_wt` —
this predates the reorg and needs a real decision about which schema is current,
not a path fix.
