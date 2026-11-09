Warm-start datasets synchronized with the analysis notebooks
===========================================================

The two canonical exports use exactly the selected rows and full-precision numeric
data in the corresponding notebook's `campaign_detailed` dataframe:

| Notebook | Warm-start CSV | Current saved selection |
| --- | --- | ---: |
| `EVALUATE/campaign_trends.ipynb` | `polysulfone_polarclean.csv` | 119 samples |
| `EVALUATE/primospire_nmp_campaign_trends.ipynb` | `primospire_nmp.csv` | 74 samples |

Rerunning the main trend-plot cell in either notebook refreshes its warm-start
CSV and JSON, even when `SAVE_OUTPUTS = False`. It exports the actual selected
dataframe, including campaign/date/chemistry filters, CV and discard limits,
replicate-strain checks, stock ages, and manual exclusions. The exporter applies
no additional date caps, quality filters, deduplication, or bath corrections.
Only AL report/provenance fields are enriched; measurements are not rounded.
AL request formatting applies the separate two-decimal prompt-only rule.

Standalone regeneration reads the notebooks' **saved** settings and runs only
their configuration and loading/filtering cells, without plots, model fitting,
API calls, or changes to source result CSVs:

```console
python EVALUATE/export_warm_start.py
python EVALUATE/export_primospire_warm_start.py
```

The JSON sidecars record the notebook, selected campaigns, filters, exclusions,
and current counts. Counts above reflect the current saved settings and may
change after editing filters or adding data.

Historical bath correction (operator confirmed 2026-10-23): all recorded historical
NIPS baths contained **0 wt% solvent**. Warm-start exports and historical campaign
CSV rows now explicitly record `nips_bath_solvent=none` and
`nips_bath_solvent_wt_percent=0.0`, with a `bath_context_source` provenance column.
This is separate from the current **10 wt% PolarClean** bath used for future runs.
The fixed condition list in `historical_zero_bath_conditions.json` limits the
backfill to confirmed history; future/unlisted conditions do not default to zero,
and explicit nonzero records are preserved. The exporter preserves the notebook's
selected bath values without export-only changes. To restore this context after regenerating
historical result CSVs, run `python EVALUATE/backfill_historical_bath_context.py`.
This does not recompute fits, change measurements, or regenerate LLM suggestions.

The current Polysulfone selection includes the August 21/22, September 21/25,
and October 15 source campaigns and the notebook's manual sample exclusion.
The Primospire selection includes September 10, September 30, and October 30.
Unknown property measurements remain unknown when the notebook retains the row.

In `src/pipeline/run_loop.py`, set:

```python
POLYMER_TYPE = "Polysulfone"  # PSf
SOLVENT_TYPE = "PolarClean"
LLM_AL_SEARCH_MODE = "double"  # modulus and pore fraction
LLM_AL_WARM_START_CSV = _REPO_ROOT / "data/warm_start/polysulfone_polarclean.csv"
CONTINUE_CAMPAIGN = None
```

For a new campaign, also set `CONTINUE_CAMPAIGN = None`. Restart the pipeline
after changing settings. In active-learning mode, the first experiment is now a
fresh suggestion based on the warm-start history instead of `INITIAL_PARAMS`.
It uses the selected search mode, current stock bounds, additive lock, and manual
material settings. The suggestion and final parameters are saved to
`data/results/begins_<campaign>/initial_suggestion.json` before submission.
Restarting a new campaign in the same campaign folder reuses that file without
another LLM call. Current stock bounds, additive lock, material settings, and the
stock-only 25 C rule are reapplied. Rename the file to explicitly request a fresh
suggestion. An invalid saved file stops startup instead of silently regenerating.
With `CONTINUE_CAMPAIGN = None`, the folder is based on today's date; a different
date uses a different folder. Reusing a suggestion does not resume a physical
experiment that was interrupted.
Missing, empty, or invalid history stops startup rather than falling back to defaults.
With `LLM_AL_WARM_START_CSV = None`, new campaigns use `INITIAL_PARAMS`.
Explicit sweeps and campaigns with no enabled processing branches still use their
iteration lists. The history is read when generating recommendations;
already-saved recommendations are not regenerated. Historical rows are never
copied into campaign CSVs or checkpoints. A current row with the same condition
name supersedes its historical row. Set the warm-start path to `None` to disable.

