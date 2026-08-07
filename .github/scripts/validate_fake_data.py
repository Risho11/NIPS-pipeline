"""Validate fake-data conditions have params.json and correct specimen file counts."""
import re, sys
from pathlib import Path

EXPECTED_PAIRS = {
    "short-nips-30s":             3,
    "nips-300s-gap-within-zeros": 3,
    "nips-600s-tight-boundary":   3,
    "nips-660s-just-over":        3,
    "nine-per-phase-1800s":       9,
    "double-run-4-clusters":      6,
    "multi-date-two-runs":        6,
    "pipeline-all-pass":          3,
    "pipeline-some-fail":         3,
}

SPECIMEN_RE = re.compile(r"^Specimen_\d+_\d{8}_\d{6}\.csv$")

errors = []
base = Path("data/raw/fake-data")

if not base.exists():
    print("FAIL data/raw/fake-data not found")
    sys.exit(1)

for condition, expected_pairs in EXPECTED_PAIRS.items():
    d = base / condition
    if not d.exists():
        errors.append(f"missing condition folder: {condition}")
        continue
    if not (d / "params.json").exists():
        errors.append(f"{condition}: missing params.json")
    csvs = [f for f in d.iterdir() if SPECIMEN_RE.match(f.name)]
    expected_files = expected_pairs * 2
    if len(csvs) != expected_files:
        errors.append(f"{condition}: expected {expected_files} specimen CSVs, got {len(csvs)}")

if errors:
    print(f"FAIL fake-data integrity ({len(errors)} error(s)):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print(f"PASS all {len(EXPECTED_PAIRS)} fake-data conditions intact")
