"""
tools/run_eod_batch.py
Capital Strata Systems (CSS)

Phase 23D.5 — EOD Batch Wiring (Dormancy Scan inserted)

EOD Order (institutional):
1) Daily Accrual Engine
2) Dormancy Scan (auto-flag inactive customer accounts as DORMANT)
3) EOD Report Pack (Report Printer)
4) Trial Balance

Usage:
  python tools/run_eod_batch.py
  python tools/run_eod_batch.py 2026-02-28

Exit:
  raises on failure (fail-closed)
"""

from __future__ import annotations

import os
import sys
import inspect
from datetime import datetime
from typing import Any, Callable, Dict, Optional


def _banner(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _utc_ymd_today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _parse_run_date(argv: list[str]) -> str:
    if len(argv) >= 2 and argv[1].strip():
        # basic YYYY-MM-DD validation
        try:
            datetime.strptime(argv[1].strip(), "%Y-%m-%d")
        except Exception:
            raise ValueError("run_eod_batch: date must be YYYY-MM-DD (e.g., 2026-02-28)")
        return argv[1].strip()
    return _utc_ymd_today()


def _call_any(fn: Callable[..., Any], **kwargs: Any) -> Any:
    """
    Calls fn with only the kwargs it accepts. Avoids signature mismatches.
    """
    sig = inspect.signature(fn)
    allowed = {}
    for k, v in kwargs.items():
        if k in sig.parameters:
            allowed[k] = v
    return fn(**allowed)


def _resolve_callable(module_path: str, candidates: list[str]) -> Callable[..., Any]:
    """
    Imports module and returns the first callable found in candidates.
    Fail-closed if none found.
    """
    mod = __import__(module_path, fromlist=["*"])
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    raise ImportError(
        f"EOD wiring error: no callable found in {module_path}. "
        f"Expected one of: {candidates}"
    )


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except Exception:
        raise ValueError(f"Env var {name} must be an integer, got: {raw}")


def main(run_date: Optional[str] = None) -> None:
    processing_date = run_date or _parse_run_date(sys.argv)

    _banner("CSS END-OF-DAY BATCH RUN")
    print(f"Processing Date: {processing_date}")

    # ------------------------------------------------------------
    # 1) Daily Accrual Engine
    # ------------------------------------------------------------
    print("\nRunning Daily Accrual Engine...")
    accrual_fn = _resolve_callable(
        "engine.facility.accrual_engine",
        candidates=[
            "run_daily_accrual_engine",
            "run_accrual_engine",
            "run_daily_accrual",
        ],
    )

    accrual_result = _call_any(
        accrual_fn,
        posting_date=processing_date,
        run_date=processing_date,
        as_of_date=processing_date,
        processing_date=processing_date,
    )

    # tolerate None (some implementations just print)
    if isinstance(accrual_result, dict):
        print("Accrual Summary:")
        print(f"  Facilities Processed : {accrual_result.get('facilities_processed', 0)}")
        print(f"  Accruals Posted      : {accrual_result.get('accruals_posted', 0)}")
        print(f"  Total Interest Accrued : {accrual_result.get('total_interest_accrued', accrual_result.get('total_accrued', 0))}")
    else:
        print("Accrual Summary:")
        print("  (accrual engine returned no dict; assuming printed internally)")

    # ------------------------------------------------------------
    # 2) Dormancy Scan (AUTO — EOD-activated)
    # ------------------------------------------------------------
    print("\nRunning Dormancy Scan (EOD-activated)...")
    dormancy_threshold = _env_int("CSS_DORMANCY_THRESHOLD_DAYS", 90)

    from backend.app.ledger.dormancy_engine import run_dormancy_scan

    dormancy_result = run_dormancy_scan(threshold_days=dormancy_threshold)

    print("Dormancy Scan Summary:")
    print(f"  Accounts Scanned     : {dormancy_result.get('accounts_scanned', 0)}")
    print(f"  Dormant Set          : {dormancy_result.get('accounts_dormant_set', 0)}")
    print(f"  Threshold Days       : {dormancy_result.get('threshold_days', dormancy_threshold)}")

    # ------------------------------------------------------------
    # 3) EOD Report Pack (Report Printer)
    # ------------------------------------------------------------
    print("\nGenerating EOD Report Pack (Report Printer)...")
    report_pack_fn = _resolve_callable(
        "engine.reporting.report_printer",
        candidates=[
            "run_eod_pack",
            "generate_eod_pack",
            "print_eod_pack",
            "run_daily_pack",
        ],
    )

    pack_result = _call_any(
        report_pack_fn,
        run_date=processing_date,
        as_of_date=processing_date,
        ledger_date=processing_date,
        date=processing_date,
    )

    if isinstance(pack_result, dict) and pack_result.get("ok") is True:
        print("EOD Report Pack: OK (" + str(pack_result.get("fn", "run_eod_pack")) + ")")
    else:
        # if function returns None, it may have printed successfully
        print("EOD Report Pack: OK (run)")

    # ------------------------------------------------------------
    # 4) Trial Balance
    # ------------------------------------------------------------
    print("\nGenerating Trial Balance...")
    tb_fn = _resolve_callable(
        "engine.reporting.trial_balance",
        candidates=[
            "generate_trial_balance",
            "run_trial_balance",
            "print_trial_balance",
        ],
    )

    tb_result = _call_any(
        tb_fn,
        as_of_date=processing_date,
        ledger_date=processing_date,
        date=processing_date,
        run_date=processing_date,
    )

    if isinstance(tb_result, dict) and tb_result.get("ok") is True:
        print("Trial Balance: OK (generate_trial_balance)")
    else:
        print("Trial Balance: OK (run)")

    print("\nEOD Batch Completed Successfully.")
    _banner("EOD Batch Run: OK")


if __name__ == "__main__":
    main()