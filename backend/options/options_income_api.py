from __future__ import annotations

from typing import Any, Callable, Mapping

from backend.options.options_income_dashboard import fail_closed_dashboard
from backend.options.options_income_dashboard_payloads import DEFAULT_TIMESTAMP, envelope
from backend.options.paper_position_repository import SAFE_FLAGS


OPTIONS_INCOME_API_ROUTES = {
    "root": "/api/options-income",
    "status": "/api/options-income/status",
    "summary": "/api/options-income/summary",
    "opportunities": "/api/options-income/opportunities",
    "positions": "/api/options-income/positions",
    "rolls": "/api/options-income/rolls",
    "portfolio": "/api/options-income/portfolio",
    "greeks": "/api/options-income/greeks",
    "risk": "/api/options-income/risk",
    "stress_tests": "/api/options-income/stress-tests",
    "alerts": "/api/options-income/alerts",
    "explainability": "/api/options-income/explainability",
    "operational_status": "/api/options-income/operational-status",
    "report": "/api/options-income/report",
    "certification": "/api/options-income/certification",
}


class OptionsIncomeAPIError(ValueError):
    """Raised when an options-income API payload cannot be served safely."""


def build_options_income_api_payload(payload: Mapping[str, Any], section: str) -> dict[str, Any]:
    key = str(section or "").strip()
    if key not in OPTIONS_INCOME_API_ROUTES:
        return envelope("options_income_error", {"status": "FAIL_CLOSED", "reason": f"Unsupported section: {section}"})
    try:
        root = dict(payload)
        # Phase 177D runtime snapshot is a super-set; dashboard payloads remain paper-safe.
        if key in {"root", "status", "report", "certification"} or "schema_version" in root:
            return _runtime_section_payload(root, key)
        _assert_safe(root)
        data = root["summary"] if key == "summary" else root[key]
        return envelope(key, data, generated_at=str(root.get("generated_at", DEFAULT_TIMESTAMP)))
    except Exception as exc:
        return fail_closed_dashboard(reason=str(exc) or exc.__class__.__name__, generated_at=str(dict(payload).get("generated_at", DEFAULT_TIMESTAMP)))


def _runtime_section_payload(root: Mapping[str, Any], key: str) -> dict[str, Any]:
    generated = str(root.get("generated_at", DEFAULT_TIMESTAMP))
    if key == "root":
        return envelope("options_income", dict(root), generated_at=generated)
    if key == "status":
        return envelope(
            "status",
            {
                "status": root.get("status"),
                "engine_status": root.get("engine_status"),
                "deployment_state": root.get("deployment_state"),
                "certification": root.get("certification"),
                "operational_readiness": root.get("operational_readiness"),
                "missing_dependencies": root.get("missing_dependencies"),
                "execution_authority": root.get("execution_authority", "BLOCKED"),
                "advisory_only": True,
                "state_hash": root.get("state_hash"),
            },
            generated_at=generated,
        )
    if key == "certification":
        cert = root.get("certification") if isinstance(root.get("certification"), Mapping) else {}
        return envelope("certification", dict(cert), generated_at=generated)
    if key == "report":
        from backend.options.options_income_reporting import build_options_income_executive_report

        report = build_options_income_executive_report(snapshot=root)
        # Strip bulky HTML from JSON envelope default; clients may request separately
        slim = {k: v for k, v in report.items() if k != "html"}
        slim["html_available"] = True
        slim["page_count"] = (report.get("document") or {}).get("page_count")
        return envelope("report", slim, generated_at=generated)
    # Map opportunity/dashboard sections from runtime snapshot.dashboard when present
    dashboard = root.get("dashboard") if isinstance(root.get("dashboard"), Mapping) else root
    if key == "summary":
        data = dashboard.get("summary") if isinstance(dashboard, Mapping) else root.get("summary")
    elif key == "opportunities":
        data = {
            "accepted_candidates": root.get("accepted_candidates") or [],
            "rejected_candidates": root.get("rejected_candidates") or [],
            "covered_calls": root.get("covered_calls") or [],
            "cash_secured_puts": root.get("cash_secured_puts") or [],
            "opportunity_count": root.get("opportunity_count"),
            "status": root.get("engine_status"),
            "missing_dependencies": root.get("missing_dependencies"),
        }
    elif key in dashboard:
        data = dashboard.get(key)
    else:
        data = root.get(key)
    if not isinstance(data, Mapping):
        data = {"value": data}
    safe = dict(data)
    safe.setdefault("paper_only", True)
    for flag, expected in SAFE_FLAGS.items():
        safe.setdefault(flag, expected)
    return envelope(key, safe, generated_at=generated)


def create_options_income_router(payload_provider: Callable[[], Mapping[str, Any]]) -> Any:
    try:
        from fastapi import APIRouter
    except Exception:  # pragma: no cover - fallback is for minimal runtimes without FastAPI.
        return _FallbackRouter(payload_provider)

    router = APIRouter(tags=["options-income"])

    for section, path in OPTIONS_INCOME_API_ROUTES.items():
        endpoint = _endpoint(payload_provider, section)
        endpoint.__name__ = f"get_options_income_{section}"
        router.add_api_route(path, endpoint, methods=["GET"])

    @router.get("/api/options-income/report.html")
    def get_options_income_report_html() -> Any:
        from fastapi.responses import HTMLResponse

        from backend.options.options_income_reporting import build_options_income_executive_report

        report = build_options_income_executive_report(snapshot=payload_provider())
        return HTMLResponse(str(report.get("html") or ""), media_type="text/html")

    return router


def _endpoint(payload_provider: Callable[[], Mapping[str, Any]], section: str) -> Callable[[], dict[str, Any]]:
    def handler() -> dict[str, Any]:
        return build_options_income_api_payload(payload_provider(), section)

    return handler


def _assert_safe(payload: Mapping[str, Any]) -> None:
    for key, value in SAFE_FLAGS.items():
        if payload.get(key) is not value:
            raise OptionsIncomeAPIError("Unsafe options-income payload")
    if payload.get("paper_only") is not True:
        raise OptionsIncomeAPIError("Options-income payload must be paper-only")


class _FallbackRouter:
    def __init__(self, payload_provider: Callable[[], Mapping[str, Any]]) -> None:
        self.payload_provider = payload_provider
        self.routes = [dict(path=path, methods={"GET"}, section=section) for section, path in OPTIONS_INCOME_API_ROUTES.items()]


__all__ = [
    "OPTIONS_INCOME_API_ROUTES",
    "OptionsIncomeAPIError",
    "build_options_income_api_payload",
    "create_options_income_router",
]
