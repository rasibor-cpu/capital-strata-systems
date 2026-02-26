"""
tools/run_engine_smoke_portfolio.py

Portfolio-Governed Smoke Test
--------------------------------
Validates:
- EngineLoop + PCC integration
- PositionBook lifecycle
- PnLTracker stability
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Ensure repo root on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


INSTRUMENT = "EUR_USD"
STARTING_EQUITY = 100_000
STEPS = 800


def build_prices(steps: int) -> list[float]:
    base = 100.0
    prices = []
    for i in range(steps):
        # controlled oscillation
        trend = math.sin(i / 15.0) * 0.8
        noise = math.sin(i / 3.0) * 0.2
        prices.append(base + trend + noise)
    return prices


def main():
    engine = EngineLoop(behaviour="D", starting_equity=STARTING_EQUITY)

    prices = build_prices(STEPS)

    for p in prices:
        engine.process_bar(INSTRUMENT, p)

    summary = engine.summary()

    print("\n=== PORTFOLIO GOVERNED SMOKE TEST ===")
    for k, v in summary.items():
        print(f"{k:25s}: {v}")


if __name__ == "__main__":
    main()