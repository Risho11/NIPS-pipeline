import urllib.request
import json

# the Newton software to talk to the compression tester runs on the laptop under windows
# this module is for communicating with that laptop to see if the test finished sucessfully, or if the pin is in an unsafe position

BASE_URL = "http://169.254.230.148:8000" # url of the http server running on the mini pc

# GET methods, since we just need the server to do the action and then send us a response
def get_compressiontester_status():
    with urllib.request.urlopen(f"{BASE_URL}/compressiontester/status") as response:
        return json.loads(response.read())

def take_snapshot(timeout=60):
    # Allow for the PC camera warm-up, capture, and disk write independently of
    # any global socket timeout installed by a robot library. Do not auto-retry:
    # a timed-out request may still have saved an image.
    with urllib.request.urlopen(f"{BASE_URL}/camera/snapshot", timeout=timeout) as response:
        result = json.loads(response.read())
    if result is not True:
        raise RuntimeError(f"PC did not confirm a saved camera snapshot: {result!r}")
    return result

# POST method, since we want to pass the parameters to the server
def start_processing(params, protocol_log=None):
    body = {"parameters": params}
    if protocol_log:
        body["protocol_log"] = protocol_log
    data = json.dumps(body).encode()
    with urllib.request.urlopen(f"{BASE_URL}/server/process", data=data, timeout=86400) as response:
        return json.loads(response.read())
