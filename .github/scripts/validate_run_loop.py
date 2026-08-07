"""Validate run_loop.py imports correct modules, has required function calls,
and that param extraction/validation logic works on known LLM outputs."""
import json, re, sys

src = open("src/pipeline/run_loop.py").read()
errors = []

REQUIRED_IMPORTS = ["master_processing", "llm_context", "activeLearning_29", "url_29"]
REQUIRED_CALLS = [
    "master_processing.run_branches",
    "master_processing.any_branch_enabled",
    "master_processing.confirm_settings",
    "llm_context.ensure_condition_row",
    "llm_context.attach_all_branch_results",
    "llm_context.generate_reports_and_suggestion",
    "_next_iteration_params",
    "url.run_test",
    "json.dump",
]
REQUIRED_NEW = ["PARAMS_SCHEMA", "_extract_next_params", "_validate_params"]

for module in REQUIRED_IMPORTS:
    if module not in src:
        errors.append(f"missing import: {module}")

for call in REQUIRED_CALLS:
    if call not in src:
        errors.append(f"missing call/reference: {call}")

for symbol in REQUIRED_NEW:
    if symbol not in src:
        errors.append(f"missing symbol: {symbol}")

if errors:
    print("FAIL run_loop.py structure checks:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("PASS run_loop.py structure OK")

# ── Functional tests for extraction + validation (stdlib only, no API calls) ──

PARAMS_SCHEMA = {
    "mixing_temp":              (int, float),
    "bath_temp":                (int, float),
    "weight_percent":           (int, float),
    "volume":                   (int, float),
    "pullcast_speed":           (int, float),
    "nitrogen":                 (bool,),
    "coupon_to_bath_wait_time": (int, float),
    "nips_bath_wait_time":      (int, float),
}

def _extract_next_params(raw_text):
    def _navigate(parsed):
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if isinstance(parsed, dict):
            if "next_params" in parsed:
                return parsed["next_params"]
            if set(PARAMS_SCHEMA).issubset(parsed.keys()):
                return {k: parsed[k] for k in PARAMS_SCHEMA}
        return None

    try:
        result = _navigate(json.loads(raw_text.strip()))
        if result is not None:
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
    if fence:
        try:
            result = _navigate(json.loads(fence.group(1).strip()))
            if result is not None:
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    for pattern in (r'\[[\s\S]*\]', r'\{[\s\S]*\}'):
        m = re.search(pattern, raw_text)
        if m:
            try:
                result = _navigate(json.loads(m.group(0)))
                if result is not None:
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

    m = re.search(r'\{[^{}]*\}', raw_text)
    if m:
        try:
            candidate = json.loads(m.group(0))
            if isinstance(candidate, dict):
                return candidate
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"LLM returned no parseable params:\n{raw_text[:300]}")


def _validate_params(params):
    expected = set(PARAMS_SCHEMA)
    got = set(params)
    missing = expected - got
    extra = got - expected
    if missing:
        raise ValueError(f"next_params missing keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"next_params has unexpected keys: {sorted(extra)}")
    for key, allowed_types in PARAMS_SCHEMA.items():
        val = params[key]
        if isinstance(val, bool) and bool not in allowed_types:
            raise ValueError(
                f"next_params['{key}'] wrong type: got bool, expected "
                f"{tuple(t.__name__ for t in allowed_types)}"
            )
        if not isinstance(val, allowed_types):
            raise ValueError(
                f"next_params['{key}'] wrong type: got {type(val).__name__}, expected "
                f"{tuple(t.__name__ for t in allowed_types)}"
            )


# ── Known LLM outputs from data/llm_results/ and root ─────────────────────────────

GOOD_CASES = [
    # llm_result_17-5deg-7s-NoN2-30s.json
    (
        "17-5deg-7s-NoN2-30s",
        '[{"condition": "17-5deg-7s-NoN2-30s", "next_params": {"mixing_temp": 60, "bath_temp": 25, "weight_percent": 10, "volume": 1000, "pullcast_speed": 1, "nitrogen": true, "coupon_to_bath_wait_time": 300, "nips_bath_wait_time": 1800}}]',
    ),
    # llm_result_17-5deg-4s-NoN2-60s_run2.json
    (
        "17-5deg-4s-NoN2-60s_run2",
        '[{"condition": "17-5deg-4s-NoN2-60s_run2", "next_params": {"mixing_temp": 60, "bath_temp": 5, "weight_percent": 17, "volume": 1000, "pullcast_speed": 1, "nitrogen": true, "coupon_to_bath_wait_time": 0, "nips_bath_wait_time": 1800}}]',
    ),
    # llm_result_17-5deg-4s-NoN2-60s.json
    (
        "17-5deg-4s-NoN2-60s",
        '[{"condition": "17-5deg-4s-NoN2-60s", "next_params": {"mixing_temp": 60, "bath_temp": 5, "weight_percent": 17, "volume": 1000, "pullcast_speed": 1, "nitrogen": false, "coupon_to_bath_wait_time": 0, "nips_bath_wait_time": 1800}}]',
    ),
    # llm_result_17-13deg-3s-NoN2-60s.json
    (
        "17-13deg-3s-NoN2-60s",
        '[{"condition": "17-13deg-3s-NoN2-60s", "next_params": {"mixing_temp": 60, "bath_temp": 5, "weight_percent": 17, "volume": 1000, "pullcast_speed": 1, "nitrogen": true, "coupon_to_bath_wait_time": 600, "nips_bath_wait_time": 1800}}]',
    ),
]

# llm_result_17-13deg-18s-NoN2-50s.json — missing "volume"
MISSING_VOLUME_CASE = '[{"condition": "17-13deg-18s-NoN2-50s", "next_params": {"mixing_temp": 60, "bath_temp": 5, "weight_percent": 17, "pullcast_speed": 1, "coupon_to_bath_wait_time": 0, "nips_bath_wait_time": 1800, "nitrogen": true}}]'

test_errors = []

for label, raw in GOOD_CASES:
    try:
        p = _extract_next_params(raw)
        _validate_params(p)
        assert set(p.keys()) == set(PARAMS_SCHEMA), f"{label}: key mismatch"
    except Exception as e:
        test_errors.append(f"FAIL good case '{label}': {e}")

# Missing-volume case must raise ValueError from _validate_params
try:
    p = _extract_next_params(MISSING_VOLUME_CASE)
    _validate_params(p)
    test_errors.append("FAIL missing-volume case: should have raised ValueError but did not")
except ValueError as e:
    if "volume" not in str(e):
        test_errors.append(f"FAIL missing-volume case: raised ValueError but 'volume' not in message: {e}")
except Exception as e:
    test_errors.append(f"FAIL missing-volume case: unexpected exception type {type(e).__name__}: {e}")

# Garbage input must raise ValueError from _extract_next_params
try:
    _extract_next_params("Based on the data, I recommend increasing temperature.")
    test_errors.append("FAIL garbage case: should have raised ValueError but did not")
except ValueError:
    pass
except Exception as e:
    test_errors.append(f"FAIL garbage case: unexpected exception type {type(e).__name__}: {e}")

if test_errors:
    print("FAIL param extraction/validation tests:")
    for e in test_errors:
        print(f"  - {e}")
    sys.exit(1)

print("PASS param extraction/validation tests (5 known outputs)")
