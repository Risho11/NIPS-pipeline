"""Validate all params.json files in compression-test-data have required keys and correct types."""
import json, sys
from pathlib import Path

REQUIRED_KEYS = {
    "mixing_temp":              (int, float),
    "bath_temp":                (int, float),
    "weight_percent":           (int, float),
    "pullcast_speed":           (int, float),
    "nitrogen":                 (bool,),
    "coupon_to_bath_wait_time": (int, float),
    "nips_bath_wait_time":      (int, float),
}

errors = []
checked = 0

for p in Path("compression-test-data").rglob("params.json"):
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        errors.append(f"{p}: invalid JSON — {e}")
        continue
    for key, types in REQUIRED_KEYS.items():
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
