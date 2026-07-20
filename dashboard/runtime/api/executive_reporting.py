"""
Phase 178 — Executive Financial Reporting API (advisory / read-only).

GET /api/executive-reporting/financial-summary
GET /api/executive-reporting/financial-report
GET /api/executive-reporting/financial-narrative
GET /api/executive-reporting/management-actions
POST /api/executive-reporting/generate  (artifact only; no source mutation)
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

from backend.executive_reporting.service import ExecutiveFinancialReportingService

_BANNED = ("password", "secret", "token", "api_key", "traceback", "stack", "credential")


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    for banned in _BANNED:
        payload.pop(banned, None)
    return payload


def create_executive_reporting_router(
    *,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["executive-reporting"])
    service = ExecutiveFinancialReportingService()

    def _state() -> dict[str, Any]:
        if state_provider is None:
            return {}
        try:
            state = state_provider() or {}
            return state if isinstance(state, dict) else {}
        except Exception:
            return {}

    @router.get("/api/executive-reporting/financial-summary")
    def get_financial_summary() -> dict[str, Any]:
        try:
            return _scrub(dict(service.financial_summary(_state())))
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.executive_financial_summary.v1",
                    "reporting_readiness": "NOT_READY",
                    "profitability_traffic_light": "NOT_AVAILABLE",
                    "advisory_only": True,
                    "trading_impact": False,
                    "financial_blockers": ["upstream_unavailable"],
                }
            )

    @router.get("/api/executive-reporting/financial-report")
    def get_financial_report() -> dict[str, Any]:
        try:
            return _scrub(service.to_json(service.generate_from_state(_state())))
        except Exception:
            return _scrub(service.to_json(service.degraded_package()))

    @router.get("/api/executive-reporting/financial-narrative")
    def get_financial_narrative() -> dict[str, Any]:
        try:
            return _scrub(dict(service.financial_narrative(_state())))
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.executive_financial_narrative.v1",
                    "sections": {"executive_conclusion": "Narrative unavailable."},
                    "advisory_only": True,
                    "trading_impact": False,
                }
            )

    @router.get("/api/executive-reporting/management-actions")
    def get_management_actions() -> dict[str, Any]:
        try:
            actions = service.management_actions(_state())
            return _scrub(
                {
                    "schema_version": "css.executive_management_actions.v1",
                    "actions": actions,
                    "advisory_only": True,
                    "trading_impact": False,
                    "executable": False,
                }
            )
        except Exception:
            return _scrub(
                {
                    "schema_version": "css.executive_management_actions.v1",
                    "actions": [],
                    "advisory_only": True,
                    "trading_impact": False,
                    "executable": False,
                    "blockers": ["upstream_unavailable"],
                }
            )

    @router.post("/api/executive-reporting/generate")
    def post_generate() -> dict[str, Any]:
        """Generate report artifact only — does not mutate financial source data."""
        try:
            package = service.generate_from_state(_state())
            return _scrub(
                {
                    "status": "OK",
                    "report_id": package.get("report_id"),
                    "package": service.to_json(package),
                    "html_available": True,
                    "advisory_only": True,
                    "trading_impact": False,
                    "source_data_mutated": False,
                }
            )
        except Exception:
            degraded = service.degraded_package()
            return _scrub(
                {
                    "status": "DEGRADED",
                    "report_id": degraded.get("report_id"),
                    "package": service.to_json(degraded),
                    "html_available": True,
                    "advisory_only": True,
                    "trading_impact": False,
                    "source_data_mutated": False,
                }
            )

    return router


__all__ = ["create_executive_reporting_router"]
