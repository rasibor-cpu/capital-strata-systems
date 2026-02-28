"""
Report Printer – Phase 17 Hardened (Lazy Import / Fail-Closed)
Capital Strata Systems
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import importlib
from engine.reporting.approval_queue_snapshot import build_approval_queue_snapshot


REGISTERED_REPORTS = {
    "gl_print",
    "gl_as_of",
    "customer_subledger",
    "ar_ageing",
    "supervisory_control_pack",
    "supervisor_signoff",
    "treasury_instrument_aggregate",
    "pnl_report",
}


def list_reports() -> List[str]:
    return sorted(REGISTERED_REPORTS)


def _call_first(module: Any, candidate_names: List[str], **kwargs: Any) -> Dict[str, Any]:
    for name in candidate_names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(**kwargs)
    raise AttributeError(f"{module.__name__} missing entrypoint. Tried: {candidate_names}")


def _import(module_path: str) -> Any:
    try:
        return importlib.import_module(module_path)
    except Exception as e:
        raise ModuleNotFoundError(
            f"Report module import failed: {module_path}. "
            f"Underlying error: {type(e).__name__}: {e}"
        ) from e


def print_report(
    report_name: str,
    role: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    as_of_date: Optional[str] = None,
    sections: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    if report_name not in REGISTERED_REPORTS:
        raise ValueError(f"Unknown report requested: {report_name}")

    filters = filters or {}
    sections = sections or []

    if report_name in {"gl_print", "gl_as_of"}:
        raise ModuleNotFoundError(
            f"GL report '{report_name}' not wired yet. "
            f"Your engine/reporting folder has no GL module (e.g., gl_ledger.py)."
        )

    if report_name == "ar_ageing":
        mod = _import("engine.reporting.ageing_reports")
        return _call_first(
            mod,
            ["generate_ar_ageing", "generate_ageing_ar", "generate_customer_ageing"],
            role=role,
            filters=filters,
        )

    # ✅ FIX: SCP entrypoint exists, but does NOT accept role=
    if report_name == "supervisory_control_pack":
        mod = _import("engine.reporting.supervisory_control_pack")

        # Prefer the confirmed function.
        fn = getattr(mod, "generate_scp_report", None)
        if callable(fn):
            # Provide only what SCP is likely to accept; do NOT pass role.
            # If SCP doesn't use filters/sections it can ignore them or we adjust next.
            try:
                return fn(as_of_date=as_of_date, filters=filters, sections=sections)
            except TypeError:
                # Minimal call fallback
                return fn(as_of_date=as_of_date)

        # Fallbacks (if you later rename)
        return _call_first(
            mod,
            ["generate_supervisory_control_pack", "build_supervisory_control_pack", "generate_report"],
            as_of_date=as_of_date,
            filters=filters,
            sections=sections,
        )

    if report_name == "supervisor_signoff":
        mod = _import("engine.reporting.supervisor_signoff")
        return _call_first(
            mod,
            ["generate_supervisor_signoff", "generate_signoff", "build_signoff", "generate_report"],
            as_of_date=as_of_date,
            role=role,
            filters=filters,
        )

    if report_name == "treasury_instrument_aggregate":
        mod = _import("engine.reporting.treasury_instrument_aggregate")
        return _call_first(
            mod,
            ["generate_treasury_instrument_aggregate", "generate_treasury_aggregate", "generate_report"],
            as_of_date=as_of_date,
            role=role,
            filters=filters,
        )

    if report_name == "pnl_report":
        mod = _import("engine.reporting.pnl_ledger")
        return _call_first(
            mod,
            ["generate_pnl_report", "generate_pnl", "generate_report"],
            from_date=from_date,
            to_date=to_date,
            as_of_date=as_of_date,
            role=role,
            filters=filters,
        )

    if report_name == "customer_subledger":
        customer_id = filters.get("customer_id")
        if not customer_id:
            raise ValueError("customer_subledger requires 'customer_id' in filters")

        mod = _import("engine.reporting.customer_subledger_report")
        return _call_first(
            mod,
            ["generate_customer_subledger", "generate_customer_ledger", "generate_subledger"],
            customer_id=customer_id,
            from_date=from_date,
            to_date=to_date,
        )

    raise RuntimeError(f"Unhandled report dispatch for: {report_name}")