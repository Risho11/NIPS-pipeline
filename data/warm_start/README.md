Warm-start history for Polysulfone / PolarClean
=============================================

`polysulfone_polarclean.csv` contains 59 conditions matching the current
`campaign_trends.ipynb` selection, dated August 14 through September 5, 2026.
All 59 have the eight synthesis parameters; 56 have both elastic modulus and
pore fraction. The three with missing objectives remain useful parameter history.
The companion JSON records counts, campaign provenance, filters, and limitations.

In `src/pipeline/run_loop.py`, set:

```python
LLM_AL_SEARCH_MODE = "single"  # "double" or "explore" also work
LLM_AL_WARM_START_CSV = _REPO_ROOT / "data/warm_start/polysulfone_polarclean.csv"
```

For a new campaign, also set `CONTINUE_CAMPAIGN = None`. Restart the pipeline
after changing settings. The history is read when generating recommendations;
already-saved recommendations are not regenerated. Historical rows are never
copied into campaign CSVs or checkpoints. A current row with the same condition
name supersedes its historical row. Set the warm-start path to `None` to disable.

Single mode receives historical modulus and uncertainty; double mode also receives
the explicit pore-fraction reports; explore mode includes the historical parameter
points in its diversity context. All modes receive available quality reports.

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
- One source folder is named `begins_1999`; its retained condition has an actual
  specimen timestamp on August 19, 2026. Source names and timestamps are preserved.
- Historical LLM suggestions are excluded. Reports are rebuilt locally from the
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
