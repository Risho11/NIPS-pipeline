# Experiment evidence and output contract

- `reps.csv`: specimen-level processing results. Several specimens from one
  synthesis are not independent synthesis repeats. Preserve Trial and fit flags.
- `agg.csv`: aggregate processing results, including pre/post-discard variants.
  Do not pool both variants as separate syntheses or silently discard exclusions.
- `llm.csv`: one promoted row per exact condition name, including `_runN` repeats.
  Use this selected processing version for trajectories. Source condition A's
  `LLM_suggestion` proposes the next experiment B; it is not A's measured result.
- `warm_start.csv` in frozen inputs is context from another source, never a new
  campaign measurement. Compare material/bath contexts explicitly. When names
  overlap, current campaign evidence supersedes historical evidence; never count
  the same condition twice. Unknown historical materials remain unknown.
- Frozen `context.json` records operator settings, the additive lock, stock
  metadata and allowed ranges. Never infer current settings from historical rows.
- Numeric measured fields take priority over narrative summaries. Use original
  precision for calculations. Missing is unknown, not zero. SD is intra-sample
  dispersion, not uncertainty across independent syntheses.
- Modulus and compression slopes use bar; thickness uses micrometers; compression
  changepoint is a dimensionless pore-fraction estimate, not porosimetry.
- The deterministic trajectory CSV/PNG uses promoted-row order, not measured
  elapsed time. Missing measurements are omitted from plots and remain missing in
  tables. The graph does not establish causality or reproducibility by itself.

## Author outputs

The JSON schema is generated from the corresponding Pydantic model for each
request; the same model validates the returned JSON. Stage fields are direct:
`HypothesisUpdate.hypotheses`, `ExperimentDesign.experiment` and
`ExperimentDecision.next_params`. The report field
contains readable English Markdown and evidence references. Analysis distinguishes
observations, interpretations and uncertainty. Hypotheses retain stable IDs,
statements, status, evidence and change reasons. Design states prediction,
comparator, support/refutation/inconclusive criteria and the full next conditions.

Only eight tunables appear in `next_params`: mixing_temp, bath_temp,
pullcast_speed, nitrogen, coupon_to_bath_wait_time, nips_bath_wait_time,
polymer_wt and additive_wt. Respect all supplied numeric ranges, stock polygon,
additive lock and the 25 C undiluted-stock constraint before QA. Operator material
and bath fields are attached by Python. The final main decision must exactly
match the reviewed design. Python rejects an invalid design instead of clamping it.

## Existing outputs

The deterministic processing pipeline alone writes measured `reps.csv` and
`agg.csv`. MAS reads them. Its accepted analysis is attached to `llm.csv`
initial_report/final_report, its final decision to LLM_suggestion, and its decision
report path to mas_report_path, on the exact current condition row only. Numeric
columns and other rows are preserved. No campaign row is invented at initialization.

For run, the existing `data/llm_results/llm_result_<source_condition>.json` remains
the executable next-condition payload with stock metadata. No such execution JSON
is created for hold/stop. The pipeline checkpoint points to the final decision.
