"""Validate run_loop.py imports correct modules and has required function calls."""
import sys

src = open("run_loop.py").read()
errors = []

REQUIRED_IMPORTS = ["processing_29", "activeLearning_29", "url_29"]
REQUIRED_CALLS = [
    "save_to_csv",
    "Generate_report",
    "LLM_AL",
    "url.run_test",
    "aggregate_path",
    "CSV_AGG_LLM",
    "promote_to_main",
    "json.dump",
]

for module in REQUIRED_IMPORTS:
    if module not in src:
        errors.append(f"missing import: {module}")

for call in REQUIRED_CALLS:
    if call not in src:
        errors.append(f"missing call/reference: {call}")

if errors:
    print("FAIL run_loop.py validation:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("PASS run_loop.py structure OK")
