# dry_run_post.py
#
# "Fake run loop" sender for the opentrons dry run. Loads a params JSON
# file and POSTs it to the dry-run robot server
# (2025-07-02/protocol-dryrun.py), which listens on port 8001 (the
# production server listens on port 8000).
#
# See TESTS/DRY_RUN_README.md for full details.
#
# Usage:
#   python dry_run_post.py [path/to/params.json]
#
# If no path is given, defaults to dry_run_params.json in this folder.

import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

DRY_RUN_URL = "http://169.254.46.48:8001/run"
TIMEOUT = 30

params_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "dry_run_params.json"

with open(params_file) as f:
    params = json.load(f)

print(f"Posting {params_file} to {DRY_RUN_URL}:")
print(json.dumps(params, indent=2))

# A hung/missing response here means the dry-run server never started the
# opentrons steps - fail loudly instead of leaving the caller waiting forever
# with no indication anything went wrong.
try:
    with urllib.request.urlopen(DRY_RUN_URL, json.dumps(params).encode(), timeout=TIMEOUT) as response:
        print("Response:", response.read().decode())
except urllib.error.HTTPError as e:
    sys.exit(
        f"FATAL: dry-run server at {DRY_RUN_URL} rejected params {params_file} "
        f"with HTTP {e.code} {e.reason}: {e.read().decode(errors='replace')}"
    )
except urllib.error.URLError as e:
    sys.exit(
        f"FATAL: no response from dry-run server at {DRY_RUN_URL} within {TIMEOUT}s "
        f"for params {params_file}. Reason: {e.reason}"
    )
