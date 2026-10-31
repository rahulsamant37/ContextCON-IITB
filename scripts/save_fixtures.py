"""Promote a live run's recorded responses into fixtures/raw so `REPLAY=1` can re-run it offline.
Usage: python scripts/save_fixtures.py <mission_id> [more mission ids]
Recorded files contain request bodies (filters) and provider responses only; the API key is never written."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dest = ROOT / "fixtures" / "raw"
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for mid in sys.argv[1:]:
        for f in sorted((ROOT / "out" / mid / "raw").glob("*.json")):
            shutil.copy2(f, dest / f.name)
            n += 1
    print(f"copied {n} files to {dest}")


if __name__ == "__main__":
    main()
