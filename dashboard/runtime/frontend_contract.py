from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from dashboard.runtime.dashboard_state import (
    DASHBOARD_PAYLOAD_SCHEMA,
    DASHBOARD_PAYLOAD_VERSION,
    DashboardState,
)


FRONTEND_CONTRACT_VERSION = "1.0.0"
FRONTEND_CONTRACT_SCHEMA = "css.frontend.contract.v1"

CONTRACT_NAME = "CSS Institutional Frontend Payload"
CONTRACT_VERSION = FRONTEND_CONTRACT_VERSION
CONTRACT_TIMESTAMP = "2026-05-08T00:00:00Z"
FRONTEND_SECTIONS = (
    "account_summary",
    "positions",
    "pnl_summary",
    "risk",
    "governance",
    "market",
    "execution",
    "opportunities",
    "broker",
)


@dataclass(frozen=True)
class FrontendEnvelope:
    payload_version: str = FRONTEND_CONTRACT_VERSION
    payload_schema: str = FRONTEND_CONTRACT_SCHEMA
    dashboard_payload_version: str = DASHBOARD_PAYLOAD_VERSION
    dashboard_payload_schema: str = DASHBOARD_PAYLOAD_SCHEMA
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    message_type: str = "dashboard_snapshot"
    source: str = "dashboard.runtime.frontend_contract"
    contract_name: str = CONTRACT_NAME
    contract_version: str = CONTRACT_VERSION
    contract_timestamp: str = CONTRACT_TIMESTAMP
    schema_metadata: dict[str, str] = field(
        default_factory=lambda: {
            "strict_typing": "True",
            "enforces_payload_versioning": "True",
            "compatibility": "Backward compatible with CSS legacy dashboards",
        }
    )


@dataclass(frozen=True)
class WebsocketDelta:
    message_type: str
    payload_version: str
    generated_at: str
    changed_sections: list[str]
    data: dict[str, Any]
    sequence: int = 0
    stale_after_ms: int = 15000

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def build_frontend_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
) -> dict[str, Any]:
    dashboard_payload = _dashboard_payload(dashboard_state)
    envelope = FrontendEnvelope()

    payload = {
        "payload_version": envelope.payload_version,
        "payload_schema": envelope.payload_schema,
        "dashboard_payload_version": dashboard_payload.get(
            "payload_version",
            DASHBOARD_PAYLOAD_VERSION,
        ),
        "dashboard_payload_schema": dashboard_payload.get(
            "payload_schema",
            DASHBOARD_PAYLOAD_SCHEMA,
        ),
        "generated_at": envelope.generated_at,
        "message_type": envelope.message_type,
        "source_metadata": {
            "source": envelope.source,
            "canonical_bridge": "DashboardState.to_dict",
            "transport": "snapshot",
            "frontend_safe": True,
            "secrets_redacted": True,
        },
        "contract_name": envelope.contract_name,
        "contract_version": envelope.contract_version,
        "contract_timestamp": envelope.contract_timestamp,
        "schema_metadata": envelope.schema_metadata,
        "session": _mapping(dashboard_payload.get("session")),
        "session_id": str(dashboard_payload.get("session_id", "")),
        "resolved_mode": str(dashboard_payload.get("resolved_mode", "paper")),
        "sections": {
            "account_summary": account_summary(dashboard_payload),
            "positions": positions(dashboard_payload),
            "pnl_summary": pnl_summary(dashboard_payload),
            "risk": risk(dashboard_payload),
            "governance": governance(dashboard_payload),
            "market": market(dashboard_payload),
            "execution": execution(dashboard_payload),
            "opportunities": opportunities(dashboard_payload),
            "broker": broker(dashboard_payload),
        },
    }

    return _json_safe(payload)


def account_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    account = _mapping(dashboard_payload.get("account_summary"))
    return {
        "cash_balance": _number(account.get("cash_balance")),
        "total_equity": _number(account.get("total_equity")),
        "buying_power": _number(account.get("buying_power")),
        "margin_used": _number(account.get("margin_used")),
        "available_margin": _number(account.get("available_margin")),
        "currency": str(account.get("currency", "USD")),
        "broker": str(account.get("broker", "NONE")),
        "account_mode": str(account.get("account_mode", "paper")),
    }


