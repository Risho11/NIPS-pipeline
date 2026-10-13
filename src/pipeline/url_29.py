import urllib.request
import urllib.error
import http.client
import json
import socket
import time
import uuid

BASE_URL = "http://169.254.46.48:8000"
ATTEMPTS = 3
HEALTH_TIMEOUT = 60
HEALTH_RETRY_WAIT = 30
NETWORK_ERRORS = (urllib.error.URLError, OSError, http.client.HTTPException)


def check_health(timeout=HEALTH_TIMEOUT, attempts=ATTEMPTS, expected_journal=None):
    """Read-only preflight. No robot action is sent by this function."""
    destination = f"{BASE_URL}/health"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(destination, timeout=timeout) as response:
                health = json.loads(response.read())
            if (health.get('service') != 'membrane-robot'
                    or health.get('idempotency_version') != 1):
                raise RuntimeError('Robot server lacks durable duplicate protection. Deploy updated robot files first.')
            uuid.UUID(health['journal_id'])
            if expected_journal and health['journal_id'] != expected_journal:
                raise RuntimeError('Robot journal changed. Stop and inspect robot state; do not discard the checkpoint.')
            return health
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Health endpoint {destination} returned HTTP {exc.code}; deploy/check the robot server.') from exc
        except NETWORK_ERRORS as exc:
            print(f'[robot] destination={destination} stage=preflight attempt={attempt}/{attempts} error={exc}')
            if attempt == attempts:
                raise RuntimeError(f'Robot preflight failed at {destination}; no POST sent by this call. Check campaign process and port 8000, then resume the same checkpoint.') from exc
            print(f'[robot] stage=preflight retry_in={HEALTH_RETRY_WAIT}s timeout={timeout}s')
            time.sleep(HEALTH_RETRY_WAIT)


def _proven_before_send(exc):
    # Do not classify arbitrary timeouts/resets as safe: they may follow a write.
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    return isinstance(reason, (socket.gaierror, ConnectionRefusedError))


def run_test(params, timeout=30, request_id=None, journal_id=None):
    """Retry one logical submission only against a verified durable journal."""
    if isinstance(params, (str, bytes)):
        params = json.loads(params)
    if not isinstance(params, dict):
        raise TypeError('Experiment parameters must be a JSON object')
    payload = json.dumps(params, allow_nan=False).encode('utf-8')
    request_id = request_id or str(uuid.uuid4())
    uuid.UUID(request_id)
    destination = f'{BASE_URL}/run'
    for attempt in range(1, ATTEMPTS + 1):
        health = check_health(expected_journal=journal_id)
        journal_id = health['journal_id']
        request = urllib.request.Request(destination, data=payload, headers={
            'Content-Type': 'application/json', 'X-Request-ID': request_id,
            'X-Journal-ID': journal_id,
        })
        print(f'[robot] destination={destination} stage=submission request_id={request_id} attempt={attempt}/{ATTEMPTS}')
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = response.read().decode('utf-8')
            ack = json.loads(result)
            if ack.get('request_id') != request_id or ack.get('status') not in ('accepted', 'completed'):
                raise RuntimeError('Invalid robot acknowledgement; preserve checkpoint and inspect robot logs.')
            print(f'[robot] request_id={request_id} stage=acknowledged duplicate={ack.get("duplicate")}')
            return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'Robot submission HTTP {exc.code} at {destination}, request_id={request_id}: {body}. Preserve checkpoint; inspect robot state before manual recovery.') from exc
        except NETWORK_ERRORS as exc:
            stage = 'before-send' if _proven_before_send(exc) else 'outcome-unknown'
            print(f'[robot] destination={destination} stage={stage} request_id={request_id} attempt={attempt}/{ATTEMPTS} error={exc}')
            if attempt == ATTEMPTS:
                raise RuntimeError(f'Robot submission retries exhausted: {destination}, request_id={request_id}, stage={stage}. Restore server connectivity and resume the same checkpoint/ID; do not start a fresh experiment.') from exc
            # Ambiguous failures are retried ONLY with the same persisted server journal and ID.
            time.sleep(2 ** (attempt - 1))


def run_test_json(params, timeout=30):
    return run_test(params, timeout=timeout)

# methods for getting data about the machine
def get_coupons():
    with urllib.request.urlopen(f"{BASE_URL}/coupons") as response:
        return json.loads(response.read())
def get_rings():
    with urllib.request.urlopen(f"{BASE_URL}/rings") as response:
        return json.loads(response.read())
def get_discard():
    with urllib.request.urlopen(f"{BASE_URL}/discard") as response:
        return json.loads(response.read())
def get_tip_index():
    with urllib.request.urlopen(f"{BASE_URL}/tipindex") as response:
        return json.loads(response.read())
def get_heater_well_index():
    with urllib.request.urlopen(f"{BASE_URL}/heaterwellindex") as response:
        return json.loads(response.read())

# methods for setting data about the machine
def set_coupons(num):
    data = json.dumps(num).encode()
    urllib.request.urlopen(f"{BASE_URL}/setcoupons", data=data)
def set_rings(num):
    data = json.dumps(num).encode()
    urllib.request.urlopen(f"{BASE_URL}/setrings", data=data)
def set_discard(num):
    data = json.dumps(num).encode()
    urllib.request.urlopen(f"{BASE_URL}/setdiscard", data=data)
def set_tip_index(num):
    data = json.dumps(num).encode()
    urllib.request.urlopen(f"{BASE_URL}/settipindex", data=data)
def set_heater_well_index(num):
    data = json.dumps(num).encode()
    urllib.request.urlopen(f"{BASE_URL}/setheaterwellindex", data=data)
