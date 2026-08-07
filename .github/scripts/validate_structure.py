"""
Parse <<< FOLDER NAME >>> and <<< IMPORT >>> markers from source files.
Check that referenced folders/modules still exist on disk.
Run this after any file/folder reorganization.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent  # project root

FOLDER_MARKER = re.compile(r'"([^"]+)"\s*#\s*<<<\s*FOLDER NAME\s*>>>')
IMPORT_MARKER = re.compile(r'import\s+(\S+?)(?:\s+as\s+\S+)?\s*#\s*<<<\s*IMPORT\s*>>>')

# Modules not committed to repo (e.g. contain API keys) — skip existence check
OPTIONAL_IMPORTS = {"activeLearning_29"}

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules"}

errors = []
checked = 0

# scan all .py files recursively, skipping excluded dirs
source_files = [
    p for p in ROOT.rglob("*.py")
    if not any(part in EXCLUDE_DIRS for part in p.parts)
]

for src in source_files:
    try:
        content = src.read_text(errors="ignore")
    except Exception:
        continue

    for match in FOLDER_MARKER.finditer(content):
        folder_name = match.group(1)
        checked += 1
        # check relative to project root, one level deep, then anywhere under root
        # (handles folders nested further, e.g. data/raw/fake-data)
        candidates = [ROOT / folder_name] + list(ROOT.glob(f"*/{folder_name}"))
        found = any(p.is_dir() for p in candidates)
        if not found:
            found = any(p.is_dir() for p in ROOT.rglob(folder_name))
        if not found:
            errors.append(f"{src.name}: folder '{folder_name}' not found under project root")
        else:
            print(f"Test {checked} passed: '{folder_name}' found at {src.name}")

    for match in IMPORT_MARKER.finditer(content):
        module = match.group(1)
        if module in OPTIONAL_IMPORTS:
            continue
        checked += 1
        # check same dir, parent dir, and anywhere under ROOT (handles scripts whose
        # sys.path.insert points at a specific subfolder like src/pipeline, not just parent)
        candidates = [src.parent / f"{module}.py", src.parent.parent / f"{module}.py"]
        found = next((p for p in candidates if p.exists()), None)
        if found is None:
            matches = list(ROOT.rglob(f"{module}.py"))
            found = matches[0] if matches else None
        if found is None:
            errors.append(f"{src.name}: import '{module}' not found in {src.parent}, {src.parent.parent}, or anywhere under {ROOT}")
        else:
            print(f"Test {checked} passed: '{module}' found at {found.parent}")

if errors:
    print(f"FAIL structure validation ({len(errors)} error(s)):")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print(f"PASS {checked} structure references valid")
