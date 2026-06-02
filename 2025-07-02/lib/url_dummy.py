# modified to just emulate the functionality for the compression tester
# so we can test the rest of the system while the compressiontester is being repaired
import time

import urllib.request
import json

# the Newton software to talk to the compression tester runs on the laptop under windows
# this module is for communicating with that laptop to see if the test finished sucessfully, or if the pin is in an unsafe position

BASE_URL = "http://169.254.71.234:8000" # url of the http server running on the laptop

def get_compressiontester_status():
    modTime = time.time() - 10
    data = {
        "safe": True,
        "time": modTime
    }
    
    return data
    
    #with urllib.request.urlopen(f"{BASE_URL}/compressiontester/status") as response:
    #    return json.loads(response.read())

def take_snapshot():
    with urllib.request.urlopen(f"{BASE_URL}/camera/snapshot") as response:
        return json.loads(response.read())