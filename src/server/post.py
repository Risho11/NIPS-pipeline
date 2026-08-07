import urllib.request
import json

params = {
    "mixing_temp": 25,
    "bath_temp": 13,
    "weight_percent": 17,
    "volume": 1000,
    "pullcast_speed": 10,
    "nitrogen": False,
    "coupon_to_bath_wait_time": 120,
    "nips_bath_wait_time": 1800
    }

response = urllib.request.urlopen("http://169.254.46.48:8000", json.dumps(params).encode())
