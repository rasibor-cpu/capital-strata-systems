"""
Phase 177 — Canonical Financial Reporting API (advisory / read-only).

GET /api/financial-reporting/summary
Optional:
  GET /api/financial-reporting/income-statement
  GET /api/financial-reporting/balance-sheet
  GET /api/financial-reporting/cash-flow
  GET /api/financial-reporting/profitability-run-rate
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

from backend.financial_reporting.adapters import (
    contract_from_mission_control_state,
    summarize_package,
)
from backend.financial_reporting.engine import (
    CanonicalFinancialReportingEngine,
    empty_degraded_summary,
)


_BANNED_KEYS = ("password", "secret", "token", "api_key", "traceback", "stack", "credential")


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    for banned in _BANNED_KEYS:
        payload.pop(banned, None)
    return payload


def create_financial_reporting_router(
    *,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    """
    Expose advisory financial reporting summaries.

    Optional state_provider supplies Mission Control–shaped state for contract
    mapping. When omitted or failing, endpoints degrade safely (NOT_READY).
    """

    router = APIRouter(tags=["financial-reporting"])
    engine = CanonicalFinancialReportingEngine()

    def _package() -> dict[str, Any]:
        state: dict[str, Any] = {}
        if state_provider is not None:
            try:
                state = state_provider() or {}
            except Exception:
                state = {}
        if not isinstance(state, dict):
            state = {}
        contract = contract_from_mission_control_state(state)
        return engine.generate_financial_report_package(contract)

    @router.get("/api/financial-reporting/summary")
    def get_financial_reporting_summary() -> dict[str, Any]:
        try:
            package = _package()
            return _scrub(summarize_package(package))
        except Exception:
            return _scrub(dict(empty_degraded_summary()))

    @router.get("/api/financial-reporting/income-statement")
    def get_income_statement() -> dict[str, Any]:
        try:
            package = _package()
            body = package.get("income_statement") or {}
            return _scrub(
                {
                    "schema_version": package.get("schema_version"),
                    "income_statement": body,
                    "advisory_only": True,
                    "trading_impact": False,
                }
            )
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.canonical_financial_report.v1",
                    "income_statement": None,
                    "advisory_only": True,
                    "trading_impact": False,
                    "blockers": ["upstream_unavailable"],
                }
            )

    @router.get("/api/financial-reporting/balance-sheet")
    def get_balance_sheet() -> dict[str, Any]:
        try:
            package = _package()
            return _scrub(
                {
                    "schema_version": package.get("schema_version"),
                    "balance_sheet": package.get("balance_sheet"),
                    "advisory_only": True,
                    "trading_impact": False,
                }
            )
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.canonical_financial_report.v1",
                    "balance_sheet": None,
                    "advisory_only": True,
                    "trading_impact": False,
                    "blockers": ["upstream_unavailable"],
                }
            )

    @router.get("/api/financial-reporting/cash-flow")
    def get_cash_flow() -> dict[str, Any]:
        try:
            package = _package()
            return _scrub(
                {
                    "schema_version": package.get("schema_version"),
                    "cash_flow_statement": package.get("cash_flow_statement"),
                    "advisory_only": True,
                    "trading_impact": False,
                }
            )
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.canonical_financial_report.v1",
                    "cash_flow_statement": None,
                    "advisory_only": True,
                    "trading_impact": False,
                    "blockers": ["upstream_unavailable"],
                }
            )

    @router.get("/api/financial-reporting/profitability-run-rate")
    def get_profitability_run_rate() -> dict[str, Any]:
        try:
            package = _package()
            return _scrub(
                {
                    "schema_version": package.get("schema_version"),
                    "profitability_run_rate": package.get("profitability_run_rate"),
                    "advisory_only": True,
                    "trading_impact": False,
                }
            )
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.canonical_financial_report.v1",
                    "profitability_run_rate": {
                        "traffic_light": "NOT_AVAILABLE",
                        "confidence_status": "NOT_AVAILABLE",
                    },
                    "advisory_only": True,
                    "trading_impact": False,
                    "blockers": ["upstream_unavailable"],
                }
            )

    return router


__all__ = ["create_financial_reporting_router"]
