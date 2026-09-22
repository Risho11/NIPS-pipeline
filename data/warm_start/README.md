Warm-start history for Polysulfone / PolarClean
=============================================

`polysulfone_polarclean.csv` contains 66 conditions from the exported notebook
selection through campaign `2026-08-22-exploration-mode`.
All 66 have the eight synthesis parameters; 63 have both elastic modulus and
pore fraction. The three with missing objectives remain useful parameter history.
The companion JSON records counts, campaign provenance, filters, and limitations.

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
Missing, empty, or invalid history stops startup rather than falling back to defaults.
With `LLM_AL_WARM_START_CSV = None`, new campaigns use `INITIAL_PARAMS`.
Explicit sweeps and campaigns with no enabled processing branches still use their
iteration lists. The history is read when generating recommendations;
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
