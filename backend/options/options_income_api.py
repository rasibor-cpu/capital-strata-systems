from __future__ import annotations

from typing import Any, Callable, Mapping

from backend.options.options_income_advisory_contracts import unexpected_advisory_fault
from backend.options.options_income_dashboard import fail_closed_dashboard
from backend.options.options_income_dashboard_payloads import DEFAULT_TIMESTAMP, envelope
from backend.options.paper_position_repository import SAFE_FLAGS

try:
    from fastapi import Request
except Exception:  # pragma: no cover - minimal runtime fallback.
    Request = Any  # type: ignore[misc,assignment]


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
    # Phase 178A — GET-only advisory data surfaces
    "data_readiness": "/api/options-income/data-readiness",
    "providers": "/api/options-income/providers",
    "option_chain": "/api/options-income/option-chain",
    "holdings": "/api/options-income/holdings",
    "collateral_summary": "/api/options-income/collateral",
    "opportunity_inputs": "/api/options-income/opportunity-inputs",
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
        fault = unexpected_advisory_fault(exc)
        result = fail_closed_dashboard(
            reason=fault["failure_reason"],
            generated_at=str(dict(payload).get("generated_at", DEFAULT_TIMESTAMP)),
        )
        result["correlation_id"] = fault["correlation_id"]
        return result


def _runtime_section_payload(root: Mapping[str, Any], key: str) -> dict[str, Any]:
    generated = str(root.get("generated_at", DEFAULT_TIMESTAMP))
    if key == "root":
        safe_root = dict(root)
        advisory = safe_root.pop("advisory_data", None)
        if isinstance(advisory, Mapping):
            safe_root["advisory_data_summary"] = {
                "readiness_status": advisory.get("readiness_status"),
                "market_data_available": bool(advisory.get("market_data_available")),
                "option_chain_available": bool(advisory.get("option_chain_available")),
                "account_holdings_available": bool(advisory.get("account_holdings_available")),
                "broker_operational_state": advisory.get("broker_operational_state"),
                "broker_option_chain_state": advisory.get("broker_option_chain_state"),
                "broker_expected_condition": advisory.get("broker_expected_condition"),
                "advisory_only": True,
                "execution_allowed": False,
            }
        return envelope("options_income", safe_root, generated_at=generated)
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
                "data_readiness": root.get("data_readiness"),
                "provider_summary": root.get("provider_summary"),
                "execution_authority": root.get("execution_authority", "BLOCKED"),
                "advisory_only": True,
                "state_hash": root.get("state_hash"),
            },
            generated_at=generated,
        )
    if key == "certification":
        cert = root.get("certification") if isinstance(root.get("certification"), Mapping) else {}
        return envelope("certification", dict(cert), generated_at=generated)
    if key == "data_readiness":
        data = root.get("data_readiness") if isinstance(root.get("data_readiness"), Mapping) else {}
        adv = root.get("advisory_data") if isinstance(root.get("advisory_data"), Mapping) else {}
        payload = {
            **dict(data),
            "readiness_status": adv.get("readiness_status") or data.get("status"),
            "missing_dependencies": root.get("missing_dependencies"),
            "last_successful_refresh": root.get("last_successful_refresh"),
            "broker_operational_state": adv.get("broker_operational_state"),
            "broker_option_chain_state": adv.get("broker_option_chain_state"),
            "broker_expected_condition": adv.get("broker_expected_condition"),
            "execution_ready": False,
            "live_ready": False,
            "advisory_only": True,
        }
        return envelope("data_readiness", payload, generated_at=generated)
    if key == "providers":
        summary = root.get("provider_summary") if isinstance(root.get("provider_summary"), Mapping) else {}
        adv = root.get("advisory_data") if isinstance(root.get("advisory_data"), Mapping) else {}
        questrade = adv.get("questrade_readiness") if isinstance(adv.get("questrade_readiness"), Mapping) else {}
        return envelope(
            "providers",
            {
                **dict(summary),
                "provider_registry": adv.get("provider_registry") or summary.get("provider_registry"),
                "questrade_readiness": {
                    key: questrade.get(key)
                    for key in (
                        "broker",
                        "state",
                        "adapter_state",
                        "health",
                        "listed_equity_options_capability",
                        "authentication_activated",
                        "network_probe_performed",
                        "order_submission",
                        "advisory_only",
                        "execution_allowed",
                        "provenance",
                    )
                },
                "broker_capability_truth": adv.get("broker_capability_truth") or summary.get("broker_capability_truth"),
                "broker_operational_state": adv.get("broker_operational_state"),
                "broker_option_chain_state": adv.get("broker_option_chain_state"),
                "advisory_only": True,
                "execution_allowed": False,
            },
            generated_at=generated,
        )
    if key == "option_chain":
        adv = root.get("advisory_data") if isinstance(root.get("advisory_data"), Mapping) else {}
        chains = adv.get("option_chains") or adv.get("option_chain_rows") or {"status": "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"}
        meta = dict(chains) if isinstance(chains, Mapping) else {"rows": chains}
        # Strip bulky quotes from metadata surface
        safe = {
            "status": meta.get("status"),
            "underlying_symbol": meta.get("underlying_symbol") or meta.get("canonical_underlying"),
            "expirations": meta.get("expirations") or [],
            "contract_count": meta.get("contract_count"),
            "greeks_origin": meta.get("greeks_origin"),
            "freshness": meta.get("freshness"),
            "provenance": meta.get("provenance"),
            "failure_reason": meta.get("failure_reason"),
            "advisory_only": True,
            "execution_allowed": False,
        }
        return envelope("option_chain", safe, generated_at=generated)
    if key == "holdings":
        adv = root.get("advisory_data") if isinstance(root.get("advisory_data"), Mapping) else {}
        holdings = dict(adv.get("holdings") or {})
        safe_holdings = {
            key: holdings.get(key)
            for key in (
                "contract",
                "schema_version",
                "status",
                "broker",
                "account_type",
                "base_currency",
                "quality",
                "quality_flags",
                "completeness_pct",
                "missing_fields",
                "failure_reason",
                "freshness",
                "age_seconds",
                "provider_timestamp",
                "received_at",
                "generated_at",
                "provenance",
                "demonstration",
            )
        }
        safe_holdings.update(
            {
                "holding_count": len(holdings.get("holdings") or []),
                "option_position_count": len(holdings.get("option_positions") or []),
                "restricted_position_count": len(holdings.get("restricted_positions") or []),
                "short_position_count": len(holdings.get("short_positions") or []),
                "monetary_values_redacted": True,
                "account_identifier_redacted": True,
                "advisory_only": True,
                "execution_allowed": False,
            }
        )
        return envelope("holdings", safe_holdings, generated_at=generated)
    if key == "collateral_summary":
        adv = root.get("advisory_data") if isinstance(root.get("advisory_data"), Mapping) else {}
        coll = dict(adv.get("collateral") or root.get("collateral") or {})
        safe_collateral = {
            key: coll.get(key)
            for key in (
                "contract",
                "schema_version",
                "status",
                "authority_level",
                "source",
                "currency",
                "broker_confirmed",
                "css_derived",
                "failure_reason",
                "provenance",
                "timestamp",
                "generated_at",
                "rejects_simulated_10000_fixture",
            )
        }
        safe_collateral.update(
            {
                "monetary_value_redacted": True,
                "advisory_only": True,
                "execution_allowed": False,
            }
        )
        return envelope("collateral", safe_collateral, generated_at=generated)
    if key == "opportunity_inputs":
        adv = root.get("advisory_data") if isinstance(root.get("advisory_data"), Mapping) else {}
        return envelope(
            "opportunity_inputs",
            {
                "eligibility": adv.get("eligibility"),
                "events": adv.get("events"),
                "broker_listed_options_compatible": adv.get("broker_listed_options_compatible"),
                "broker_operational_state": adv.get("broker_operational_state"),
                "broker_option_chain_state": adv.get("broker_option_chain_state"),
                "broker_expected_condition": adv.get("broker_expected_condition"),
                "missing_dependencies": root.get("missing_dependencies"),
                "opportunity_count": root.get("opportunity_count"),
                "rejected_opportunity_count": root.get("rejected_opportunity_count"),
                "executable_order_objects": False,
                "advisory_only": True,
                "execution_allowed": False,
            },
            generated_at=generated,
        )
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
        from fastapi.responses import JSONResponse
    except Exception:  # pragma: no cover - fallback is for minimal runtimes without FastAPI.
        return _FallbackRouter(payload_provider)

    router = APIRouter(tags=["options-income"])

    for section, path in OPTIONS_INCOME_API_ROUTES.items():
        endpoint = _endpoint(payload_provider, section)
        endpoint.__name__ = f"get_options_income_{section}"
        router.add_api_route(path, endpoint, methods=["GET"])

    @router.get("/api/options-income/report.html")
    def get_options_income_report_html(request: Request) -> Any:
        from fastapi.responses import HTMLResponse

        from backend.options.options_income_reporting import build_options_income_executive_report

        report = build_options_income_executive_report(snapshot=_redacted_report_snapshot(payload_provider()))
        return HTMLResponse(str(report.get("html") or ""), media_type="text/html")

    @router.get("/api/options-income/report.viewer")
    def get_options_income_report_viewer(request: Request) -> Any:
        """Phase 177H — one-page-at-a-time paginated viewer (default human-facing mode)."""
        from fastapi.responses import HTMLResponse

        from backend.options.options_income_reporting import build_options_income_executive_report
        from dashboard.enterprise_shell.routes import ROUTES, mobile_home_href
        from dashboard.reports_viewer import render_paginated_viewer

        report = build_options_income_executive_report(snapshot=_redacted_report_snapshot(payload_provider()))
        doc = report.get("document") or {}
        html = render_paginated_viewer(
            doc if isinstance(doc, dict) else {},
            reports_href=ROUTES.mc_reports,
            home_href=mobile_home_href(for_surface="mission_control"),
            print_href="/api/options-income/report.html",
            surface="mission_control",
        )
        return HTMLResponse(html, media_type="text/html")

    return router


