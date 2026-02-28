"""
run_eod_batch.py
Capital Strata Systems (CSS)

Phase 22D — EOD Lifecycle Integration

EOD Execution Order:
1. Run Daily Accrual Engine (idempotent)
2. Generate ledger snapshot
3. Generate trial balance
4. Generate audit logs
5. Close batch
"""

from __future__ import annotations

from datetime import date
import sys


def main():

    today = date.today()
    print("======================================")
    print("CSS END-OF-DAY BATCH RUN")
    print(f"Processing Date: {today}")
    print("======================================\n")

    # ----------------------------------------------------
    # 1️⃣ DAILY ACCRUAL ENGINE
    # ----------------------------------------------------
    print("Running Daily Accrual Engine...")

    from engine.facility.accrual_engine import run_daily_accrual

    accrual_result = run_daily_accrual(today)

    print("Accrual Summary:")
    print(f"  Facilities Processed : {accrual_result['facilities_processed']}")
    print(f"  Accruals Posted      : {accrual_result['accruals_posted']}")
    print(f"  Total Interest Accrued : {accrual_result['total_interest_accrued']}\n")

    # ----------------------------------------------------
    # 2️⃣ LEDGER SNAPSHOT
    # ----------------------------------------------------
    print("Generating Ledger Snapshot...")

    from engine.reporting.snapshot_engine import generate_eod_snapshot

    generate_eod_snapshot(today)

    print("Ledger Snapshot Completed.\n")

    # ----------------------------------------------------
    # 3️⃣ TRIAL BALANCE
    # ----------------------------------------------------
    print("Generating Trial Balance...")

    from engine.reporting.trial_balance_engine import generate_trial_balance

    generate_trial_balance(today)

    print("Trial Balance Completed.\n")

    # ----------------------------------------------------
    # 4️⃣ AUDIT CONFIRMATION
    # ----------------------------------------------------
    print("EOD Batch Completed Successfully.")
    print("======================================\n")


if __name__ == "__main__":
    main()