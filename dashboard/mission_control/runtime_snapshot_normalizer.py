from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from dashboard.mission_control.serializers import state_hash
from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


UNAVAILABLE_TEXT = {None, "", "N/A", "NA", "NONE", "UNKNOWN", DATA_UNAVAILABLE, "UNAVAILABLE"}


def normalize_runtime_snapshot(
    source: Any,
    frontend_payload: Mapping[str, Any] | None = None,
    *,
    source_name: str = "runtime_snapshot_provider",
    stale_after_seconds: float = 120.0,
) -> dict[str, Any]:
    frontend = frontend_payload if isinstance(frontend_payload, Mapping) else _frontend_from_source(source)
    if not isinstance(frontend, Mapping) or not isinstance(frontend.get("sections"), Mapping):
        artifact_snapshot = _snapshot_from_artifacts(source, source_name=source_name)
        if artifact_snapshot:
            return artifact_snapshot
        return offline_runtime_snapshot(reason="runtime_snapshot_unavailable", source_name=source_name)
    if str(frontend.get("mission_control_data_source") or "").upper() == "UNAVAILABLE":
        return offline_runtime_snapshot(reason="frontend_source_unavailable", source_name=source_name)

    sections = frontend.get("sections", {})
    session = frontend.get("session") if isinstance(frontend.get("session"), Mapping) else {}
    broker = sections.get("broker") if isinstance(sections.get("broker"), Mapping) else {}
    account = sections.get("account_summary") if isinstance(sections.get("account_summary"), Mapping) else {}
    pnl = sections.get("pnl_summary") if isinstance(sections.get("pnl_summary"), Mapping) else {}
    positions = sections.get("positions") if isinstance(sections.get("positions"), Mapping) else {}
    risk = sections.get("risk") if isinstance(sections.get("risk"), Mapping) else {}
    market = sections.get("market") if isinstance(sections.get("market"), Mapping) else {}
    certification = sections.get("runtime_certification_snapshot") if isinstance(sections.get("runtime_certification_snapshot"), Mapping) else {}
    rc1 = sections.get("rc1_operational_dashboard") if isinstance(sections.get("rc1_operational_dashboard"), Mapping) else {}

    generated_at = _first_text(frontend.get("generated_at"), frontend.get("timestamp"), default=_now())
    heartbeat = _first_text(broker.get("last_heartbeat"), broker.get("last_successful_sync"), generated_at, default="UNAVAILABLE")
    heartbeat_age = _age_seconds(heartbeat)
    heartbeat_status = _heartbeat_status(heartbeat_age, heartbeat, stale_after_seconds=stale_after_seconds)
    runtime_status = _runtime_status(frontend, certification, heartbeat_status)
    source_status = str(frontend.get("mission_control_data_source") or "RUNTIME").upper()
    runtime_id = _runtime_id(frontend, session, source_name)
    alert_count = _extract_alert_count(source)

    snapshot = {
        "runtime_id": runtime_id,
        "session_id": _first_text(session.get("session_id"), frontend.get("session_id"), default="UNAVAILABLE"),
        "user_id": _first_text(session.get("user_id"), frontend.get("user_id"), default="UNAVAILABLE"),
        "runtime_status": runtime_status,
        "runtime_mode": _first_text(frontend.get("resolved_mode"), session.get("resolved_mode"), default="UNAVAILABLE"),
        "engine_mode": _first_text(session.get("engine_mode"), frontend.get("engine_mode"), default="UNAVAILABLE"),
        "cycle_mode": _first_text(frontend.get("cycle_mode"), default="UNAVAILABLE"),
        "cycle": _number(session.get("cycle_number", frontend.get("cycle_number")), default=0),
        "uptime_seconds": _number(frontend.get("uptime_seconds"), default="UNAVAILABLE"),
        "heartbeat_status": heartbeat_status,
        "heartbeat_age_seconds": heartbeat_age,
        "last_heartbeat": heartbeat,
        "last_successful_cycle": _first_text(frontend.get("last_successful_cycle"), default="UNAVAILABLE"),
        "last_failed_cycle": _first_text(frontend.get("last_failed_cycle"), default="UNAVAILABLE"),
        "restart_count": _number(broker.get("restart_count"), default=0),
        "failure_count": _number(broker.get("failure_count"), default=0),
        "recovery_count": _number(broker.get("recovery_count"), default=0),
        "alert_count": alert_count,
        "disconnect_count": _number(broker.get("disconnect_count"), default=0),
        "runtime_health": _first_text(certification.get("operational_state"), rc1.get("operational_state"), risk.get("risk_state"), default=runtime_status),
        "data_freshness": heartbeat_status,
        "generated_at": generated_at,
        "observed_at": heartbeat if heartbeat not in UNAVAILABLE_TEXT else generated_at,
        "source": source_status if source_status in {"LIVE", "RUNTIME", "CACHE", "HISTORICAL", "MOCK", "DEMO"} else "RUNTIME",
        "provenance": {
            "source_name": source_name,
            "frontend_schema": frontend.get("payload_schema", "UNAVAILABLE"),
            "frontend_source": frontend.get("source_metadata", {}),
        },
        "broker": {
            "selected_broker": _first_text(broker.get("selected_broker"), default="UNAVAILABLE"),
            "broker_mode": _first_text(broker.get("broker_mode"), default="UNAVAILABLE"),
            "broker_health": _first_text(broker.get("broker_health"), broker.get("overall_status"), default="UNAVAILABLE"),
            "authentication": _first_text(broker.get("authentication_status"), broker.get("auth_status"), default="UNAVAILABLE"),
            "transport": _first_text(broker.get("connection_status"), broker.get("api_health"), default="UNAVAILABLE"),
            "account": _first_text(broker.get("account_data_health"), broker.get("account_status"), default="UNAVAILABLE"),
            "balances": _first_text(broker.get("balance_position_status"), broker.get("balance_status"), default="UNAVAILABLE"),
            "buying_power": broker.get("buying_power", account.get("buying_power", "UNAVAILABLE")),
            "margin": _first_text(broker.get("margin_status"), default="UNAVAILABLE"),
            "market_data": _first_text(broker.get("market_data_status"), broker.get("product_price_status"), default="UNAVAILABLE"),
            "products": broker.get("products_loaded", "UNAVAILABLE"),
            "readiness": _first_text(broker.get("readiness_state"), broker.get("readiness_status"), default="UNAVAILABLE"),
            "overall_status": _first_text(broker.get("overall_status"), broker.get("broker_health"), default="UNAVAILABLE"),
            "state_hash": _first_text(broker.get("state_hash"), default="UNAVAILABLE"),
            "provenance": broker.get("status_provenance", {}),
            "failure_reason": _first_text(broker.get("failure_reason"), broker.get("connection_error"), default="UNAVAILABLE"),
            "warnings": broker.get("warning_reasons", broker.get("readiness_reasons", [])),
            "execution_scope": _first_text(broker.get("execution_scope"), default="READ_ONLY"),
        },
        "portfolio": {
            "equity": account.get("total_equity", "UNAVAILABLE"),
            "cash": account.get("cash_balance", "UNAVAILABLE"),
            "buying_power": account.get("buying_power", "UNAVAILABLE"),
            "capital_deployed": positions.get("total_exposure", pnl.get("total_exposure", "UNAVAILABLE")),
            "capital_available": account.get("buying_power", "UNAVAILABLE"),
            "realized_pnl": pnl.get("realized_pnl", "UNAVAILABLE"),
            "unrealized_pnl": pnl.get("unrealized_pnl", "UNAVAILABLE"),
            "net_pnl": pnl.get("net_pnl", "UNAVAILABLE"),
            "positions": positions.get("items", positions.get("open_positions", [])),
            "open_positions": positions.get("total", positions.get("open_count", "UNAVAILABLE")),
            "exposure": pnl.get("total_exposure", positions.get("total_exposure", "UNAVAILABLE")),
            "drawdown": risk.get("current_drawdown", "UNAVAILABLE"),
            "asset_allocation": positions.get("by_asset", {}),
            "pnl_by_asset": pnl.get("asset_unrealized_pnl", {}),
            "pnl_by_strategy": "UNAVAILABLE",
        },
        "risk": {
            "risk_status": _first_text(risk.get("risk_state"), default="UNAVAILABLE"),
            "risk_score": risk.get("risk_score", "UNAVAILABLE"),
            "trade_gate_status": _first_text(risk.get("gate_status"), default="UNAVAILABLE"),
            "anti_bleed_guard": "UNAVAILABLE",
            "margin_gate": "UNAVAILABLE",
            "kill_switch": "UNAVAILABLE",
            "drawdown": risk.get("current_drawdown", "UNAVAILABLE"),
            "exposure": risk.get("total_exposure", "UNAVAILABLE"),
        },
        "market": {
            "market_regime": _first_text(market.get("market_regime"), market.get("regime_state"), default="UNAVAILABLE"),
            "trend": _first_text(market.get("trend_state"), default="UNAVAILABLE"),
            "volatility": _first_text(market.get("volatility_state"), default="UNAVAILABLE"),
            "liquidity": _first_text(market.get("liquidity_state"), default="UNAVAILABLE"),
            "momentum": _first_text(market.get("momentum_state"), default="UNAVAILABLE"),
            "vwap": _first_text(market.get("vwap_state"), default="UNAVAILABLE"),
            "spread": _first_text(market.get("spread_state"), default="UNAVAILABLE"),
            "signal_confluence": _first_text(market.get("signal_confluence_state"), default="UNAVAILABLE"),
        },
        "certification": {
            "rc1_certification": _first_text(certification.get("certification"), default="UNAVAILABLE"),
            "rc1_operational_readiness": _first_text(certification.get("operational_state"), default="UNAVAILABLE"),
            "runtime_readiness": _first_text(certification.get("operational_state"), default=runtime_status),
            "broker_readiness": _first_text(broker.get("broker_health"), default="UNAVAILABLE"),
            "options_income_certification": "UNAVAILABLE",
            "blockers": certification.get("blocker_reasons", []),
            "warnings": certification.get("warning_reasons", []),
        },
        "alerts": {
            "active_alerts": _alerts_from_source(source),
            "count": alert_count,
            "heartbeat_status": heartbeat_status,
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    snapshot["state_hash"] = state_hash({key: value for key, value in snapshot.items() if key != "state_hash"})
    return snapshot


def offline_runtime_snapshot(*, reason: str, source_name: str = "runtime_snapshot_provider") -> dict[str, Any]:
    generated_at = _now()
    snapshot = {
        "runtime_id": "UNAVAILABLE",
        "session_id": "UNAVAILABLE",
        "user_id": "UNAVAILABLE",
        "runtime_status": "OFFLINE",
        "runtime_mode": "UNAVAILABLE",
        "engine_mode": "UNAVAILABLE",
        "cycle_mode": "UNAVAILABLE",
        "cycle": "UNAVAILABLE",
        "uptime_seconds": "UNAVAILABLE",
        "heartbeat_status": "UNAVAILABLE",
        "heartbeat_age_seconds": "UNAVAILABLE",
        "last_heartbeat": "UNAVAILABLE",
        "last_successful_cycle": "UNAVAILABLE",
        "last_failed_cycle": "UNAVAILABLE",
        "restart_count": "UNAVAILABLE",
        "failure_count": "UNAVAILABLE",
        "recovery_count": "UNAVAILABLE",
        "alert_count": "UNAVAILABLE",
        "disconnect_count": "UNAVAILABLE",
        "runtime_health": "UNAVAILABLE",
        "data_freshness": "UNAVAILABLE",
        "generated_at": generated_at,
        "observed_at": "UNAVAILABLE",
        "source": "UNAVAILABLE",
        "provenance": {"source_name": source_name, "reason": reason},
        "broker": _unavailable_group(),
        "portfolio": _unavailable_group(),
        "risk": _unavailable_group(),
        "market": _unavailable_group(),
        "certification": _unavailable_group(),
        "alerts": {"active_alerts": [], "count": "UNAVAILABLE", "heartbeat_status": "UNAVAILABLE"},
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    snapshot["state_hash"] = state_hash({key: value for key, value in snapshot.items() if key != "state_hash"})
    return snapshot


def _frontend_from_source(source: Any) -> Mapping[str, Any] | None:
    if isinstance(source, Mapping):
        if isinstance(source.get("frontend_payload"), Mapping):
            return source.get("frontend_payload")
        if source.get("payload_schema") == "css.frontend.contract.v1" and isinstance(source.get("sections"), Mapping):
            return source
    return None


def _snapshot_from_artifacts(source: Any, *, source_name: str) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        return {}
    supervisor = source.get("supervisor") if isinstance(source.get("supervisor"), Mapping) else {}
    session_payload = source.get("session") if isinstance(source.get("session"), Mapping) else {}
    account = source.get("account") if isinstance(source.get("account"), Mapping) else {}
    session = session_payload.get("session") if isinstance(session_payload.get("session"), Mapping) else session_payload
    if not any((supervisor, session, account)):
        return {}

    heartbeat = _first_text(supervisor.get("last_heartbeat"), supervisor.get("last_heartbeat_at"), default="UNAVAILABLE")
    heartbeat_age = _age_seconds(heartbeat)
    heartbeat_status = _heartbeat_status(heartbeat_age, heartbeat, stale_after_seconds=120.0)
    generated_at = _now()
    snapshot = {
        "runtime_id": _first_text(session.get("runtime_id"), session.get("session_id"), default="runtime_artifacts:UNAVAILABLE"),
        "session_id": _first_text(session.get("session_id"), default="UNAVAILABLE"),
        "user_id": _first_text(session.get("user_id"), default="UNAVAILABLE"),
        "runtime_status": _first_text(supervisor.get("status"), default="OFFLINE"),
        "runtime_mode": _first_text(session.get("resolved_mode"), session.get("live_or_paper"), session.get("engine_mode"), default="UNAVAILABLE"),
        "engine_mode": _first_text(session.get("engine_mode"), default="UNAVAILABLE"),
        "cycle_mode": _first_text(session.get("cycle_mode"), default="UNAVAILABLE"),
        "cycle": _number(session.get("cycle_number"), default=0),
        "uptime_seconds": _number(supervisor.get("uptime_seconds"), default="UNAVAILABLE"),
        "heartbeat_status": heartbeat_status,
        "heartbeat_age_seconds": heartbeat_age,
        "last_heartbeat": heartbeat,
        "last_successful_cycle": _first_text(supervisor.get("last_successful_cycle"), default="UNAVAILABLE"),
        "last_failed_cycle": _first_text(supervisor.get("last_failed_cycle"), default="UNAVAILABLE"),
        "restart_count": _number(supervisor.get("restart_count"), default=0),
        "failure_count": _number(supervisor.get("failure_count"), default=0),
        "recovery_count": _number(supervisor.get("recovery_count"), default=0),
        "alert_count": "UNAVAILABLE",
        "disconnect_count": _number(supervisor.get("disconnect_count"), default=0),
        "runtime_health": _first_text(supervisor.get("status"), default="UNAVAILABLE"),
        "data_freshness": heartbeat_status,
        "generated_at": generated_at,
        "observed_at": heartbeat,
        "source": str(source.get("source") or "CACHE").upper(),
        "provenance": {"source_name": source_name, "source_files": ["supervisor", "session", "account"]},
        "broker": {"selected_broker": _first_text(session.get("broker"), session.get("selected_broker"), default="UNAVAILABLE")},
        "portfolio": {
            "equity": account.get("total_equity", account.get("account_balance", "UNAVAILABLE")),
            "cash": account.get("cash_balance", account.get("account_balance", "UNAVAILABLE")),
            "buying_power": account.get("buying_power", "UNAVAILABLE"),
            "realized_pnl": account.get("lifetime_realized_pnl", "UNAVAILABLE"),
            "unrealized_pnl": account.get("unrealized_pnl", "UNAVAILABLE"),
            "net_pnl": (
                account.get("lifetime_realized_pnl", 0.0) + account.get("unrealized_pnl", 0.0)
                if isinstance(account.get("lifetime_realized_pnl", 0.0), (int, float))
                and isinstance(account.get("unrealized_pnl", 0.0), (int, float))
                else "UNAVAILABLE"
            ),
            "positions": account.get("positions", []),
            "open_positions": len(account.get("positions", [])) if isinstance(account.get("positions"), list) else "UNAVAILABLE",
        },
        "risk": {"risk_status": _first_text(session.get("risk_status"), default="UNAVAILABLE")},
        "market": {"market_regime": _first_text(session.get("market_regime"), default="UNAVAILABLE")},
        "certification": {"rc1_certification": "UNAVAILABLE", "runtime_readiness": _first_text(supervisor.get("status"), default="UNAVAILABLE")},
        "alerts": {"active_alerts": [], "count": "UNAVAILABLE", "heartbeat_status": heartbeat_status},
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    snapshot["state_hash"] = state_hash({key: value for key, value in snapshot.items() if key != "state_hash"})
    return snapshot


def _runtime_id(frontend: Mapping[str, Any], session: Mapping[str, Any], source_name: str) -> str:
    return _first_text(
        frontend.get("runtime_id"),
        session.get("runtime_id"),
        session.get("session_id"),
        frontend.get("session_id"),
        default=f"{source_name}:UNAVAILABLE",
    )


def _runtime_status(frontend: Mapping[str, Any], certification: Mapping[str, Any], heartbeat_status: str) -> str:
    explicit = _first_text(certification.get("operational_state"), frontend.get("runtime_status"), default="")
    if explicit:
        return explicit
    if heartbeat_status in {"FRESH", "AGING"}:
        return "ONLINE"
    if heartbeat_status == "STALE":
        return "STALE"
    return "OFFLINE"


def _heartbeat_status(age_seconds: float | str, heartbeat: str, *, stale_after_seconds: float) -> str:
    if heartbeat in UNAVAILABLE_TEXT or age_seconds == "UNAVAILABLE":
        return "UNAVAILABLE"
    if float(age_seconds) <= stale_after_seconds / 2:
        return "FRESH"
    if float(age_seconds) <= stale_after_seconds:
        return "AGING"
    return "STALE"


def _age_seconds(value: str) -> float | str:
    if value in UNAVAILABLE_TEXT:
        return "UNAVAILABLE"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "UNAVAILABLE"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return round(max((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds(), 0.0), 3)


def _first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if value not in UNAVAILABLE_TEXT:
            text = str(value).strip()
            if text and text.upper() not in UNAVAILABLE_TEXT:
                return text
    return default


def _number(value: Any, *, default: Any) -> Any:
    if value in UNAVAILABLE_TEXT:
        return default
    try:
        return int(value) if isinstance(default, int) else float(value)
    except (TypeError, ValueError):
        return default


def _extract_alert_count(source: Any) -> Any:
    if isinstance(source, Mapping):
        alerts = source.get("alerts")
        if isinstance(alerts, Mapping):
            return alerts.get("count", len(alerts.get("active", [])) if isinstance(alerts.get("active"), list) else "UNAVAILABLE")
        if isinstance(alerts, list):
            return len(alerts)
    return "UNAVAILABLE"


def _alerts_from_source(source: Any) -> list[Any]:
    if isinstance(source, Mapping):
        alerts = source.get("alerts")
        if isinstance(alerts, Mapping):
            active = alerts.get("active")
            return active if isinstance(active, list) else []
        if isinstance(alerts, list):
            return list(alerts)
    return []


def _unavailable_group() -> dict[str, str]:
    return {"status": "UNAVAILABLE"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["normalize_runtime_snapshot", "offline_runtime_snapshot"]
