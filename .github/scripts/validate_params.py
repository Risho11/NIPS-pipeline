"""Validate all params.json files in data/raw have required keys and correct types.

Two schema generations legitimately coexist in real data:
  - old: weight_percent (single polymer concentration)
  - new: polymer_wt + additive_wt (polymer/additive campaign)
Each condition folder must match exactly one of the two, plus the common keys.
"""
import json, sys
from pathlib import Path

COMMON_KEYS = {
    "mixing_temp":              (int, float),
    "bath_temp":                (int, float),
    "pullcast_speed":           (int, float),
    "nitrogen":                 (bool,),
    "coupon_to_bath_wait_time": (int, float),
    "nips_bath_wait_time":      (int, float),
}
OLD_SCHEMA_KEYS = {"weight_percent": (int, float)}
NEW_SCHEMA_KEYS = {"polymer_wt": (int, float), "additive_wt": (int, float)}

errors = []
checked = 0

for p in Path("data/raw").rglob("params.json"):
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{p}: invalid JSON — {e}")
        continue

    is_old = "weight_percent" in data
    is_new = "polymer_wt" in data or "additive_wt" in data
    if is_old and is_new:
        errors.append(f"{p}: mixes old (weight_percent) and new (polymer_wt/additive_wt) schema keys")
        schema_keys = {}
    elif is_old:
        schema_keys = OLD_SCHEMA_KEYS
    elif is_new:
        schema_keys = NEW_SCHEMA_KEYS
    else:
        errors.append(f"{p}: has neither 'weight_percent' nor 'polymer_wt'/'additive_wt'")
        schema_keys = {}

    for key, types in {**COMMON_KEYS, **schema_keys}.items():
        if key not in data:
            errors.append(f"{p}: missing key '{key}'")
        elif not isinstance(data[key], types):
            errors.append(f"{p}: '{key}' wrong type (got {type(data[key]).__name__})")
    checked += 1

if errors:
    print(f"FAIL params.json validation ({len(errors)} error(s)):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print(f"PASS {checked} params.json files valid")
