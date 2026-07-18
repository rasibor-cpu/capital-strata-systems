from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from backend.runtime.canonical_runtime_authority import (
    AUTHORITY_ONLINE,
    classify_canonical_runtime_authority,
)


SCHEMA_VERSION = "css.op002.canonical_runtime_snapshot.v1"
DATA_UNAVAILABLE = "DATA UNAVAILABLE"
UNAVAILABLE_TEXT = {None, "", "N/A", "NA", "NONE", "UNKNOWN", DATA_UNAVAILABLE, "UNAVAILABLE"}


def build_canonical_runtime_snapshot(
    source: Any,
    frontend_payload: Mapping[str, Any] | None = None,
    *,
    source_name: str = "backend.runtime.canonical_runtime_snapshot",
    stale_after_seconds: float = 120.0,
) -> dict[str, Any]:
    """Build the single read-only runtime snapshot used by runtime displays.

    The function normalizes existing dashboard/frontend/runtime-artifact
    payloads. It does not query brokers, mutate artifacts, write state, or
    grant execution authority.
    """

    frontend = frontend_payload if isinstance(frontend_payload, Mapping) else _frontend_from_source(source)
    if not isinstance(frontend, Mapping) or not isinstance(frontend.get("sections"), Mapping):
        artifact_snapshot = _snapshot_from_artifacts(source, source_name=source_name)
        if artifact_snapshot:
            return artifact_snapshot
        return offline_runtime_snapshot(reason="runtime_snapshot_unavailable", source_name=source_name)
    if str(frontend.get("mission_control_data_source") or "").upper() == "UNAVAILABLE":
        return offline_runtime_snapshot(reason="frontend_source_unavailable", source_name=source_name)

    sections = frontend.get("sections", {})
    session = _mapping(frontend.get("session"))
    broker = _mapping(sections.get("broker"))
    account = _mapping(sections.get("account_summary"))
    pnl = _mapping(sections.get("pnl_summary"))
    positions = _mapping(sections.get("positions"))
    risk = _mapping(sections.get("risk"))
    market = _mapping(sections.get("market"))
    options_income = _mapping(sections.get("options_income"))
    decision = _mapping(sections.get("institutional_investment_committee"))
    certification = _mapping(sections.get("runtime_certification_snapshot"))
    rc1 = _mapping(sections.get("rc1_operational_dashboard"))

    generated_at = _first_text(frontend.get("generated_at"), frontend.get("timestamp"), default=_now())
    # Phase 172A: the canonical launcher's supervisor heartbeat (threaded
    # through by the caller as frontend["canonical_runtime_supervisor"], read
    # directly from runtime/supervisor/css_runtime_supervisor_state.json)
    # takes precedence over broker connectivity data -- "Last Runtime
    # Heartbeat" must reflect the canonical launcher, never broker sync time.
    canonical_supervisor = _mapping(frontend.get("canonical_runtime_supervisor"))
    canonical_authority = classify_canonical_runtime_authority(canonical_supervisor, None) if canonical_supervisor else None
    canonical_heartbeat = _first_text(canonical_supervisor.get("last_heartbeat_at"), canonical_supervisor.get("last_heartbeat"), default="")
    heartbeat = canonical_heartbeat or _first_text(broker.get("last_heartbeat"), broker.get("last_successful_sync"), generated_at, default="UNAVAILABLE")
    heartbeat_age = _age_seconds(heartbeat)
    heartbeat_status = _heartbeat_status(heartbeat_age, heartbeat, stale_after_seconds=stale_after_seconds)
    source_status = str(frontend.get("mission_control_data_source") or "RUNTIME").upper()
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "runtime_id": _runtime_id(frontend, session, source_name),
        "session_id": _first_text(session.get("session_id"), frontend.get("session_id"), default="UNAVAILABLE"),
        "user_id": _first_text(session.get("user_id"), frontend.get("user_id"), default="UNAVAILABLE"),
        "runtime_status": (
            canonical_authority["authority_status"]
            if canonical_authority and canonical_authority["authority_status"] != AUTHORITY_ONLINE
            else _runtime_status(frontend, certification, heartbeat_status)
        ),
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
        "alert_count": _extract_alert_count(source),
        "disconnect_count": _number(broker.get("disconnect_count"), default=0),
        "runtime_health": _first_text(certification.get("operational_state"), rc1.get("operational_state"), risk.get("risk_state"), default=heartbeat_status),
        "data_freshness": heartbeat_status,
        "generated_at": generated_at,
        "observed_at": heartbeat if heartbeat not in UNAVAILABLE_TEXT else generated_at,
        "source": source_status
        if source_status
        in {"LIVE", "RUNTIME", "RUNTIME_ENDPOINT", "RUNTIME_ARTIFACT", "RUNTIME_REGISTRY", "CACHE", "HISTORICAL", "MOCK", "DEMO"}
        else "RUNTIME",
        "provenance": {
            "canonical_owner": "backend.runtime.canonical_runtime_snapshot",
            "source_name": source_name,
            "frontend_schema": frontend.get("payload_schema", "UNAVAILABLE"),
            "frontend_source": frontend.get("source_metadata", {}),
        },
        "broker": _broker_snapshot(broker, account),
        "portfolio": _portfolio_snapshot(account, positions, pnl, risk),
        "risk": _risk_snapshot(risk),
        "market": _market_snapshot(market),
        "decision_intelligence": {
            "status": _first_text(decision.get("status"), decision.get("committee_status"), default="UNAVAILABLE"),
            "source": "dashboard.runtime.frontend_contract",
        },
        "options_income": {
            "status": _first_text(options_income.get("status"), default="UNAVAILABLE"),
            "certification": _first_text(options_income.get("certification"), default="UNAVAILABLE"),
            "operational_readiness": _first_text(options_income.get("operational_readiness"), default="UNAVAILABLE"),
        },
        "certification": {
            "rc1_certification": _first_text(certification.get("certification"), default="UNAVAILABLE"),
            "rc1_operational_readiness": _first_text(certification.get("operational_state"), default="UNAVAILABLE"),
            "runtime_readiness": _first_text(certification.get("operational_state"), default=heartbeat_status),
            "broker_readiness": _first_text(broker.get("broker_health"), broker.get("overall_status"), default="UNAVAILABLE"),
            "options_income_certification": _first_text(options_income.get("certification"), default="UNAVAILABLE"),
            "blockers": certification.get("blocker_reasons", []),
            "warnings": certification.get("warning_reasons", []),
        },
        "alerts": {
            "active_alerts": _alerts_from_source(source),
            "count": _extract_alert_count(source),
            "heartbeat_status": heartbeat_status,
        },
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    snapshot["state_hash"] = stable_state_hash({key: value for key, value in snapshot.items() if key != "state_hash"})
    return _json_safe(snapshot)


