"""Testing ground for Megagem bots. Puts the harness and this repo on sys.path."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS_SRC = ROOT / "harness" / "src"
if not HARNESS_SRC.is_dir():
    raise SystemExit("Harness not found. Run scripts/setup_harness.sh first.")
for path in (str(HARNESS_SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
