"""
run_export_eod.py — REA Capital Trading Engine
---------------------------------------------
Single-command runner for Daily End-of-Day (EOD) export pack.

Usage:
    python run_export_eod.py --as_of YYYY-MM-DD

Behavior:
- Loads batch close engine
- Executes EOD batch close (read-only aggregation)
- Exports CSV report pack via ReportExports
- Prints output folder
"""

import argparse
from datetime import date, datetime
import sys

# Core engines
from batch_close import BatchCloseEngine
from report_exports import ReportExports


def parse_args() -> date:
    parser = argparse.ArgumentParser(description="Run EOD export pack")
    parser.add_argument(
        "--as_of",
        required=True,
        help="Business date for EOD export (YYYY-MM-DD)",
    )
    args = parser.parse_args()
    try:
        return date.fromisoformat(args.as_of)
    except ValueError:
        print("ERROR: --as_of must be in YYYY-MM-DD format", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    as_of = parse_args()

    print(f"=== REA EOD EXPORT RUNNER ===")
    print(f"As-of date: {as_of.isoformat()}")

    # Initialize batch engine (no writes)
    batch = BatchCloseEngine()

    # Run batch close (aggregations + validations already wired)
    batch.run_eod(as_of)

    # Export reports
    exporter = ReportExports(batch)
    folder = exporter.export_eod_pack(as_of)

    print(f"EOD export completed successfully.")
    print(f"Reports written to: {folder}")


if __name__ == "__main__":
    main()