def offline_runtime_snapshot(*, reason: str, source_name: str = "backend.runtime.canonical_runtime_snapshot") -> dict[str, Any]:
    generated_at = _now()
    snapshot = {
        "schema_version": SCHEMA_VERSION,
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
        "provenance": {
            "canonical_owner": "backend.runtime.canonical_runtime_snapshot",
            "source_name": source_name,
            "reason": reason,
        },
        "broker": _unavailable_group(),
        "portfolio": _unavailable_group(),
        "risk": _unavailable_group(),
        "market": _unavailable_group(),
        "decision_intelligence": _unavailable_group(),
        "options_income": _unavailable_group(),
        "certification": _unavailable_group(),
        "alerts": {"active_alerts": [], "count": "UNAVAILABLE", "heartbeat_status": "UNAVAILABLE"},
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    snapshot["state_hash"] = stable_state_hash({key: value for key, value in snapshot.items() if key != "state_hash"})
    return snapshot


def stable_state_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(_json_safe(dict(payload)), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


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
    supervisor = _mapping(source.get("supervisor"))
    session_payload = _mapping(source.get("session"))
    account = _mapping(source.get("account"))
    runtime_portfolio = _mapping(source.get("runtime_portfolio_state"))
    diagnostics = _mapping(source.get("runtime_source_diagnostics"))
    session = _mapping(session_payload.get("session")) if isinstance(session_payload.get("session"), Mapping) else session_payload
    if not any((supervisor, session, account)):
        return {}

    heartbeat = _first_text(supervisor.get("last_heartbeat"), supervisor.get("last_heartbeat_at"), default="UNAVAILABLE")
    heartbeat_age = _age_seconds(heartbeat)
    heartbeat_status = _heartbeat_status(heartbeat_age, heartbeat, stale_after_seconds=120.0)
    generated_at = _now()
    # Phase 172A: prefer the fail-closed canonical authority classification
    # (backend.runtime.canonical_runtime_authority, computed by
    # RuntimeArtifactFreshnessManager) over the raw supervisor status field
    # whenever it detects a non-ONLINE condition -- e.g. ORPHANED_RUNTIME,
    # where a subordinate dashboard heartbeat is fresh but the canonical
    # launcher is stopped/absent. A subordinate dashboard heartbeat must
    # never be able to present itself as canonical runtime health.
    canonical_authority = _mapping(_mapping(diagnostics.get("freshness")).get("canonical_authority"))
    authority_status = str(canonical_authority.get("authority_status") or "").upper()
    runtime_status = authority_status if authority_status and authority_status != "ONLINE" else _first_text(supervisor.get("status"), default="OFFLINE")
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "runtime_id": _first_text(session.get("runtime_id"), session.get("session_id"), default="runtime_artifacts:UNAVAILABLE"),
        "session_id": _first_text(session.get("session_id"), default="UNAVAILABLE"),
        "user_id": _first_text(session.get("user_id"), default="UNAVAILABLE"),
        "runtime_status": runtime_status,
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
        "source": str(source.get("source_type") or source.get("source") or "CACHE").upper(),
        "provenance": {
            "canonical_owner": "backend.runtime.canonical_runtime_snapshot",
            "source_name": source_name,
            "source_files": ["supervisor", "session", "account", "runtime_portfolio_state"],
            "runtime_source": diagnostics,
        },
        "source_diagnostics": diagnostics,
        "broker": _broker_from_artifacts(session, account, runtime_portfolio),
        "portfolio": _portfolio_from_artifacts(account, runtime_portfolio),
        "risk": {"risk_status": _first_text(session.get("risk_status"), default="UNAVAILABLE")},
        "market": {"market_regime": _first_text(session.get("market_regime"), default="UNAVAILABLE")},
        "decision_intelligence": _unavailable_group(),
        "options_income": _unavailable_group(),
        "certification": {"rc1_certification": "UNAVAILABLE", "runtime_readiness": _first_text(supervisor.get("status"), default="UNAVAILABLE")},
        "alerts": {"active_alerts": [], "count": "UNAVAILABLE", "heartbeat_status": heartbeat_status},
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }
    snapshot["state_hash"] = stable_state_hash({key: value for key, value in snapshot.items() if key != "state_hash"})
    return _json_safe(snapshot)


def _broker_snapshot(broker: Mapping[str, Any], account: Mapping[str, Any]) -> dict[str, Any]:
    canonical = _mapping(broker.get("canonical_broker_runtime_state"))
    source = canonical if canonical else broker
    return {
        "selected_broker": _first_text(broker.get("selected_broker"), source.get("broker"), default="UNAVAILABLE"),
        "broker_mode": _first_text(broker.get("broker_mode"), source.get("mode"), default="UNAVAILABLE"),
        "broker_health": _first_text(source.get("overall_status"), broker.get("broker_health"), default="UNAVAILABLE"),
        "authentication": _first_text(source.get("authentication_status"), broker.get("authentication_status"), broker.get("auth_status"), default="UNAVAILABLE"),
        "transport": _first_text(source.get("transport_status"), source.get("connection_status"), broker.get("connection_status"), broker.get("api_health"), default="UNAVAILABLE"),
        "account": _first_text(source.get("account_status"), broker.get("account_data_health"), broker.get("account_status"), default="UNAVAILABLE"),
        "balances": _first_text(source.get("balance_status"), broker.get("balance_position_status"), broker.get("balance_status"), default="UNAVAILABLE"),
        "buying_power": _first_text(source.get("buying_power_status"), broker.get("buying_power"), account.get("buying_power"), default="UNAVAILABLE"),
        "margin": _first_text(source.get("margin_status"), broker.get("margin_status"), default="UNAVAILABLE"),
        "market_data": _first_text(source.get("market_data_status"), broker.get("market_data_status"), broker.get("product_price_status"), default="UNAVAILABLE"),
        "products": _first_text(source.get("product_status"), broker.get("products_loaded"), default="UNAVAILABLE"),
        "readiness": _first_text(source.get("readiness_state"), broker.get("readiness_state"), broker.get("readiness_status"), default="UNAVAILABLE"),
        "overall_status": _first_text(source.get("overall_status"), broker.get("overall_status"), broker.get("broker_health"), default="UNAVAILABLE"),
        "state_hash": _first_text(source.get("state_hash"), broker.get("state_hash"), default="UNAVAILABLE"),
        "provenance": source.get("status_provenance", broker.get("status_provenance", {})),
        "failure_reason": _first_text(source.get("failure_reason"), broker.get("connection_error"), default="UNAVAILABLE"),
        "warnings": source.get("warning_reasons", broker.get("readiness_reasons", [])),
        "execution_scope": _first_text(source.get("execution_scope"), broker.get("execution_scope"), default="READ_ONLY"),
    }


def _portfolio_snapshot(account: Mapping[str, Any], positions: Mapping[str, Any], pnl: Mapping[str, Any], risk: Mapping[str, Any]) -> dict[str, Any]:
    return {
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
    }


def _portfolio_from_artifacts(account: Mapping[str, Any], runtime_portfolio: Mapping[str, Any]) -> dict[str, Any]:
    nested = _mapping(runtime_portfolio.get("account"))
    positions = runtime_portfolio.get("positions", account.get("positions", []))
    return {
        "equity": nested.get("equity", account.get("total_equity", account.get("account_balance", "UNAVAILABLE"))),
        "cash": nested.get("cash", account.get("cash_balance", account.get("account_balance", "UNAVAILABLE"))),
        "buying_power": nested.get("buying_power", account.get("buying_power", "UNAVAILABLE")),
        "realized_pnl": nested.get("realized_pnl", account.get("lifetime_realized_pnl", "UNAVAILABLE")),
        "unrealized_pnl": nested.get("open_pnl", account.get("unrealized_pnl", "UNAVAILABLE")),
        "net_pnl": _net_pnl(account),
        "positions": positions,
        "open_positions": len(positions) if isinstance(positions, list) else "UNAVAILABLE",
    }


def _broker_from_artifacts(session: Mapping[str, Any], account: Mapping[str, Any], runtime_portfolio: Mapping[str, Any]) -> dict[str, Any]:
    broker_state = _mapping(session.get("broker_state"))
    if not broker_state:
        broker_state = _mapping(account.get("broker_state"))
    if not broker_state:
        broker_state = _mapping(runtime_portfolio.get("broker_state"))
    canonical = _mapping(broker_state.get("canonical_broker_runtime_state"))
    source = canonical if canonical else broker_state
    return {
        "selected_broker": _first_text(session.get("broker"), session.get("selected_broker"), account.get("selected_broker"), default="UNAVAILABLE"),
        "broker_mode": _first_text(session.get("broker_mode"), account.get("broker_mode"), default="UNAVAILABLE"),
        "broker_health": _first_text(source.get("overall_status"), source.get("broker_health"), source.get("readiness_state"), default="UNAVAILABLE"),
        "authentication": _first_text(source.get("authentication_status"), source.get("authentication"), default="UNAVAILABLE"),
        "transport": _first_text(source.get("connection_status"), source.get("transport"), default="UNAVAILABLE"),
        "account": _first_text(source.get("account_status"), source.get("account"), default="UNAVAILABLE"),
        "balances": _first_text(source.get("balance_status"), source.get("balances"), default="UNAVAILABLE"),
        "buying_power": source.get("buying_power", account.get("buying_power", "UNAVAILABLE")),
        "margin": _first_text(source.get("margin_status"), default="UNAVAILABLE"),
        "market_data": _first_text(source.get("market_data_status"), source.get("market_data"), default="UNAVAILABLE"),
        "products": source.get("product_status", source.get("products_loaded", "UNAVAILABLE")),
        "readiness": _first_text(source.get("readiness_state"), source.get("readiness_status"), default="UNAVAILABLE"),
        "overall_status": _first_text(source.get("overall_status"), source.get("broker_health"), default="UNAVAILABLE"),
        "state_hash": _first_text(source.get("state_hash"), broker_state.get("state_hash"), default="UNAVAILABLE"),
        "provenance": source.get("status_provenance", broker_state.get("status_provenance", {})),
        "failure_reason": _first_text(source.get("failure_reason"), broker_state.get("failure_reason"), default="UNAVAILABLE"),
        "warnings": source.get("warning_reasons", broker_state.get("warning_reasons", [])),
        "execution_scope": _first_text(source.get("execution_scope"), default="READ_ONLY"),
    }


def _risk_snapshot(risk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "risk_status": _first_text(risk.get("risk_state"), default="UNAVAILABLE"),
        "risk_score": risk.get("risk_score", "UNAVAILABLE"),
        "trade_gate_status": _first_text(risk.get("gate_status"), default="UNAVAILABLE"),
        "anti_bleed_guard": _first_text(risk.get("anti_bleed_guard"), default="UNAVAILABLE"),
        "margin_gate": _first_text(risk.get("margin_gate"), default="UNAVAILABLE"),
        "kill_switch": _first_text(risk.get("kill_switch"), default="UNAVAILABLE"),
        "drawdown": risk.get("current_drawdown", "UNAVAILABLE"),
        "exposure": risk.get("total_exposure", "UNAVAILABLE"),
    }


def _market_snapshot(market: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "market_regime": _first_text(market.get("market_regime"), market.get("regime_state"), default="UNAVAILABLE"),
        "trend": _first_text(market.get("trend_state"), default="UNAVAILABLE"),
        "volatility": _first_text(market.get("volatility_state"), default="UNAVAILABLE"),
        "liquidity": _first_text(market.get("liquidity_state"), default="UNAVAILABLE"),
        "momentum": _first_text(market.get("momentum_state"), default="UNAVAILABLE"),
        "vwap": _first_text(market.get("vwap_state"), default="UNAVAILABLE"),
        "spread": _first_text(market.get("spread_state"), default="UNAVAILABLE"),
        "signal_confluence": _first_text(market.get("signal_confluence_state"), default="UNAVAILABLE"),
    }


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


def _net_pnl(account: Mapping[str, Any]) -> Any:
    realized = account.get("lifetime_realized_pnl", 0.0)
    unrealized = account.get("unrealized_pnl", 0.0)
    if isinstance(realized, (int, float)) and isinstance(unrealized, (int, float)):
        return realized + unrealized
    return "UNAVAILABLE"


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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _unavailable_group() -> dict[str, str]:
    return {"status": "UNAVAILABLE"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "DATA_UNAVAILABLE",
    "SCHEMA_VERSION",
    "build_canonical_runtime_snapshot",
    "offline_runtime_snapshot",
    "stable_state_hash",
]
