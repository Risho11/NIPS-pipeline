# Auto-Membranes

Automated membrane fabrication and characterization system for NIPS (Non-solvent
Induced Phase Separation) membranes — polymer membranes made by casting a
polysulfone solution and immersing it in a bath to trigger phase separation.

An Opentrons robot fabricates each batch, a compression tester measures its
mechanical properties, and an LLM active-learning loop suggests the next set of
fabrication parameters to try. See [`docs/PIPELINE_OVERVIEW.md`](docs/PIPELINE_OVERVIEW.md)
for the stage-by-stage mechanics of the curve-processing pipeline (reconciled with
the current file layout as of 2026-08-13).

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
  results/         begins_<date>/{reps,agg,llm}.csv per campaign (CONTINUE_CAMPAIGN in run_loop.py)
  llm_results/     per-condition next-params JSON written by run_loop.py
  plots/           segmentation plots (real runs + pseudo-runs/ for test/dev, gitignored)
  archive/         retired data kept for history — compression-test-data-legacy/, results-legacy/,
                   old_csv/, Image Processing/ (pre-reorg; only EVALUATE/generate_quality_log.py
                   still reads these, as a fallback behind the live data/raw/ and data/results/)
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
uv sync --locked
uv run --locked --no-sync python src/pipeline/run_loop.py          # full active-learning loop — needs real hardware
uv run --locked --no-sync python tests/run_tests.py                # CI test suite, mocked LLM, fake-data fixtures
uv run --locked --no-sync python tests/test_csv.py                 # unit tests for save_to_csv edge cases
uv run --locked --no-sync python tests/test_guardrails.py          # degenerate-input robustness tests
uv run --locked --no-sync python tests/test_processing.py          # run the real pipeline on one real condition (Mac, no hardware)
uv run --locked --no-sync python tests/test_master.py              # run the full branch dispatcher on one condition (Mac, no hardware)
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

Set `POLYMER_TYPE` and `SOLVENT_TYPE` in `src/pipeline/run_loop.py` before a
campaign, or call `run_loop.set_material_types(polymer_type="polysulfone",
solvent_type="PolarClean")` before starting the loop. Use the actual materials;
the source settings are operator choices, not confirmation of installed materials. These manual identities are saved with each condition
and supplied to LLM-AL for both new and resumed recommendations. `SOLVENT_TYPE`
is the base casting solvent, separate from the cosolvent and NIPS bath solvent.
The model cannot change these settings. Older records without identities remain
unknown rather than inheriting the current campaign's materials.

### Dynamic active learning

Set `LLM_AL_SEARCH_MODE = "dynamic"` in `src/pipeline/run_loop.py` and create
`data/results/begins_YYYY-MM-DD/dynamic_prompt.jinja` in the selected campaign
folder before it requests a recommendation. Write the campaign's objective,
current hypotheses and search guidance as UTF-8 text. For example:

```jinja
Seek reproducible improvements in elastic modulus and pore fraction. Use the
measured observations and their units, and treat missing measurements as unknown.
Prefer an informative experiment that can distinguish the current explanations.
```

The template can reference `{{ ranges }}`. Python adds the current parameter
ranges and response format and sends the observations with the existing
OpenRouter request. Each new recommendation reads the file again. A missing,
empty or invalid template stops that recommendation. A saved recommendation
is reused on retry through the existing checkpoint.

Codex CLI can read saved campaign results and update the template while the
loop runs. Write the new content to a temporary file in the campaign directory,
then replace the template. When its content changes, commit only
`dynamic_prompt.jinja` to preserve revision history. The loop reads the saved
file independently of that commit.

The default remains `double_explore`. Review any existing SDK MAS decision
or submission checkpoint before transitioning an old `dynamic` campaign.
[Historical SDK workflow and records](docs/mas/README.md) remain available.