Set `LLM_AL_SEARCH_MODE = "double_explore"` for equal-priority modulus and pore-fraction
optimization with modest exploration of promising, under-sampled conditions. This
mode includes diversity coverage and retains candidate validation requirements.
`double` retains its existing objective-first strategy; `explore` prioritizes coverage.
Restart the pipeline after changing the mode; saved recommendations are reused.

All modes receive `experimental_observations_v2`: each experiment contains its
conditions, property means/SDs, `image_analysis.quality_report`, and
`experiment_timing` (date/time and source). CSV input columns remain compatible:
`quality_report`, `sample_time`, and `time_source` accompany the property columns.
Missing fields become null. Historical exports retain these columns; no regeneration
is needed for existing files that already contain them. Live runs record the earliest
timestamp in their `Specimen_*.csv` filenames. Processing time stays separate;
historical processing-time fallbacks remain labeled by their source. Timestamps
without timezone information are not assigned a timezone. Time is context, not a
third optimization objective. Image reports are included in full in the same record
as the properties, so long campaigns can produce larger prompts.

Limitations:

- Chemistry follows the notebook's inference, rather than verified stock metadata.
  Use this file for compatible chemistry and retain current stock bounds.
- Pore fraction is the compression-curve plateau/densification intersection
  estimate, not independent porosimetry. Modulus is in bar, pore fraction is
  dimensionless, and thickness is in micrometers.
- SD is intra-sample; independent synthesis validation is unknown. Separate
  `_runN` conditions remain distinct, but are not automatically certified repeats.
- Notebook filters require thickness >= 70 micrometers and polymer 13–17 wt%,
  and exclude other inferred chemistries. Exploration coverage therefore omits
  excluded experiments; this is a selected history, not every attempted experiment.
- Source names and timestamps are preserved. Notebook effective-date rules also
  apply to exported stock ages and date-filter membership.
- Historical LLM suggestions are not used as observations. Reports are rebuilt locally from the
  aggregate measurements and context, with missing values explicitly unknown.

Regenerate with the current notebook-default filters:

```console
python EVALUATE/export_warm_start.py
```

To export a differently filtered dataframe directly in the notebook:

```python
from export_warm_start import export_warm_start
export_warm_start(campaign_detailed, repo_root / "data/warm_start/custom.csv")
```

For custom selections, pass `selection_description="..."` to document your filters
in the companion JSON.

Dated PSf/PolarClean snapshot: September 25, 2026
------------------------------------------------

`polysulfone_polarclean_through_2026-09-25.csv` contains 94 unique conditions:
66 from the original warm start and 28 from `begins_2026-09-21/llm.csv`.
All aggregate Mean/SD columns are preserved; 91 rows have both objective means.
The latest specimen timestamp is September 25, 2026 at 12:31:24.
The companion JSON documents sources, counts, selection, and limitations.

The September 21 campaign's proposal reports omitted some measured properties.
Those measurements remain valid numeric history and are included by the new
structured proposal context. The export preserves reports and marks that campaign
with `proposal_context_version`; historical chemistry inference stays separate
from the newer recorded polymer/solvent identities. Original CSVs are unchanged.

This dated snapshot is archival and is not refreshed by notebook synchronization.
Use the two canonical filenames above for notebook-matched warm starts. The
pipeline uses whichever path is configured in `LLM_AL_WARM_START_CSV`; select the
file matching the campaign chemistry and restart the process after changing it.
