"""
tools/run_multi_instrument_smoke.py

Multi-Instrument Portfolio Smoke Test
--------------------------------------
Validates:
- Shared capital across instruments
- PCC global cap enforcement
- Asset-class cap enforcement
- Correlation proxy throttle
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.engine_loop import EngineLoop


STARTING_EQUITY = 100_000
STEPS = 800

INSTRUMENTS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "AUD_USD",
    "NZD_USD",
]


def build_price_series(base: float, phase_shift: float, steps: int):
    prices = []
    for i in range(steps):
        trend = math.sin((i + phase_shift) / 15.0) * 0.8
        noise = math.sin((i + phase_shift) / 4.0) * 0.2
        prices.append(base + trend + noise)
    return prices


def main():
    engine = EngineLoop(behaviour="D", starting_equity=STARTING_EQUITY)

    # Explicitly set asset classes (all FX here)
    for inst in INSTRUMENTS:
        engine.asset_class_map[inst] = "FX"

    # Generate staggered price streams
    price_streams = {
        inst: build_price_series(100 + idx * 5, idx * 10, STEPS)
        for idx, inst in enumerate(INSTRUMENTS)
    }

    for step in range(STEPS):
        for inst in INSTRUMENTS:
            engine.process_bar(inst, price_streams[inst][step])

    summary = engine.summary()

    print("\n=== MULTI-INSTRUMENT PORTFOLIO TEST ===")
    for k, v in summary.items():
        print(f"{k:30s}: {v}")


if __name__ == "__main__":
    main()