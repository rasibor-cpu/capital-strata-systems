"""
tools/run_phase1_portfolio_replay_dev_slice.py

Phase 1 Portfolio Replay – DEV SLICE MODE
------------------------------------------
Goal:
- Provide a fast iteration runner while your full-year portfolio replay is heavy.
- Supports:
  --start YYYY-MM-DD
  --end   YYYY-MM-DD
  --max_ts N
  --instruments "EUR_USD,GBP_USD,..."

Important:
- This file is a thin wrapper that calls into your existing V5 convexity trim runner:
  tools/run_phase1_portfolio_replay_v5_convexity_trim.py

- It assumes that runner exposes a callable `run_replay(...)` that accepts:
    start, end, max_timestamps, instruments, telemetry_class

If your V5 runner currently does NOT expose `run_replay`, tell me what functions
exist at the top-level (e.g., main(), run(), etc.) and I’ll send a new wrapper file
that targets what you actually have — still with no patching.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.replay._telemetry import ReplayTelemetry

# ✅ Confirmed file name from your screenshot:
from tools.run_phase1_portfolio_replay_v5_convexity_trim import run_replay


def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    # Accept YYYY-MM-DD only (date), treat as midnight local
    return datetime.fromisoformat(s)


def _parse_instruments(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    items = [x.strip() for x in s.split(",") if x.strip()]
    return items or None


def parse_args():
    p = argparse.ArgumentParser(
        prog="run_phase1_portfolio_replay_dev_slice",
        description="Phase 1 Portfolio Replay (DEV slice runner)",
    )

    p.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    p.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    p.add_argument("--max_ts", type=int, default=None, help="Max timestamps to process")
    p.add_argument("--instruments", type=str, default=None, help="Comma-separated instruments")

    return p.parse_args()


def main():
    args = parse_args()

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    instruments = _parse_instruments(args.instruments)
    max_ts = args.max_ts

    print("==== DEV SLICE PORTFOLIO REPLAY (WRAPPER) ====")
    print(f"Runner: tools/run_phase1_portfolio_replay_v5_convexity_trim.py")
    print(f"Start: {start}")
    print(f"End: {end}")
    print(f"Max TS: {max_ts}")
    print(f"Instruments: {instruments}")
    print("---------------------------------------------")

    # Call the V5 engine with telemetry enabled
    run_replay(
        start=start,
        end=end,
        max_timestamps=max_ts,
        instruments=instruments,
        telemetry_class=ReplayTelemetry,
    )


if __name__ == "__main__":
    main()