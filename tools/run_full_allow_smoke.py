"""
tools/run_full_allow_smoke.py

FULL ALLOW SMOKE (Laptop-1)
---------------------------
- Uses EngineLoop(instrument, price) via process_bar()
- Prints engine.summary() at the end
- Synthetic price path: trend -> reversal -> recovery
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


INSTRUMENT = "EURUSD"
STARTING_EQUITY = 100_000
STEPS = 800


def build_prices(steps: int) -> list[float]:
    base = 100.0
    out = []
    for i in range(steps):
        if i < steps * 0.35:
            drift = 0.020
        elif i < steps * 0.65:
            drift = -0.030
        else:
            drift = 0.015

        wave = 0.25 * math.sin(i / 7.0)
        micro = 0.05 * math.sin(i / 2.5)
        base += drift + wave + micro
        out.append(base)
    return out


def main() -> None:
    print("\n=== FULL ALLOW SMOKE TEST START ===")
    print(f"Repo root: {REPO_ROOT}")
    print(f"Steps: {STEPS} | Instrument: {INSTRUMENT}")
    print(f"Starting equity: {STARTING_EQUITY}")

    engine = EngineLoop(behaviour="D", starting_equity=float(STARTING_EQUITY))

    prices = build_prices(STEPS)
    for p in prices:
        engine.process_bar(INSTRUMENT, float(p))

    print("\n=== SUMMARY ===")
    print(engine.summary())
    print("=== END ===\n")


if __name__ == "__main__":
    main()