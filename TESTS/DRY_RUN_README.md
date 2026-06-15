# Opentrons Dry Run

## Purpose

A fast way to exercise the **real opentrons hardware** (mixing, dispensing,
pullcast) for a given set of parameters, without running through the full
compression-tester cycle (3 "zero" tests on a fresh coupon + 3 "membrane"
tests after the NIPS bath), which is normally the slowest part of a run.

Use this when you've changed something about the opentrons protocol (e.g.
solution prep, pullcast speed/timing) and want to confirm it still works on
real hardware quickly, without waiting through compression testing.

## Files

| File | Role |
| --- | --- |
| `2025-07-02/protocol-dryrun.py` | Robot/jupyter-side HTTP server. Manually-maintained copy of `2025-07-02/protocol-multithreaded.py` with dry-run flags added. Runs on the robot machine, controls Arm/OT2/Chiller/Uno hardware. |
| `TESTS/dry_run_post.py` | "Fake run loop" sender, runs on the minipc. Loads a params JSON file and POSTs it to `protocol-dryrun.py`. Equivalent to `minipc/post.py` / `run_loop.py`'s `INITIAL_PARAMS` POST, but file-driven and aimed at the dry-run server. |
| `TESTS/dry_run_params.json` | Sample params (same schema as `run_loop.py`'s `INITIAL_PARAMS`), with short `coupon_to_bath_wait_time` / `nips_bath_wait_time` so a dry run finishes quickly. |

## How `protocol-dryrun.py` differs from `protocol-multithreaded.py`

It is a **manually-maintained copy**, not an import — if you change
`protocol-multithreaded.py`'s hardware logic (mixing, dispensing, pullcast,
NIPS bath, ring placement, arm waypoints, etc.), mirror the change here too,
otherwise the dry run will drift out of sync and may not reflect real
behaviour.

### Dry-run config flags (top of the file)

```python
DRY_RUN_COMPRESSION_TESTS = True   # default: skip compression tester entirely
DRY_RUN_CHILLER = False            # default: chiller runs for real
DRY_RUN_KNIFE_CLEANING = False     # default: knife cleaning runs for real
DRY_RUN_CAMERA = False             # default: camera snapshots run for real
```

Opentrons calls (`opentrons.*`, `xArm.pullcast`, etc.) are **never** gated by
a flag — they always run for real, since testing them is the point of this
script.

- **`DRY_RUN_COMPRESSION_TESTS`** (corresponds to
  `protocol-multithreaded.py` lines ~111-184 and ~334-394):
  - In `zero_and_place_coupon()`: instead of the lock-juggling
    pick-up-coupon -> 3 zero compression tests -> place-on-stand sequence,
    just picks up a coupon and places it directly on the opentrons stand
    (`xArm.pick_up_coupon()` -> `xArm.put_down("coupon angled opentrons",
    pitch=False)` -> mark stand "clean").
  - At the end of `run_test()`: instead of moving the coupon to the
    compression tester for the 3 membrane tests, goes straight from the
    pre-bath photo to a post-bath photo and discards the coupon.
  - When `False`, both sections fall back to the original
    `protocol-multithreaded.py` logic verbatim (including `arduino.run_test()`
    and `url.get_compressiontester_status()` calls).

- **`DRY_RUN_CHILLER`** (corresponds to line ~209,
  `chiller.go_to_temperature`): when `True`, the chiller background thread is
  a no-op so `chiller_process.join()` returns immediately. Set to `False` if
  you want to verify chiller behaviour too.

- **`DRY_RUN_KNIFE_CLEANING`** (corresponds to line ~281-282,
  `delayed_knife_cleaning`): when `True`, skips the 300s-delayed knife
  cleaning arm sequence.

- **`DRY_RUN_CAMERA`** (corresponds to `url.take_snapshot()` calls at lines
  ~332 and ~395): when `True`, skips both pre- and post-bath snapshot
  requests to the minipc camera.

### Port

`protocol-dryrun.py` binds to **`169.254.46.48:8001`** (the production
`protocol-multithreaded.py` uses port `8000`), so the two servers can run
without colliding or being confused for one another. `dry_run_post.py`
targets port 8001.

## Running a dry run

1. On the robot/jupyter machine, in the `2025-07-02` folder:
   ```
   python protocol-dryrun.py
   ```
   This prompts for the same robot-state confirmation as
   `protocol-multithreaded.py`, plus prints the current `DRY_RUN_*` flag
   values so you can confirm the mode before continuing.

2. On the minipc, trigger a run with a params file:
   ```
   python TESTS/dry_run_post.py TESTS/dry_run_params.json
   ```
   or point it at any other JSON file with the same schema as
   `run_loop.py`'s `INITIAL_PARAMS` (`mixing_temp`, `bath_temp`,
   `weight_percent`, `volume`, `pullcast_speed`, `nitrogen`,
   `coupon_to_bath_wait_time`, `nips_bath_wait_time`).

3. At the end of the run, `protocol-dryrun.py` still calls
   `url.start_processing(parameters)`, so the minipc pipeline
   (`minipc/server.py`) will process the resulting files normally.

## Troubleshooting / keeping in sync

- If `protocol-multithreaded.py` changes (new arm waypoints, new parameters,
  changed lock ordering, etc.), update `protocol-dryrun.py`'s corresponding
  sections to match — diff the two files to find what's changed.
- If the dry run behaves unexpectedly, check the `DRY_RUN_*` flag values
  printed at startup first — it's easy to leave one flipped from a previous
  session.
- `robot.json` is shared state between `protocol-multithreaded.py` and
  `protocol-dryrun.py` (coupon/ring/discard counts, tip index, etc.) — running
  a dry run consumes coupons/rings just like a real run.