def _endpoint(payload_provider: Callable[[], Mapping[str, Any]], section: str) -> Callable[..., Any]:
    def handler(request: Request) -> Any:
        denied = _authorization_denial(request)
        if denied is not None:
            from fastapi.responses import JSONResponse

            return JSONResponse(denied, status_code=401)
        return build_options_income_api_payload(payload_provider(), section)

    return handler


def _authorization_denial(request: Any) -> dict[str, Any] | None:
    from dashboard.auth.session_bridge import resolve_authorization_context

    auth = resolve_authorization_context(channel="options_income_advisory_api", request=request)
    if auth.authenticated and auth.active:
        return None
    return {
        "status": "DENIED",
        "reason": "AUTHENTICATION_REQUIRED",
        "advisory_only": True,
        "execution_allowed": False,
    }


def _redacted_report_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep public paginated-report compatibility without exposing account detail."""
    root = dict(payload)
    advisory = dict(root.get("advisory_data") or {})
    holdings_envelope = build_options_income_api_payload(root, "holdings")
    collateral_envelope = build_options_income_api_payload(root, "collateral_summary")
    advisory["holdings"] = holdings_envelope.get("data", {})
    advisory["collateral"] = collateral_envelope.get("data", {})
    root["advisory_data"] = advisory
    root["collateral"] = collateral_envelope.get("data", {})
    return root


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
