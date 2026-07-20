"""Phase 179 — adapters that extract canonical upstream signals (no broker/execution access)."""

from __future__ import annotations

from typing import Any


def section(state: dict[str, Any] | None, key: str) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    value = state.get(key)
    return value if isinstance(value, dict) else {}


def extract_operational_signals(state: dict[str, Any] | None) -> dict[str, Any]:
    """Read Mission Control categorical posture only — never broker APIs."""
    platform = section(state, "platform")
    runtime = section(state, "runtime")
    risk = section(state, "risk")
    alerts = section(state, "alerts")
    freshness = section(state, "data_freshness")
    portfolio = section(state, "portfolio")

    alert_count = alerts.get("count")
    try:
        alert_count_i = int(alert_count) if alert_count is not None else 0
    except (TypeError, ValueError):
        alert_count_i = 0

    runtime_offline = bool(platform.get("runtime_offline"))
    runtime_health = str(platform.get("runtime_health") or runtime.get("heartbeat_status") or "UNKNOWN")
    broker_health = str(platform.get("broker_health") or "UNKNOWN").upper()
    risk_state = str(
        risk.get("overall_risk_state") or risk.get("status") or risk.get("state") or "UNKNOWN"
    ).upper()

    age = freshness.get("age_seconds")
    data_stale = False
    try:
        if age is not None and float(age) > 86400:
            data_stale = True
    except (TypeError, ValueError):
        pass
    if str(freshness.get("overall_freshness") or "").upper() in {"STALE", "OUTDATED"}:
        data_stale = True

    return {
        "runtime_offline": runtime_offline,
        "runtime_health": runtime_health,
        "broker_health": broker_health,
        "risk_state": risk_state,
        "alert_count": alert_count_i,
        "data_stale": data_stale,
        # Portfolio health is categorical only — do not compute returns/PnL here.
        "portfolio_present": bool(portfolio),
        "portfolio_keys": sorted(str(k) for k in portfolio.keys())[:20] if portfolio else [],
    }


def extract_brief_readiness(state: dict[str, Any] | None) -> dict[str, Any]:
    """Prefer precomputed 176J payload on MC state; never invent scores."""
    for key in (
        "executive_brief_readiness",
        "brief_readiness",
        "executive_brief_readiness_report",
    ):
        blob = section(state, key)
        if blob:
            return {
                "overall_state": blob.get("overall_state") or blob.get("state"),
                "score": blob.get("score") or blob.get("overall_readiness_score"),
                "source": key,
            }
    # Nested institutional reporting may carry readiness
    reporting = section(state, "institutional_reporting")
    if reporting.get("overall_state"):
        return {
            "overall_state": reporting.get("overall_state"),
            "score": reporting.get("score"),
            "source": "institutional_reporting",
        }
    return {"overall_state": None, "score": None, "source": None}


def extract_financial_package_safe(
    state: dict[str, Any] | None,
    *,
    report_id: str = "edi-decision",
) -> tuple[dict[str, Any], list[str]]:
    """
    Consume Phase 178 package via service. Returns (package, errors).
    Never recalculates statements. Uses a stable report_id for deterministic EDI runs.
    """
    errors: list[str] = []
    try:
        from backend.executive_reporting.service import ExecutiveFinancialReportingService

        service = ExecutiveFinancialReportingService()
        package = service.generate_from_state(
            state if isinstance(state, dict) else {},
            report_id=report_id,
        )
        if not isinstance(package, dict):
            return {}, ["executive_reporting_invalid_package"]
        return package, errors
    except Exception as exc:  # noqa: BLE001 — degraded isolation
        errors.append(f"executive_reporting_error:{type(exc).__name__}")
        return {}, errors
