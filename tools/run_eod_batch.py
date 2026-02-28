"""
run_eod_batch.py
Capital Strata Systems (CSS)

Phase 22D (Aligned) — EOD Lifecycle Integration

EOD Execution Order:
1) Run Daily Accrual Engine (idempotent)
2) Generate EOD Report Pack (report_printer.run_eod_pack)
3) Generate Trial Balance (gateway-compatible kwarg: as_of_date)
"""

from __future__ import annotations

from datetime import date
from typing import Optional


def main(run_date: Optional[date] = None) -> None:
    if run_date is None:
        run_date = date.today()

    run_date_str = run_date.isoformat()

    print("======================================")
    print("CSS END-OF-DAY BATCH RUN")
    print(f"Processing Date: {run_date_str}")
    print("======================================\n")

    # ----------------------------------------------------
    # 1) DAILY ACCRUAL ENGINE
    # ----------------------------------------------------
    print("Running Daily Accrual Engine...")

    from engine.facility.accrual_engine import run_daily_accrual

    accrual_result = run_daily_accrual(run_date)

    print("Accrual Summary:")
    print(f"  Facilities Processed   : {accrual_result.get('facilities_processed')}")
    print(f"  Accruals Posted        : {accrual_result.get('accruals_posted')}")
    print(f"  Total Interest Accrued : {accrual_result.get('total_interest_accrued')}\n")

    # ----------------------------------------------------
    # 2) REPORT PACK / LEDGER PRINT PACK
    # ----------------------------------------------------
    print("Generating EOD Report Pack (Report Printer)...")

    from engine.reporting import report_printer as rp

    pack = rp.run_eod_pack(run_date)

    if not pack.get("ok"):
        raise RuntimeError(f"EOD Report Pack failed: {pack}")

    print("EOD Report Pack: OK (run_eod_pack)\n")

    # ----------------------------------------------------
    # 3) TRIAL BALANCE (OFFICIAL)
    # ----------------------------------------------------
    print("Generating Trial Balance...")

    from engine.reporting import trial_balance as tb

    # Gateway-compatible: must pass as_of_date= (keyword-only)
    tb_result = tb.generate_trial_balance(as_of_date=run_date_str)

    if not tb_result.get("ok"):
        raise RuntimeError(f"Trial Balance failed: {tb_result}")

    print("Trial Balance: OK (generate_trial_balance)\n")

    print("EOD Batch Completed Successfully.")
    print("======================================\n")


if __name__ == "__main__":
    main()