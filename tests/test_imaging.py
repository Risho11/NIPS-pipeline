"""
test_imaging.py — run image_processing pipeline locally on Mac for one condition.

Sibling to test_processing.py, but image_processing only ever runs on one condition
at a time (no "run ALL" mode) — there's no LLM/CSV aggregation step downstream of it yet.

With membrane_imaging.SEND_RAW_IMAGE = True (the default), run() just locates the photo --
no pixel-math, no uniform_map/test_point/safe_radius, no LLM call here (see
TESTS/test_master.py for the vision-LLM quality-report step). Flip SEND_RAW_IMAGE to False in
membrane_imaging.py to exercise the legacy pixel-math path instead; this script handles both.

Edit DATA_ROOT and CONDITION below, then:
    python test_imaging.py

Outputs (legacy pixel-math path only):
  - image_tests/<condition>_uniform_map.png — visual: white/black/gray(170)=uniform region
  - image_tests/<condition>_result.json     — test_point + safe_radius
"""

import json
from pathlib import Path

import cv2

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # <<< IMPORT >>> points to project root where membrane_imaging.py lives
import membrane_imaging as imaging              # <<< IMPORT >>> must be in same folder

# ── edit these ──────────────────────────────────────────────────────────────
DATA_ROOT  = Path(__file__).parent.parent
CONDITION  = '17-5deg-340s-N2-1800s'
# <<< PATH >>> output files land beside this script
OUTPUT_DIR = Path(__file__).parent / "image_tests"
# ────────────────────────────────────────────────────────────────────────────

def _short(p):
    """Print paths starting after the repo root folder (Auto-Membranes/...) instead of
    the full absolute path — terminal display only, stored values stay untouched."""
    try:
        return str(Path(p).relative_to(DATA_ROOT))
    except ValueError:
        return str(p)


condition_dir = DATA_ROOT / "compression-test-data" / CONDITION
print(f"Data root      : {_short(DATA_ROOT)}")
print(f"Condition      : {CONDITION}")
print(f"Folder         : {_short(condition_dir)}")
print(f"SEND_RAW_IMAGE : {imaging.SEND_RAW_IMAGE}")
print()

result = imaging.run(condition_dir)

print(f"image used : {_short(result['image_path'])}")

if "uniform_map" not in result:
    print("(SEND_RAW_IMAGE=True — no pixel-math ran; the raw photo is what a vision LLM would "
          "see, see TESTS/test_master.py for the actual quality-report call)")
else:
    print(f"test_point  : {result['test_point']}")
    print(f"safe_radius : {result['safe_radius']}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    map_path = OUTPUT_DIR / f"{CONDITION}_uniform_map.png"
    cv2.imwrite(str(map_path), result["uniform_map"])

    json_path = OUTPUT_DIR / f"{CONDITION}_result.json"
    with open(json_path, "w") as f:
        json.dump({
            "condition": CONDITION,
            "image_path": result["image_path"],
            "test_point": result["test_point"],
            "safe_radius": result["safe_radius"],
        }, f, indent=2)

    print(f"\nUniform map : {_short(map_path)}")
    print(f"Result JSON : {_short(json_path)}")
