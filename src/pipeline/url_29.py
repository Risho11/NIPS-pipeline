import urllib.request
import urllib.error
import json

# this file is a small library for holding code about sending http requests to the opentrons
# used for starting a compression test or getting information about the status of the machine

BASE_URL = "http://169.254.46.48:8000" # url of the http server running on the opentrons

# run a test, takes a python object as arguments
def run_test(params, timeout=30):
    """Run a test, takes either a python dict/list or a JSON string/bytes object."""
    # 1. Safely normalize whatever type comes in into bytes
    if isinstance(params, (dict, list)):
        print("Python recieved!")
        payload = json.dumps(params).encode('utf-8')
    elif isinstance(params, str):
        print("JSON string recieved!")
        payload = params.encode('utf-8')
    elif isinstance(params, bytes):
        print("Pure JSON bytes recieved!")
        payload = params
    else:
        raise TypeError(f"Unsupported parameters type: {type(params)}")
    # 2. Build the Request object to explicitly inject JSON headers
    print(f"Exact payload being sent: {payload.decode('utf-8')}")
    url = f"{BASE_URL}/run"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=payload, headers=headers)

    # 3. Open the connection safely using a 'with' block so it never hangs open
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = response.read().decode('utf-8')
            print(f"Opentrons response: {result}")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"Opentrons rejected request! Code: {e.code}, Reason: {e.reason}, Body: {body}")
        raise
    except urllib.error.URLError as e:
        print(f"Network connection issue to Opentrons: {e.reason}")
        raise
    except Exception as e:
        print(f"Unexpected error in run_test: {type(e).__name__}: {e}")
        raise

# same idea but takes a json string as arguments
# the llm active learning thing should spit out just a json string not a python object so this might be better
def run_test_json(params, timeout=30):
    urllib.request.urlopen(f"{BASE_URL}/run", params.encode(), timeout=timeout)

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