def _print(params):
    print(params["polymer_stock_wt_percent"])
    print(params["additive_stock_polymer_wt_percent"])
    print(params["additive_stock_additive_wt_percent"])

parameters = {
    "mixing_temp": 6,
    "bath_temp": 5,
    "pullcast_speed": 1,
    "nitrogen": False,
    "coupon_to_bath_wait_time": 55,
    "nips_bath_wait_time": 101,
    "polymer_wt": 17,
    "additive_wt": 5,
    "stock_metadata": {
        "polymer_stock_wt_percent": 21.0,
        "additive_stock_polymer_wt_percent": 21.0,
        "additive_stock_additive_wt_percent": 5.0
    }
}

air_data = {
    "air_temperature" : 15,
    "air_humidity" : 40
}

combined = {**parameters, **air_data}
print(combined)

parameters.update(air_data)
print(parameters)

