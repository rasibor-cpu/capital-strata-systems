"""
Report Printer – Phase 1 Hardened (Lazy Import / Fail-Closed)
Capital Strata Systems

Goal:
- Central dispatch for printable reports
- Do NOT allow one broken report module to crash the reporting gateway
- Fail-closed with explicit, audit-friendly errors
- Supports COA-complete Trial Balance + interbranch visibility (Phase 1)
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import importlib


# ==========================================================
# Report Registry (names exposed to gateway/screens)
# ==========================================================

REGISTERED_REPORTS = {
    # General Ledger
    "gl_print",
    "gl_as_of",

    # Trial Balance
    "trial_balance",

    # Subledgers / AR
    "customer_subledger",
    "ar_ageing",

    # Packs / controls
    "supervisory_control_pack",
    "supervisor_signoff",

    # Treasury / PnL
    "treasury_instrument_aggregate",
    "pnl_report",
}


def list_reports() -> List[str]:
    return sorted(REGISTERED_REPORTS)


# ==========================================================
# Internal Helpers
# ==========================================================

def _import(module_path: str) -> Any:
    """
    Lazy import with clean error message (fail-closed).
    """
    try:
        return importlib.import_module(module_path)
    except Exception as e:
        raise ModuleNotFoundError(
            f"Report module import failed: {module_path}. "
            f"Underlying error: {type(e).__name__}: {e}"
        ) from e


def _call_first(module: Any, candidate_names: List[str], **kwargs: Any) -> Dict[str, Any]:
    """
    Calls the first callable entrypoint found on a module.
    If a candidate doesn't accept some kwargs, we retry without those kwargs (soft-compat).
    """
    last_type_error: Optional[TypeError] = None

    for name in candidate_names:
        fn = getattr(module, name, None)
        if not callable(fn):
            continue

        try:
            return fn(**kwargs)
        except TypeError as te:
            # Soft-compat: remove common unused kwargs and retry once
            last_type_error = te
            pruned = dict(kwargs)

            # commonly incompatible keys across report modules
            for k in ("role", "sections"):
                pruned.pop(k, None)

            try:
                return fn(**pruned)
            except TypeError:
                # keep trying other candidates
                continue

    if last_type_error is not None:
        raise last_type_error

    raise AttributeError(f"{module.__name__} missing entrypoint. Tried: {candidate_names}")


# ==========================================================
# Public API
# ==========================================================

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

    # ------------------------------------------------------
    # Trial Balance (engine/reporting/trial_balance.py)
    # ------------------------------------------------------
    if report_name == "trial_balance":
        mod = _import("engine.reporting.trial_balance")
        return _call_first(mod, ["generate_trial_balance"])

    # ------------------------------------------------------
    # General Ledger (engine/reporting/gl_ledger.py)
    # ------------------------------------------------------
    if report_name in {"gl_print", "gl_as_of"}:
        # Fail cleanly if GL module not yet present
        try:
            mod = _import("engine.reporting.gl_ledger")
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                f"GL report '{report_name}' not wired yet (missing engine.reporting.gl_ledger). "
                f"Create engine/reporting/gl_ledger.py or update dispatch. Details: {e}"
            ) from e

        if report_name == "gl_print":
            return _call_first(
                mod,
                ["generate_gl_print", "print_gl_range", "generate_gl_range"],
                from_date=from_date,
                to_date=to_date,
                role=role,
                filters=filters,
            )

        return _call_first(
            mod,
            ["generate_gl_as_of", "print_gl_as_of", "generate_as_of"],
            as_of_date=as_of_date,
            role=role,
            filters=filters,
        )

    # ------------------------------------------------------
    # AR Ageing (engine/reporting/ageing_reports.py)
    # ------------------------------------------------------
    if report_name == "ar_ageing":
        mod = _import("engine.reporting.ageing_reports")
        return _call_first(
            mod,
            ["generate_ar_ageing", "generate_ageing_ar", "generate_customer_ageing"],
            role=role,
            filters=filters,
        )

    # ------------------------------------------------------
    # Supervisory Control Pack (engine/reporting/supervisory_control_pack.py)
    # NOTE: this module currently exposes generate_scp_report(as_of_date, filters)
    # ------------------------------------------------------
    if report_name == "supervisory_control_pack":
        mod = _import("engine.reporting.supervisory_control_pack")
        return _call_first(
            mod,
            ["generate_scp_report", "generate_supervisory_control_pack", "build_supervisory_control_pack", "generate_report"],
            as_of_date=as_of_date,
            role=role,
            filters=filters,
            sections=sections,
        )

    # ------------------------------------------------------
    # Supervisor Sign-off (engine/reporting/supervisor_signoff.py)
    # ------------------------------------------------------
    if report_name == "supervisor_signoff":
        mod = _import("engine.reporting.supervisor_signoff")
        return _call_first(
            mod,
            ["generate_supervisor_signoff", "generate_signoff", "build_signoff"],
            as_of_date=as_of_date,
            role=role,
            filters=filters,
        )

    # ------------------------------------------------------
    # Treasury Instrument Aggregate (engine/reporting/treasury_instrument_aggregate.py)
    # ------------------------------------------------------
    if report_name == "treasury_instrument_aggregate":
        mod = _import("engine.reporting.treasury_instrument_aggregate")
        return _call_first(
            mod,
            ["generate_treasury_instrument_aggregate", "generate_treasury_aggregate", "generate_report"],
            as_of_date=as_of_date,
            role=role,
            filters=filters,
        )

    # ------------------------------------------------------
    # PnL Report (repo has engine/reporting/pnl_ledger.py)
    # ------------------------------------------------------
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

    # ------------------------------------------------------
    # Customer Subledger (engine/reporting/customer_subledger_report.py)
    # ------------------------------------------------------
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