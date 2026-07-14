from __future__ import annotations

from typing import Any, Callable, Mapping

from backend.options.options_income_dashboard import fail_closed_dashboard
from backend.options.options_income_dashboard_payloads import DEFAULT_TIMESTAMP, envelope
from backend.options.paper_position_repository import SAFE_FLAGS


OPTIONS_INCOME_API_ROUTES = {
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
}


class OptionsIncomeAPIError(ValueError):
    """Raised when an options-income API payload cannot be served safely."""


def build_options_income_api_payload(payload: Mapping[str, Any], section: str) -> dict[str, Any]:
    key = str(section or "").strip()
    if key not in OPTIONS_INCOME_API_ROUTES:
        return envelope("options_income_error", {"status": "FAIL_CLOSED", "reason": f"Unsupported section: {section}"})
    try:
        root = dict(payload)
        _assert_safe(root)
        data = root["summary"] if key == "summary" else root[key]
        return envelope(key, data, generated_at=str(root.get("generated_at", DEFAULT_TIMESTAMP)))
    except Exception as exc:
        return fail_closed_dashboard(reason=str(exc) or exc.__class__.__name__, generated_at=str(dict(payload).get("generated_at", DEFAULT_TIMESTAMP)))


def create_options_income_router(payload_provider: Callable[[], Mapping[str, Any]]) -> Any:
    try:
        from fastapi import APIRouter
    except Exception:  # pragma: no cover - fallback is for minimal runtimes without FastAPI.
        return _FallbackRouter(payload_provider)

    router = APIRouter()

    for section, path in OPTIONS_INCOME_API_ROUTES.items():
        endpoint = _endpoint(payload_provider, section)
        endpoint.__name__ = f"get_options_income_{section}"
        router.add_api_route(path, endpoint, methods=["GET"])
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
