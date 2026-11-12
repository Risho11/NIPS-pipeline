# Pareto validation protocol

The frozen [plan](../protocols/pareto_validation_plan.json) contains the approved
five PSf and five Primospire conditions, with original `params.json` hashes and
exact recorded settings. It does not rerank candidates or use active learning.

Run the separate [Mini PC runner](../src/pipeline/run_pareto_validation.py) from
the repository root. Preview needs no camera, robot connection, or setup file:

```powershell
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py
```

Each condition gets **three independently fabricated samples**. Each sample gets
two blank-coupon zero tests and two membrane tests, using **coupon test 2 then
coupon test 4** in both phases. The total is 30 samples, 60 membrane tests, and
60 zero tests. The two locations are within-sample measurements, not independent
synthesis repeats. All three synthesis repeats of a condition run consecutively
before advancing to the next condition. For `psf-water`, the order is
V1 ×3 → V2 ×3 → V4 ×3 → V5 ×3.

## Bottom-location mapping

Bottom means the **start of blade casting**, as specified by the operator.
In `OT2_Server_2026-06-11/lib/arm.py`, casting moves X=215 to X=110. The coupon
pickup at the casting station has yaw −90°, and the flattened coupon at the
tester has yaw +91°. Thus the casting direction is approximately +X in the
tester frame. The probe stays fixed while the coupon moves: the larger coupon
pose X=170 places the casting-start side under it. These are tests **2 and 4**,
at Y=355 and Y=365. Tests 1 and 3 use X=160 and correspond to the other side.
No calibrated coordinates were changed. This mapping was traced from source
motions; it has not been verified by moving the physical apparatus.

## Deploy the robot-side support

With the campaign stopped, deploy these files to their existing robot locations:

- `OT2_Server_2026-06-11/protocol-multithreaded.py`
- `OT2_Server_2026-06-11/lib/compression_plan.py` (new helper)
- `OT2_Server_2026-06-11/lib/request_server.py`
- `OT2_Server_2026-06-11/lib/ot2.py` (polymer/solvent-only stock support)
- `OT2_Server_2026-06-11/lib/calculations.py` (two-liquid mass balance)

Start the robot protocol normally. Its existing startup checks and operator
hardware-state confirmation remain in place. Keep real compression and pictures
enabled. Requests without `compression_test_locations` still use the historical
four-location behavior. Requests for this plan use the same two-location tuple
in both blank and membrane phases. The updated health endpoint advertises this
capability, and the Mini PC refuses an older server that might ignore it.

The legacy `src/pipeline/run_loop.py` is unchanged. Stop that campaign before
starting this runner: only one Mini PC server can own port 8000 and this robot.
The runner uses the existing Mini PC address `169.254.230.148:8000` and robot
address `169.254.46.48:8000`; the robot's `lib/url.py` must point to the same Mini PC.

## Material batches and installed stock settings

The plan deliberately stops at material/bath boundaries. It does not replace
the physical stocks or prepare a different bath automatically.

The configured file `protocols/pareto_validation_setup.local.json` now records
the operator's chosen **polymer stock + pure solvent only**, with no additive
stock: 17 wt% PSf for both PSf batches and 21 wt% Primospire for its batch.
Its `stock_metadata` objects are:

```json
{"stock_mode": "polymer_solvent", "polymer_stock_wt_percent": 17.0}
```

Use 21.0 for Primospire. No unused bottle compositions are supplied or assumed.
PSf V1 and V2 use undiluted stock at their specified 25°C; all other selected
recipes require dilution. Existing calculator density defaults (polymer stock
1.10 and solvent 1.028) are retained in the mass balance; they are assumptions,
not newly measured densities for either chemistry. Dispensing retains the
existing nearest-microliter rounding convention.

| Batch | Conditions | New samples | Material / bath |
|---|---|---:|---|
| `psf-water` | PSf V1, V2, V4, V5 | 12 | Polysulfone / PolarClean; water bath |
| `psf-bath-10wt` | PSf V3 | 3 | Polysulfone / PolarClean; 10 wt% PolarClean bath |
| `primospire-water` | Primospire V1–V5 | 15 | Primospire / NMP; water bath |

Copy `protocols/pareto_validation_setup.template.json` to a local setup file,
for example `protocols/pareto_validation_setup.local.json`. Keep its material
declarations unchanged and fill each batch's `stock_metadata` using the **actual
installed stocks**. Null values intentionally prevent execution until these
operator settings are supplied. No stock concentrations have been assumed.