def positions(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    open_positions = _mapping(dashboard_payload.get("open_positions"))
    by_asset = _mapping(open_positions.get("by_asset"))
    position_state = _mapping(dashboard_payload.get("position_state"))
    asset_summaries = _mapping(dashboard_payload.get("asset_class_summaries"))
    items = []

    for position in _list(position_state.get("positions")):
        position_payload = _mapping(position)
        items.append(
            {
                "symbol": str(position_payload.get("symbol", "UNKNOWN")),
                "asset_class": str(
                    position_payload.get("asset_class", "UNKNOWN")
                ),
                "side": str(position_payload.get("side", "UNKNOWN")),
                "qty": _number(position_payload.get("qty")),
                "entry_price": _number(position_payload.get("entry_price")),
                "current_price": _number(position_payload.get("current_price")),
                "exposure": _number(position_payload.get("exposure")),
                "realized_pnl": _number(position_payload.get("realized_pnl")),
                "unrealized_pnl": _number(
                    position_payload.get("unrealized_pnl")
                ),
            }
        )

    for asset_class, summary in asset_summaries.items():
        if items:
            break

        summary_payload = _mapping(summary)
        items.append(
            {
                "asset_class": str(asset_class),
                "open_positions": _integer(
                    summary_payload.get(
                        "open_positions",
                        by_asset.get(str(asset_class), 0),
                    )
                ),
                "realized_pnl": _number(summary_payload.get("realized_pnl")),
                "unrealized_pnl": _number(summary_payload.get("unrealized_pnl")),
                "exposure": _number(summary_payload.get("exposure")),
            }
        )

    return {
        "total": _integer(
            open_positions.get("total", position_state.get("open_count"))
        ),
        "by_asset": {str(key): _integer(value) for key, value in by_asset.items()},
        "long_count": _integer(position_state.get("long_count")),
        "short_count": _integer(position_state.get("short_count")),
        "winner_count": _integer(position_state.get("winner_count")),
        "loser_count": _integer(position_state.get("loser_count")),
        "active_symbols": _string_list(position_state.get("active_symbols")),
        "items": items,
    }


def pnl_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    pnl = _mapping(dashboard_payload.get("pnl_summary"))
    return {
        "realized_pnl": _number(pnl.get("realized_pnl")),
        "unrealized_pnl": _number(pnl.get("unrealized_pnl")),
        "net_pnl": _number(pnl.get("net_pnl")),
        "total_exposure": _number(pnl.get("total_exposure")),
        "exposure_utilization_pct": _number(
            pnl.get("exposure_utilization_pct")
        ),
        "winner_count": _integer(pnl.get("winner_count")),
        "loser_count": _integer(pnl.get("loser_count")),
        "win_rate_pct": _number(pnl.get("win_rate_pct")),
        "account_equity": _number(pnl.get("account_equity")),
    }


def risk(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    risk_payload = _mapping(dashboard_payload.get("risk_summary"))
    return {
        "risk_state": str(risk_payload.get("risk_state", "NORMAL")),
        "gate_status": str(risk_payload.get("gate_status", "OPEN")),
        "total_exposure": _number(risk_payload.get("total_exposure")),
        "exposure_utilization_pct": _number(
            risk_payload.get("exposure_utilization_pct")
        ),
        "current_drawdown_pct": _number(
            risk_payload.get("current_drawdown_pct")
        ),
        "max_drawdown_pct": _number(risk_payload.get("max_drawdown_pct")),
        "daily_loss_limit": _number(risk_payload.get("daily_loss_limit")),
        "position_limit": _integer(risk_payload.get("position_limit")),
        "exposure_limit": _number(risk_payload.get("exposure_limit")),
        "risk_limits_breached": _string_list(
            risk_payload.get("risk_limits_breached")
        ),
    }


def governance(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    governance_payload = _mapping(dashboard_payload.get("governance_summary"))
    return {
        "governance_enabled": _boolean(
            governance_payload.get("governance_enabled"),
            default=True,
        ),
        "session_locked": _boolean(governance_payload.get("session_locked")),
        "defensive_mode_active": _boolean(
            governance_payload.get("defensive_mode_active")
        ),
        "unified_trade_gate_active": _boolean(
            governance_payload.get("unified_trade_gate_active"),
            default=True,
        ),
        "audit_enabled": _boolean(
            governance_payload.get("audit_enabled"),
            default=True,
        ),
        "last_governance_event": str(
            governance_payload.get("last_governance_event", "")
        ),
    }


def market(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    market_payload = _mapping(dashboard_payload.get("market_summary"))
    defaults = {
        "trend_state": "UNKNOWN",
        "volatility_state": "UNKNOWN",
        "liquidity_state": "UNKNOWN",
        "mean_reversion_state": "UNKNOWN",
        "probability_state": "UNKNOWN",
        "velocity_state": "UNKNOWN",
        "vwap_state": "UNKNOWN",
        "momentum_state": "UNKNOWN",
        "pressure_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
        "regime_state": "UNKNOWN",
        "spread_state": "UNKNOWN",
        "execution_cost_state": "UNKNOWN",
        "signal_confluence_state": "UNKNOWN",
    }
    payload = {
        key: str(market_payload.get(key, value))
        for key, value in defaults.items()
    }
    payload["vwap_distance"] = _number(market_payload.get("vwap_distance"))
    payload["vwap_elasticity"] = _number(market_payload.get("vwap_elasticity"))
    return payload


def execution(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    execution_payload = _mapping(dashboard_payload.get("execution_summary"))
    recent_trades = _execution_history(dashboard_payload)
    return {
        "execution_state": str(execution_payload.get("execution_state", "IDLE")),
        "accepted_trade_count": _integer(
            execution_payload.get("accepted_trade_count")
        ),
        "rejected_trade_count": _integer(
            execution_payload.get("rejected_trade_count")
        ),
        "pending_trade_count": _integer(
            execution_payload.get("pending_trade_count")
        ),
        "total_execution_cost": _number(
            execution_payload.get("total_execution_cost")
        ),
        "slippage_cost": _number(execution_payload.get("slippage_cost")),
        "spread_cost": _number(execution_payload.get("spread_cost")),
        "fee_cost": _number(execution_payload.get("fee_cost")),
        "avg_slippage_bps": _number(execution_payload.get("avg_slippage_bps")),
        "avg_spread_bps": _number(execution_payload.get("avg_spread_bps")),
        "execution_cost_state": str(
            execution_payload.get("execution_cost_state", "UNKNOWN")
        ),
        "last_execution_event": str(
            execution_payload.get("last_execution_event", "")
        ),
        "recent_trade_count": len(recent_trades),
        "recent_trades": recent_trades,
    }


def _execution_history(dashboard_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for item in _list(dashboard_payload.get("execution_history")):
        trade = _mapping(item)
        rows.append(
            {
                "timestamp": str(
                    trade.get(
                        "timestamp",
                        trade.get("created_utc", trade.get("recorded_utc", "")),
                    )
                ),
                "symbol": str(trade.get("symbol", "UNKNOWN")),
                "asset_class": str(trade.get("asset_class", "UNKNOWN")),
                "side": str(trade.get("side", "UNKNOWN")),
                "mode": str(trade.get("mode", "paper")),
                "broker": str(trade.get("broker", "CSS")),
                "status": str(trade.get("status", "UNKNOWN")),
                "qty": _number(trade.get("qty")),
                "amount": _number(trade.get("amount")),
                "execution_cost": _number(
                    trade.get("execution_cost", trade.get("cost", 0.0))
                ),
                "source": str(trade.get("source", "DashboardState")),
            }
        )

    return rows


def opportunities(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_opportunities = dashboard_payload.get("opportunities", [])
    if not isinstance(raw_opportunities, list):
        raw_opportunities = []
    return {
        "items": [_opportunity_item(item) for item in raw_opportunities],
        "count": len(raw_opportunities),
        "source": "DashboardState",
    }


def _opportunity_item(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    return {
        "symbol": str(item.get("symbol", "UNKNOWN")),
        "asset_class": str(item.get("asset_class", "UNKNOWN")),
        "side": str(item.get("side", item.get("direction", "WATCH"))),
        "signal": str(item.get("signal", item.get("signal_state", "WATCH"))),
        "score": _number(item.get("score", item.get("composite_score"))),
        "probability": _number(item.get("probability", item.get("prob", 0.0))),
        "status": str(item.get("status", "MONITOR_ONLY")),
        "reason": str(item.get("reason", item.get("note", ""))),
    }


def broker(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    broker_payload = _mapping(dashboard_payload.get("broker_summary"))
    return {
        "selected_broker": str(broker_payload.get("selected_broker", "NONE")),
        "broker_mode": str(broker_payload.get("broker_mode", "paper")),
        "connected": _boolean(broker_payload.get("connected")),
        "live_trading_enabled": _boolean(
            broker_payload.get("live_trading_enabled")
        ),
        "last_heartbeat": str(broker_payload.get("last_heartbeat", "")),
        "api_health": str(broker_payload.get("api_health", "UNKNOWN")),
        "reconnect_state": str(broker_payload.get("reconnect_state", "NONE")),
        "supported_assets": _string_list(broker_payload.get("supported_assets")),
        "account_readiness": str(
            broker_payload.get("account_readiness", "UNKNOWN")
        ),
        "missing_credentials": _boolean(
            broker_payload.get("missing_credentials")
        ),
        "latency_ms": _number(broker_payload.get("latency_ms")),
        "readiness_status": str(
            broker_payload.get("readiness_status", "BROKER_BLOCKED")
        ),
        "readiness_reasons": _string_list(
            broker_payload.get("readiness_reasons")
        ),
    }


def build_section_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
    section: str,
) -> dict[str, Any]:
    payload = build_frontend_payload(dashboard_state)
    sections = _mapping(payload.get("sections"))
    return {
        "payload_version": payload["payload_version"],
        "payload_schema": payload["payload_schema"],
        "generated_at": payload["generated_at"],
        "section": section,
        "data": sections.get(section, {}),
    }


def build_websocket_delta(
    previous_payload: Mapping[str, Any] | None,
    current_payload: Mapping[str, Any],
    *,
    sequence: int = 0,
    sections: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    previous_sections = _mapping((previous_payload or {}).get("sections"))
    current_sections = _mapping(current_payload.get("sections"))
    sections_to_scan = sections or FRONTEND_SECTIONS
    changed_sections = [
        section
        for section in sections_to_scan
        if previous_sections.get(section) != current_sections.get(section)
    ]
    data = {
        section: current_sections.get(section, {})
        for section in changed_sections
    }

    return WebsocketDelta(
        message_type="dashboard_delta",
        payload_version=FRONTEND_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        changed_sections=changed_sections,
        data=data,
        sequence=sequence,
    ).as_dict()


def _dashboard_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(dashboard_state, DashboardState):
        return dashboard_state.to_dict()
    if isinstance(dashboard_state, Mapping):
        return _json_safe(dict(dashboard_state))
    return DashboardState().to_dict()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _integer(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _boolean(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED"
                if _is_sensitive_key(str(key))
                else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    safe_metadata_keys = {
        "secrets_redacted",
        "credentials_redacted",
        "missing_credentials",
    }

    if normalized in safe_metadata_keys:
        return False

    sensitive_fragments = (
        "api_key",
        "access_key",
        "private_key",
        "secret",
        "token",
        "password",
        "passphrase",
        "credential",
        "pem",
        "authorization",
        "bearer",
        "oauth",
        "session_cookie",
    )
    return normalized == "key" or any(
        fragment in normalized for fragment in sensitive_fragments
    )


__all__ = [
    "FRONTEND_CONTRACT_SCHEMA",
    "FRONTEND_CONTRACT_VERSION",
    "FRONTEND_SECTIONS",
    "FrontendEnvelope",
    "WebsocketDelta",
    "account_summary",
    "broker",
    "build_frontend_payload",
    "build_section_payload",
    "build_websocket_delta",
    "execution",
    "governance",
    "market",
    "opportunities",
    "pnl_summary",
    "positions",
    "risk",
]
