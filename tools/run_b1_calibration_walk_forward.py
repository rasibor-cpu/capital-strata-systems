#!/usr/bin/env python3
"""Run B1 walk-forward calibration on a replay CSV (paper/research only).

Usage:
  PYTHONPATH=. python tools/run_b1_calibration_walk_forward.py \\
    --csv path/to/bars.csv --instrument EUR/USD --out artifacts/trading_profiles/calibration
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.trading_profiles.calibration_walk_forward import run_and_persist
from backend.trading_profiles.market_bar_source import ReplayCsvBarSource


def main() -> int:
    parser = argparse.ArgumentParser(description="CSS-118 B1 walk-forward calibration (paper only)")
    parser.add_argument("--csv", required=True, help="Replay OHLC CSV path")
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--out", default="artifacts/trading_profiles/calibration")
    parser.add_argument("--train-frac", type=float, default=0.6)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bars = ReplayCsvBarSource(args.csv, instrument=args.instrument).load()
    result = run_and_persist(
        bars,
        artifact_path=out / "engine_loop_ma_momentum_v1.json",
        enablement_root=out,
        train_frac=args.train_frac,
    )
    print(
        json.dumps(
            {
                "approved": result.approved,
                "disable_reason": result.disable_reason,
                "oos_metrics": result.oos_metrics,
                "artifact": str(out / "engine_loop_ma_momentum_v1.json"),
                "paper_only": True,
                "live_trading_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.approved else 2


if __name__ == "__main__":
    raise SystemExit(main())