For `two_bottle`, the object requires these keys (all concentration values are
wt%):

```text
stock_mode: "two_bottle"
polymer_stock_wt_percent: actual bottle-1 polymer concentration
additive_stock_polymer_wt_percent: actual bottle-2 polymer concentration
additive_stock_additive_wt_percent: actual bottle-2 additive concentration
```

For `four_bottle`, use `stock_mode: "four_bottle"`, `polymer_stock_pwt`,
`solvents_cswt`, `all_mix_pwt`, and `all_mix_cswt`, with the actual concentrations.
The installed bottles and solvent identities must correspond to the batch.

The runner checks feasibility using these supplied concentrations and sends
them as `stock_metadata`. It never projects a target to another composition.
It also rejects a heated recipe that would be drawn directly from an undiluted
stock bottle, because that robot path skips heated mixing. Supply suitable
stocks rather than silently changing the recorded temperature. This check does
not establish equivalence of stock age, ambient conditions, or historical timing.

## Run on the Mini PC

After loading the appropriate physical materials and bath, run one batch:

```powershell
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py --execute --batch psf-water --campaign pareto-validation-2026-11-12 --setup protocols/pareto_validation_setup.local.json
```

Run the other batches separately after the corresponding material/bath changes,
using `--batch psf-bath-10wt` and `--batch primospire-water`. Reuse the campaign
key to keep them together; use a new key for a genuinely new validation campaign.
The date in the example is just a label, not a scheduled launch.

Optional path/device overrides include `--csv-raw-path`, `--camera-index`,
`--server-ip`, `--server-port`, and `--robot-url`. The Newton directory defaults to
`C:\Users\opentrons\Documents\Newton Reports\With LVDT\Unnamed`; camera index
defaults to 2. A global local lock prevents two validation runner processes from
controlling the apparatus concurrently.

Raw measurements are copied into distinct
`data/raw/<campaign>_<batch>_V<n>_rep<n>/` directories. Original Newton files are
preserved. Each sample folder records exact returned parameters, source recipe,
protocol log, snapshots, and the zero/sample file order and location mapping.
Measurements are kept separate for every synthesis repeat.

State and new mechanical CSVs are written to
`data/results/begins_<campaign>/<batch>/`. The runner fits the two zero/sample
pairs through the existing mechanical pipeline. It does not call an LLM or run
the vision-quality branch. Mechanical fitting errors stop the batch with raw
data retained; failed fits are not replaced with inferred values.
Fit plots are retained under `data/plots/run-<campaign>-<batch>/`, with separate
sample identities and processing reruns preserved.

Use `--collect-only` to defer mechanical analysis during a batch. Afterwards:

```powershell
uv run --locked --no-sync python src/pipeline/run_pareto_validation.py --process-only --batch psf-water --campaign pareto-validation-2026-11-12
```

`--process-only` uses saved measurements and does not access the robot or camera.

## Resume and limits

Restart with the **same command, campaign key, setup, and paths**. The runner saves
each request UUID, robot journal identity, payload, and pre-run CSV boundary
before submission. It reuses those identities after an interrupted connection.
Completed samples are skipped. Once all samples are complete, the process exits
without submitting another experiment. Changing a saved campaign's configuration
is rejected. Do not delete either side's journal to clear an ambiguous run.
Checkpoints created under the earlier interleaved schedule are also rejected;
their completed and in-flight jobs must not be silently reordered.

The completion callback must match the active sample's saved parameters and ID.
The runner also waits for that robot request to be marked completed before it
collects data or starts another sample. A missing callback, failed request,
changed old Newton file, extra/missing new CSV, or missing image stops progression.
Exactly four new Newton CSVs must exist for the active sample; the runner never
takes the last eight files or fills a missing curve from a previous experiment.

Ctrl+C stops the Mini PC service; it is **not a robot emergency stop** and does
not cancel an accepted physical job. An interrupted robot job needs inspection
before recovery. A sample times out after four hours by default; change
`--sample-timeout` in seconds if needed. Restoring connectivity and reusing the
same checkpoint cannot automatically repair a physical crash or redo a failed job.

Validation performed here uses mocked hardware and temporary data, including
two-location dispatch, unchanged four-location defaults, exact frozen recipes,
file boundaries, callback identity, stock checks, finite batch completion and
resume deduplication. These checks do not establish live hardware readiness.
