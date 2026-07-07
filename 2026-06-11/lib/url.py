import urllib.request
import json

# the Newton software to talk to the compression tester runs on the laptop under windows
# this module is for communicating with that laptop to see if the test finished sucessfully, or if the pin is in an unsafe position

BASE_URL = "http://169.254.230.148:8000" # url of the http server running on the mini pc

# GET methods, since we just need the server to do the action and then send us a response
def get_compressiontester_status():
    with urllib.request.urlopen(f"{BASE_URL}/compressiontester/status") as response:
        return json.loads(response.read())

def take_snapshot():
    with urllib.request.urlopen(f"{BASE_URL}/camera/snapshot") as response:
        return json.loads(response.read())

# POST method, since we want to pass the parameters to the server
def start_processing(params):
    data = json.dumps(params).encode()
    with urllib.request.urlopen(f"{BASE_URL}/server/process", data=data, timeout=86400) as response:
        return json.loads(response.read())