"""
report_printer.py
Capital Strata Systems (CSS)

Phase 22D/22E Hardening — Stable EOD Report Pack API

Why this exists:
- EOD batch requires a single, stable entry point to generate all required EOD prints/snapshots.
- Over time, report modules evolve; this orchestrator must be robust to function-name drift.

Canonical API (DO NOT BREAK):
- run_eod_pack(run_date)

Also supported aliases:
- generate_eod_pack, print_eod_pack, run_daily_pack
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, Optional, Tuple


def _call_first_available(module, fn_names: Tuple[str, ...], *args, **kwargs) -> Dict[str, Any]:
    """
    Calls the first callable attribute found on module among fn_names.
    Returns a standardized result dict.
    """
    for name in fn_names:
        fn = getattr(module, name, None)
        if callable(fn):
            out = fn(*args, **kwargs)
            return {
                "ok": True,
                "module": getattr(module, "__name__", str(module)),
                "function": name,
                "result": out,
            }
    return {
        "ok": False,
        "module": getattr(module, "__name__", str(module)),
        "function": None,
        "result": None,
    }


def run_eod_pack(run_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Canonical EOD report pack runner.

    Runs a best-effort set of EOD outputs that exist in this repo:
    - approval queue snapshot
    - supervisory control pack
    - customer subledger report (if available)
    - ageing reports (if available)
    - pnl ledger / treasury aggregates (if available)

    This function MUST:
    - Not crash because ONE optional report is missing
    - Fail only if ALL reports fail (i.e., nothing was produced)
    """
    if run_date is None:
        run_date = date.today()

    results: Dict[str, Any] = {
        "ok": True,
        "run_date": run_date.isoformat(),
        "reports": [],
        "warnings": [],
    }

    # -----------------------------
    # 1) Approval Queue Snapshot (EOD-critical for follow-ups)
    # -----------------------------
    try:
        from engine.reporting import approval_queue_snapshot as aqs

        r = _call_first_available(
            aqs,
            ("build_approval_queue_snapshot", "run_approval_queue_snapshot", "generate_approval_queue_snapshot"),
            run_date,
        )
        results["reports"].append({"name": "approval_queue_snapshot", **r})
        if not r["ok"]:
            results["warnings"].append("approval_queue_snapshot: no known function found")
    except Exception as exc:
        results["reports"].append({"name": "approval_queue_snapshot", "ok": False, "error": str(exc)})
        results["warnings"].append(f"approval_queue_snapshot failed: {str(exc)}")

    # -----------------------------
    # 2) Supervisory Control Pack (EOD control evidence)
    # -----------------------------
    try:
        from engine.reporting import supervisory_control_pack as scp

        r = _call_first_available(
            scp,
            ("generate_supervisory_control_pack", "run_supervisory_control_pack", "print_supervisory_control_pack"),
            run_date,
        )
        results["reports"].append({"name": "supervisory_control_pack", **r})
        if not r["ok"]:
            results["warnings"].append("supervisory_control_pack: no known function found")
    except Exception as exc:
        results["reports"].append({"name": "supervisory_control_pack", "ok": False, "error": str(exc)})
        results["warnings"].append(f"supervisory_control_pack failed: {str(exc)}")

    # -----------------------------
    # 3) Customer Subledger Report (optional but desirable)
    # -----------------------------
    try:
        from engine.reporting import customer_subledger_report as csr

        r = _call_first_available(
            csr,
            ("generate_customer_subledger_report", "run_customer_subledger_report", "print_customer_subledger_report"),
            run_date,
        )
        results["reports"].append({"name": "customer_subledger_report", **r})
        if not r["ok"]:
            results["warnings"].append("customer_subledger_report: no known function found")
    except Exception as exc:
        # Optional — record warning only
        results["reports"].append({"name": "customer_subledger_report", "ok": False, "error": str(exc)})
        results["warnings"].append(f"customer_subledger_report skipped/failed: {str(exc)}")

    # -----------------------------
    # 4) Ageing Reports (optional)
    # -----------------------------
    try:
        from engine.reporting import ageing_reports as ar

        r = _call_first_available(
            ar,
            ("generate_ageing_reports", "run_ageing_reports", "print_ageing_reports"),
            run_date,
        )
        results["reports"].append({"name": "ageing_reports", **r})
        if not r["ok"]:
            results["warnings"].append("ageing_reports: no known function found")
    except Exception as exc:
        results["reports"].append({"name": "ageing_reports", "ok": False, "error": str(exc)})
        results["warnings"].append(f"ageing_reports skipped/failed: {str(exc)}")

    # -----------------------------
    # 5) PnL Ledger / Treasury Aggregates (optional)
    # -----------------------------
    try:
        from engine.reporting import pnl_ledger as pl

        r = _call_first_available(
            pl,
            ("generate_pnl_ledger", "run_pnl_ledger", "print_pnl_ledger"),
            run_date,
        )
        results["reports"].append({"name": "pnl_ledger", **r})
        if not r["ok"]:
            results["warnings"].append("pnl_ledger: no known function found")
    except Exception as exc:
        results["reports"].append({"name": "pnl_ledger", "ok": False, "error": str(exc)})
        results["warnings"].append(f"pnl_ledger skipped/failed: {str(exc)}")

    try:
        from engine.reporting import treasury_instrument_aggregate as tia

        r = _call_first_available(
            tia,
            ("generate_treasury_instrument_aggregate", "run_treasury_instrument_aggregate", "print_treasury_instrument_aggregate"),
            run_date,
        )
        results["reports"].append({"name": "treasury_instrument_aggregate", **r})
        if not r["ok"]:
            results["warnings"].append("treasury_instrument_aggregate: no known function found")
    except Exception as exc:
        results["reports"].append({"name": "treasury_instrument_aggregate", "ok": False, "error": str(exc)})
        results["warnings"].append(f"treasury_instrument_aggregate skipped/failed: {str(exc)}")

    # -----------------------------
    # Pass/Fail rule:
    # At least ONE report must succeed, otherwise fail.
    # -----------------------------
    any_ok = any(r.get("ok") is True for r in results["reports"])
    results["ok"] = bool(any_ok)
    if not any_ok:
        results["warnings"].append("EOD pack produced no successful reports.")

    return results


# Backward-compatible aliases (so callers can use any name)
def generate_eod_pack(run_date: Optional[date] = None) -> Dict[str, Any]:
    return run_eod_pack(run_date)


def print_eod_pack(run_date: Optional[date] = None) -> Dict[str, Any]:
    return run_eod_pack(run_date)


def run_daily_pack(run_date: Optional[date] = None) -> Dict[str, Any]:
    return run_eod_pack(run_date)