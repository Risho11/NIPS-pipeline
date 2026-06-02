import urllib.request
import json

# this file is a small library for holding code about sending http requests to the opentrons
# used for starting a compression test or getting information about the status of the machine

BASE_URL = "http://169.254.46.48:8000" # url of the http server running on the opentrons

# run a test, takes a python object as arguments
def run_test(params, timeout=30):
    urllib.request.urlopen(f"{BASE_URL}/run", json.dumps(params).encode(), timeout=timeout)

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