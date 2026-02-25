"""
tools/run_phase1_portfolio_replay_dev_slice.py

Phase 1 Portfolio Replay – DEV SLICE MODE
------------------------------------------
Purpose:
- Fast iteration runner
- Supports date slicing
- Supports instrument subset
- Supports max timestamp cap
- Uses ReplayTelemetry

This is for parameter tuning.
Full-year production replay remains separate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.replay._telemetry import ReplayTelemetry

# ⚠ Replace this import with your real loader + engine entrypoint
# These should match your existing portfolio replay structure
from tools.run_phase1_portfolio_replay_v5_convexity_trim import run_replay


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--start", type=str, default=None,
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None,
                        help="End date YYYY-MM-DD")
    parser.add_argument("--max_ts", type=int, default=None,
                        help="Maximum timestamps to process")
    parser.add_argument("--instruments", type=str, default=None,
                        help="Comma separated instrument list")

    return parser.parse_args()


def main():
    args = parse_args()

    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None

    instruments = None
    if args.instruments:
        instruments = [x.strip() for x in args.instruments.split(",")]

    print("==== DEV SLICE PORTFOLIO REPLAY ====")
    print(f"Start: {start}")
    print(f"End: {end}")
    print(f"Max TS: {args.max_ts}")
    print(f"Instruments: {instruments}")
    print("------------------------------------")

    # You must adapt run_replay signature if needed
    run_replay(
        start=start,
        end=end,
        max_timestamps=args.max_ts,
        instruments=instruments,
        telemetry_class=ReplayTelemetry,
    )


if __name__ == "__main__":
    main()