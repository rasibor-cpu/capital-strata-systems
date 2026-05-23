from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from dashboard.runtime.dashboard_state import (
    DASHBOARD_PAYLOAD_SCHEMA,
    DASHBOARD_PAYLOAD_VERSION,
    DashboardState,
)
from dashboard.runtime.broker_balance_reconciliation import (
    build_broker_reconciliation_payload,
)


FRONTEND_CONTRACT_VERSION = "1.0.0"
FRONTEND_CONTRACT_SCHEMA = "css.frontend.contract.v1"

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
    "broker_reconciliation",
    "operational_identity",
    "pilot_safety",
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


def build_frontend_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
) -> dict[str, Any]:
    dashboard_payload = _dashboard_payload(dashboard_state)
    envelope = FrontendEnvelope()

    return _json_safe(
        {
            "payload_version": envelope.payload_version,
            "payload_schema": envelope.payload_schema,
            "dashboard_payload_version": envelope.dashboard_payload_version,
            "dashboard_payload_schema": envelope.dashboard_payload_schema,
            "generated_at": envelope.generated_at,
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
                "broker_reconciliation": broker_reconciliation(dashboard_payload),
                "operational_identity": operational_identity(dashboard_payload),
                "pilot_safety": pilot_safety(dashboard_payload),
            },
        }
    )


def pilot_safety(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "live_capital_banner": "LIVE CAPITAL ACTIVE",
        "operational_identity_strip": True,
        "reconciliation_visibility_panel": True,
        "kill_switch_panel": True,
        "live_capital_endpoint": "/api/v1/live-capital-banner",
        "kill_switch_status_endpoint": "/api/v1/web-kill-switch/status",
        "kill_switch_engage_endpoint": "/api/v1/web-kill-switch/engage",
        "operational_identity_endpoint": "/api/v1/operational-identity",
        "session_replay_endpoint": "/api/v1/session-replay-evidence-export",
        "dashboard_visibility": {
            "visible": True,
            "header": "LIVE CAPITAL ACTIVE",
        },
    }


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
    return {
        "total": _integer(open_positions.get("total")),
        "by_asset": {str(k): _integer(v) for k, v in by_asset.items()},
        "items": [],
    }


def pnl_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    pnl = _mapping(dashboard_payload.get("pnl_summary"))
    return {
        "realized_pnl": _number(pnl.get("realized_pnl")),
        "unrealized_pnl": _number(pnl.get("unrealized_pnl")),
        "net_pnl": _number(pnl.get("net_pnl")),
    }


def risk(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    risk_payload = _mapping(dashboard_payload.get("risk_summary"))
    return {
        "risk_state": str(risk_payload.get("risk_state", "NORMAL")),
        "gate_status": str(risk_payload.get("gate_status", "OPEN")),
    }


def governance(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    governance_payload = _mapping(dashboard_payload.get("governance_summary"))
    return {
        "governance_enabled": _boolean(
            governance_payload.get("governance_enabled"),
            default=True,
        ),
        "audit_enabled": _boolean(
            governance_payload.get("audit_enabled"),
            default=True,
        ),
    }


def market(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    market_payload = _mapping(dashboard_payload.get("market_summary"))
    return {
        "regime_state": str(market_payload.get("regime_state", "UNKNOWN")),
    }


def execution(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    execution_payload = _mapping(dashboard_payload.get("execution_summary"))
    return {
        "execution_state": str(execution_payload.get("execution_state", "IDLE")),
    }


def opportunities(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = dashboard_payload.get("opportunities", [])
    if not isinstance(raw, list):
        raw = []
    return {
        "items": raw,
        "count": len(raw),
    }


def broker(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    broker_payload = _mapping(dashboard_payload.get("broker_summary"))
    return {
        "selected_broker": str(broker_payload.get("selected_broker", "NONE")),
        "broker_mode": str(broker_payload.get("broker_mode", "paper")),
    }


def broker_reconciliation(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_broker_reconciliation_payload(dashboard_payload)


def operational_identity(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    payload = _mapping(dashboard_payload.get("operational_identity"))
    return {
        "runtime": str(payload.get("runtime", "CSS_RUNTIME")),
        "mode": str(payload.get("mode", dashboard_payload.get("resolved_mode", "paper"))),
        "status": str(payload.get("status", "ACTIVE")),
        "live_capital_active": _boolean(payload.get("live_capital_active"), default=True),
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
    return {
        "message_type": "dashboard_delta",
        "payload_version": FRONTEND_CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "changed_sections": changed_sections,
        "data": {section: current_sections.get(section, {}) for section in changed_sections},
        "sequence": sequence,
    }


def _dashboard_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(dashboard_state, DashboardState):
        return dashboard_state.to_dict()
    if isinstance(dashboard_state, Mapping):
        return dict(dashboard_state)
    return DashboardState().to_dict()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = [
    "FRONTEND_CONTRACT_SCHEMA",
    "FRONTEND_CONTRACT_VERSION",
    "FRONTEND_SECTIONS",
    "FrontendEnvelope",
    "account_summary",
    "broker",
    "broker_reconciliation",
    "build_frontend_payload",
    "build_section_payload",
    "build_websocket_delta",
    "execution",
    "governance",
    "market",
    "opportunities",
    "operational_identity",
    "pilot_safety",
    "pnl_summary",
    "positions",
    "risk",
]
