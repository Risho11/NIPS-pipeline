"""Robot-side Temperature Module check using the campaign's OT2 initializer.

Copy beside protocol-multithreaded.py, robot.json, and lib/, then run:
    python heater_connection_test.py
    python heater_connection_test.py --samples 12 --interval 5

Stop other protocols/notebooks controlling the OT-2 before running. Initialization
loads the campaign labware and pipette and HOMES the OT-2. Each sample deactivates
the heater; no heating target, pipetting, arm, chiller, or campaign is started.
robot.json is read only. The shared initializer may create bottle_inventory.json
if it does not exist, as it does during normal campaign startup.
"""
import argparse
import datetime
import json
import logging
import math
from pathlib import Path
import sys
import threading
import time
import traceback


ROOT = Path(__file__).resolve().parent


def log(message):
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


class PollingErrors(logging.Handler):
    """Capture asynchronous driver errors that do not raise in the calling thread."""
    def __init__(self):
        super().__init__(logging.ERROR)
        self.failed = threading.Event()

    def emit(self, record):
        if record.name.startswith('opentrons'):
            self.failed.set()
            log(f"BACKGROUND ERROR [{record.name}]: {record.getMessage()}")


def check_heater(ot2, samples, interval, errors):
    if not ot2.has_temp():
        raise RuntimeError('OT2 initialization did not load a temperature module.')
    log('Temperature module loaded through OT2(heater=True).')
    for sample in range(1, samples + 1):
        if errors.failed.is_set():
            raise RuntimeError('Opentrons reported a background error; see traceback above.')
        started = time.monotonic()
        log(f'[{sample}/{samples}] Sending heater deactivate command...')
        ot2._deactivate_temp()
        log(f'Deactivate returned after {time.monotonic() - started:.2f}s.')
        # These API properties may be cached by the module's background poller.
        temperature = ot2.temp_mod.temperature
        status = ot2.temp_mod.status
        log(f'Reported temperature={temperature!r} C; status={status!r} (polled API values).')
        if temperature is None or not math.isfinite(float(temperature)):
            raise RuntimeError(f'No valid temperature reading: {temperature!r}')
        # Include a final observation window so late polling errors are not missed.
        if errors.failed.wait(interval):
            raise RuntimeError('Opentrons reported a background error during observation.')
    log('PASS: module loaded, deactivate commands returned, and no Opentrons ERROR '
        'logs were captured during this test. This does not rule out intermittent disconnects.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--samples', type=int, default=6)
    parser.add_argument('--interval', type=float, default=5,
                        help='Observation seconds after each command (default: 5).')
    args = parser.parse_args(argv)
    if args.samples < 1 or not math.isfinite(args.interval) or args.interval <= 0:
        parser.error('samples and interval must be positive; interval must be finite')

    state = json.loads((ROOT / 'robot.json').read_text())
    print('Stop the robot campaign and other OT-2 control sessions first.\n'
          'This test loads the same OT2 class as protocol-multithreaded.py, HOMES\n'
          'the OT-2, and deactivates the temperature module. Clear the homing path.\n'
          'Power on and connect the module before continuing.', flush=True)
    if input('Ready for initialization and homing? (Y/N): ').strip().lower() != 'y':
        log('Cancelled before hardware initialization.')
        return 0

    errors = PollingErrors()
    logging.getLogger().addHandler(errors)
    stage = 'importing OT2'
    try:
        sys.path.insert(0, str(ROOT / 'lib'))
        from ot2 import OT2
        stage = 'OT2 initialization / module loading / homing'
        log(f'Initializing OT2 with heater=True, tip_index={state["tip_index"]}, '
            f'heater_well_index={state["heater_well_index"]}')
        # Same constructor and robot.json arguments as protocol-multithreaded.py.
        ot2 = OT2(tip_index=state['tip_index'], heater=True,
                  heater_well_index=state['heater_well_index'])
        if ot2.protocol.is_simulating():
            raise RuntimeError('Simulation cannot confirm a physical module connection.')
        stage = 'heater communication checks'
        check_heater(ot2, args.samples, args.interval, errors)
        return 0
    except (Exception, KeyboardInterrupt):
        log(f'FAILED or interrupted during {stage}. No automatic retry or robot movement.')
        traceback.print_exc()
        return 1
    finally:
        logging.getLogger().removeHandler(errors)


if __name__ == '__main__':
    sys.exit(main())
