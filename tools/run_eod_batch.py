"""
run_eod_batch.py
Capital Strata Systems (CSS)

Phase 22D (Revised) — EOD Lifecycle Integration (Aligned to current reporting modules)

EOD Execution Order:
1) Run Daily Accrual Engine (idempotent)
2) Generate supervisory control pack / ledger print pack via report_printer
3) Generate Trial Balance (official)
4) (Optional later) Ageing reports, approval-queue snapshot, etc.
"""

from __future__ import annotations

from datetime import date
from typing import Optional


def main(run_date: Optional[date] = None) -> None:
    if run_date is None:
        run_date = date.today()

    print("======================================")
    print("CSS END-OF-DAY BATCH RUN")
    print(f"Processing Date: {run_date}")
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

    # Your existing report_printer module should own the authoritative printouts.
    # We support either function name: run_eod_pack / generate_eod_pack / print_eod_pack.
    from engine.reporting import report_printer as rp

    report_pack_ok = False
    for fn_name in ("run_eod_pack", "generate_eod_pack", "print_eod_pack", "run_daily_pack"):
        fn = getattr(rp, fn_name, None)
        if callable(fn):
            fn(run_date)  # standardize: pass date
            report_pack_ok = True
            print(f"EOD Report Pack: OK ({fn_name})\n")
            break

    if not report_pack_ok:
        raise RuntimeError(
            "EOD Report Pack failed: no callable function found in engine.reporting.report_printer "
            "(expected one of: run_eod_pack, generate_eod_pack, print_eod_pack, run_daily_pack)."
        )

    # ----------------------------------------------------
    # 3) TRIAL BALANCE (OFFICIAL)
    # ----------------------------------------------------
    print("Generating Trial Balance...")

    # trial_balance.py should contain the authoritative TB generator.
    # We support common names to avoid refactor churn.
    from engine.reporting import trial_balance as tb

    tb_ok = False
    for fn_name in ("generate_trial_balance", "run_trial_balance", "print_trial_balance"):
        fn = getattr(tb, fn_name, None)
        if callable(fn):
            fn(run_date)
            tb_ok = True
            print(f"Trial Balance: OK ({fn_name})\n")
            break

    if not tb_ok:
        raise RuntimeError(
            "Trial Balance failed: no callable function found in engine.reporting.trial_balance "
            "(expected one of: generate_trial_balance, run_trial_balance, print_trial_balance)."
        )

    # ----------------------------------------------------
    # DONE
    # ----------------------------------------------------
    print("EOD Batch Completed Successfully.")
    print("======================================\n")


if __name__ == "__main__":
    main()