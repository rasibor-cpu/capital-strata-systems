"""
run_lifecycle_smoke.py
Capital Strata Systems (CSS)

Phase 22E — Lifecycle Smoke Test (Single Command)

What this verifies:
1) Startup safety checks (Daily Accrual idempotent hook)
2) EOD batch end-to-end run

Usage:
  python tools/run_lifecycle_smoke.py

Exit Codes:
  0 = PASS
  1 = FAIL
"""

from __future__ import annotations

import sys
from datetime import datetime


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main() -> int:
    _banner("CSS LIFECYCLE SMOKE TEST — Phase 22E")
    print(f"UTC Timestamp: {datetime.utcnow().isoformat()}Z")

    # ------------------------------------------------------------
    # 1) Startup Safety Check (simulate what FastAPI startup does)
    # ------------------------------------------------------------
    _banner("1) STARTUP SAFETY CHECKS (SIMULATED)")
    try:
        from engine.facility.accrual_engine import startup_accrual_check

        result = startup_accrual_check()
        print("Startup Accrual Safety Check: OK")
        print(f"  Posting Date         : {result.get('posting_date')}")
        print(f"  Facilities Processed : {result.get('facilities_processed')}")
        print(f"  Accruals Posted      : {result.get('accruals_posted')}")
        print(f"  Total Accrued        : {result.get('total_interest_accrued')}")
    except Exception as exc:
        print("Startup Accrual Safety Check: FAILED")
        print(f"Error: {str(exc)}")
        return 1

    # ------------------------------------------------------------
    # 2) EOD Batch Run (end-to-end)
    # ------------------------------------------------------------
    _banner("2) EOD BATCH RUN")
    try:
        # tools/run_eod_batch.py has a `main()` we can call directly
        from tools.run_eod_batch import main as run_eod

        run_eod()
        print("EOD Batch Run: OK")
    except Exception as exc:
        print("EOD Batch Run: FAILED")
        print(f"Error: {str(exc)}")
        return 1

    _banner("RESULT: PASS ✅")
    return 0


if __name__ == "__main__":
    code = main()
    sys.exit(code)