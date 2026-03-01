"""
tools/run_eod_batch.py
Capital Strata Systems (CSS)

Phase 24 + Phase 23.3 — Governed EOD Batch Controller + Immutable EOD Pack

Order:
0) Duplicate-run guard
1) Accrual Engine
2) Dormancy Scan (EOD-activated)
3) Trial Balance
4) Immutable EOD Pack write + hash
5) Register completion
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _utc_ymd_today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _parse_run_date(argv: list[str]) -> str:
    # supports: python -m tools.run_eod_batch 2026-03-01
    if len(argv) >= 2 and argv[1].strip():
        try:
            datetime.strptime(argv[1].strip(), "%Y-%m-%d")
        except Exception:
            raise ValueError("run_eod_batch: date must be YYYY-MM-DD")
        return argv[1].strip()
    return _utc_ymd_today()


def main(run_date: Optional[str] = None) -> None:
    processing_date = run_date or _parse_run_date(sys.argv)

    _banner("CSS END-OF-DAY BATCH RUN")
    print(f"Processing Date: {processing_date}")

    # ------------------------------------------------------------
    # 0) DUPLICATE RUN GUARD
    # ------------------------------------------------------------
    from engine.batch.batch_registry import (
        assert_eod_not_already_run,
        register_eod_success,
    )

    print("\nValidating duplicate-run guard...")
    assert_eod_not_already_run(processing_date)
    print("Duplicate-run check: OK")

    # ------------------------------------------------------------
    # 1) Daily Accrual Engine
    # ------------------------------------------------------------
    print("\nRunning Daily Accrual Engine...")
    from engine.facility.accrual_engine import startup_accrual_check

    accrual_result = startup_accrual_check()

    print("Accrual Summary:")
    print(f"  Posting Date         : {accrual_result.get('posting_date')}")
    print(f"  Facilities Processed : {accrual_result.get('facilities_processed')}")
    print(f"  Accruals Posted      : {accrual_result.get('accruals_posted')}")
    print(f"  Total Accrued        : {accrual_result.get('total_interest_accrued')}")

    # ------------------------------------------------------------
    # 2) Dormancy Scan (EOD-activated)
    # ------------------------------------------------------------
    print("\nRunning Dormancy Scan (EOD-activated)...")
    from backend.app.ledger.dormancy_engine import run_dormancy_scan

    dormancy_result = run_dormancy_scan(threshold_days=90)

    print("Dormancy Summary:")
    print(f"  Accounts Scanned     : {dormancy_result.get('accounts_scanned')}")
    print(f"  Dormant Set          : {dormancy_result.get('accounts_dormant_set')}")
    print(f"  Threshold Days       : {dormancy_result.get('threshold_days')}")

    # ------------------------------------------------------------
    # 3) Trial Balance
    # ------------------------------------------------------------
    print("\nGenerating Trial Balance...")
    from engine.reporting.trial_balance import generate_trial_balance

    tb_result = generate_trial_balance(as_of_date=processing_date)
    print("Trial Balance: OK")

    # ------------------------------------------------------------
    # 4) Immutable EOD Pack (audit retrieval)
    # ------------------------------------------------------------
    print("\nGenerating Immutable EOD Pack (snapshot + hashes)...")
    from engine.reporting.report_printer import generate_eod_pack

    pack_result = generate_eod_pack(
        run_date=processing_date,
        trial_balance=tb_result,
        dormancy_summary=dormancy_result,
        accrual_summary=accrual_result,
    )

    if not pack_result.get("ok"):
        raise RuntimeError("EOD Pack generation failed (fail-closed).")

    print("EOD Pack: OK")
    print(f"  Files Written : {pack_result.get('files_written')}")
    print(f"  Pack Hash     : {pack_result.get('pack_hash')}")

    # ------------------------------------------------------------
    # 5) REGISTER SUCCESS
    # ------------------------------------------------------------
    register_eod_success(processing_date)

    print("\nEOD Batch Completed Successfully.")
    _banner("EOD Batch Run: OK")


if __name__ == "__main__":
    main()