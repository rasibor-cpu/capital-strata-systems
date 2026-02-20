"""
engine/run_engine_100.py

Configurable Institutional Simulation Runner
Capital Strata Systems (CSS)

Default: 200 steps (multi-week allocator validation)

Usage:
    python -u engine\\run_engine_100.py
    python -u engine\\run_engine_100.py 300
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable (so we can import root-level engine_loop.py)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine_loop import EngineLoop  # root-level file: C:\\rasib\\source\\capital-strata-systems\\engine_loop.py

DEFAULT_STEPS = 200


def main() -> int:
    steps = DEFAULT_STEPS

    if len(sys.argv) > 1:
        try:
            steps = int(sys.argv[1])
        except Exception:
            print("[runner] Invalid steps arg; using default:", DEFAULT_STEPS)
            steps = DEFAULT_STEPS

    print(f"==== INSTITUTIONAL SIMULATION ({steps} steps) ====")

    loop = EngineLoop()
    loop.run(steps=steps)

    print("\n==== SIMULATION COMPLETE ====")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
