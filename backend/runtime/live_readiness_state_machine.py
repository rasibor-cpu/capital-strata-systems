from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


LIVE_READINESS_STATES = (
    "UNCONFIGURED",
    "CREDENTIALS_PRESENT",
    "AUTHENTICATED",
    "CONNECTED",
    "ACCOUNT_DATA_READY",
    "MARKET_DATA_READY",
    "READ_ONLY_READY",
    "LIVE_VALIDATED",
)

READ_ONLY_READY_STATES = {"READ_ONLY_READY", "LIVE_VALIDATED"}


@dataclass(frozen=True)
class ReadinessChecklistItem:
    label: str
    passed: bool
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiveReadinessState:
    readiness_state: str
    go_no_go: str
    checklist: tuple[ReadinessChecklistItem, ...] = field(default_factory=tuple)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "readiness_state": self.readiness_state,
            "go_no_go": self.go_no_go,
            "readiness_checklist": [item.as_dict() for item in self.checklist],
            "startup_diagnostics": dict(self.diagnostics),
        }


def evaluate_live_readiness_state(evidence: Mapping[str, Any] | None) -> LiveReadinessState:
    data = evidence if isinstance(evidence, Mapping) else {}
    diagnostics = _startup_diagnostics(data)
    checklist = _readiness_checklist(diagnostics)

    state = "UNCONFIGURED"
    if diagnostics["credentials"] == "PRESENT":
        state = "CREDENTIALS_PRESENT"
    if state == "CREDENTIALS_PRESENT" and diagnostics["authenticated"]:
        state = "AUTHENTICATED"
    if state == "AUTHENTICATED" and diagnostics["connected"]:
        state = "CONNECTED"
    if state == "CONNECTED" and diagnostics["account_loaded"]:
        state = "ACCOUNT_DATA_READY"
    if state == "ACCOUNT_DATA_READY" and diagnostics["market_data"] == "READY":
        state = "MARKET_DATA_READY"
    if state == "MARKET_DATA_READY" and _read_only_safety_intact(diagnostics):
        state = "READ_ONLY_READY"
    if state == "READ_ONLY_READY" and _truthy(data.get("live_validated", False)):
        state = "LIVE_VALIDATED"

    diagnostics["readiness_state"] = state
    diagnostics["go_no_go"] = "GO" if state in READ_ONLY_READY_STATES else "NO GO"
    return LiveReadinessState(
        readiness_state=state,
        go_no_go=str(diagnostics["go_no_go"]),
        checklist=tuple(checklist),
        diagnostics=diagnostics,
    )


def publish_live_readiness_state(
    path: str | Path,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    state = evaluate_live_readiness_state(evidence).as_dict()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return state


def _startup_diagnostics(data: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = data.get("credential_diagnostics") if isinstance(data.get("credential_diagnostics"), Mapping) else {}
    credential_status = str(
        data.get("credential_status")
        or diagnostics.get("credential_status")
        or "MISSING"
    ).strip().upper()
    credentials = "PRESENT" if credential_status in {"PRESENT", "PASS", "READY"} else "MISSING"
    operator_requested_live = _truthy(data.get("operator_requested_live", False))
    execution_enabled = _truthy(data.get("execution_authority", data.get("execution_enabled", False)))
    can_live_execute = _truthy(data.get("can_live_execute", False)) and execution_enabled
    authenticated = _truthy(data.get("broker_authenticated", data.get("authenticated", False)))
    connected = _truthy(data.get("broker_connected", data.get("connected", False)))
    products_loaded = _int(data.get("products_loaded", 0))
    market_data_status = str(data.get("market_data_status", data.get("product_price_status", "NOT_TESTED"))).strip().upper()
    account_status = str(data.get("balance_position_status", data.get("account_read_status", ""))).strip().upper()
    account_loaded = (
        _value_present(data.get("account_equity"))
        or _value_present(data.get("cash"))
        or _value_present(data.get("available_balance"))
        or account_status in {"OK", "PASS", "READY", "AVAILABLE"}
    )
    market_ready = products_loaded > 0 and market_data_status in {"OK", "PASS", "READY", "AVAILABLE"}
    timestamp = str(data.get("timestamp") or datetime.now(timezone.utc).isoformat())
    pilot_state = str(data.get("live_micro_pilot_state", data.get("pilot_state", "DISARMED")) or "DISARMED").upper()
    broker_guard = str(data.get("broker_guard", data.get("broker_submission_guard", "REJECT_BEFORE_BROKER")) or "REJECT_BEFORE_BROKER")
    return {
        "broker": str(data.get("selected_broker", data.get("broker", "NONE")) or "NONE"),
        "broker_mode": str(data.get("broker_mode", "paper") or "paper"),
        "execution_scope": str(data.get("execution_scope", "PAPER_OR_NOT_SELECTED") or "PAPER_OR_NOT_SELECTED"),
        "operator_requested_live": operator_requested_live,
        "execution_enabled": execution_enabled,
        "execution_authority": execution_enabled,
        "authority_reason": str(data.get("authority_reason", "")),
        "live_authority_state": str(data.get("live_authority_state", "BLOCKED")),
        "can_live_execute": can_live_execute,
        "pilot_state": pilot_state,
        "capital_governor": str(data.get("capital_governor", "PHASE_152A_CAD20_GUARD_ONLY")),
        "credentials": credentials,
        "authenticated": authenticated,
        "connected": connected,
        "market_data": "READY" if market_ready else market_data_status,
        "account_loaded": account_loaded,
        "products_loaded": products_loaded,
        "broker_guard": broker_guard,
        "broker_infrastructure_health": str(data.get("broker_health", "UNKNOWN")),
        "credential_status": credentials,
        "authentication_status": "AUTHENTICATED" if authenticated else str(data.get("auth_status", "NOT_AUTHENTICATED")),
        "connection_status": "CONNECTED" if connected else str(data.get("connection_status", "NOT_CONNECTED")),
        "last_broker_sync": str(data.get("last_broker_sync", data.get("last_successful_sync", "DATA UNAVAILABLE"))),
        "timestamp": timestamp,
    }


def _readiness_checklist(diagnostics: Mapping[str, Any]) -> list[ReadinessChecklistItem]:
    return [
        ReadinessChecklistItem("Startup completed", True),
        ReadinessChecklistItem("Broker selected", str(diagnostics.get("broker", "NONE")).upper() != "NONE"),
        ReadinessChecklistItem("Broker mode selected", bool(str(diagnostics.get("broker_mode", "")).strip())),
        ReadinessChecklistItem("Execution disabled", not bool(diagnostics.get("execution_enabled"))),
        ReadinessChecklistItem("Pilot disarmed", str(diagnostics.get("pilot_state", "")).upper() == "DISARMED"),
        ReadinessChecklistItem("Orders blocked", str(diagnostics.get("broker_guard", "")).upper() == "REJECT_BEFORE_BROKER"),
        ReadinessChecklistItem("Credentials present", diagnostics.get("credentials") == "PRESENT"),
        ReadinessChecklistItem("Authentication", bool(diagnostics.get("authenticated"))),
        ReadinessChecklistItem("Broker connection", bool(diagnostics.get("connected"))),
        ReadinessChecklistItem("Account balances", bool(diagnostics.get("account_loaded"))),
        ReadinessChecklistItem("Market data", diagnostics.get("market_data") == "READY"),
    ]


def _read_only_safety_intact(diagnostics: Mapping[str, Any]) -> bool:
    return (
        not bool(diagnostics.get("execution_enabled"))
        and not bool(diagnostics.get("can_live_execute"))
        and str(diagnostics.get("pilot_state", "")).upper() == "DISARMED"
        and str(diagnostics.get("broker_guard", "")).upper() == "REJECT_BEFORE_BROKER"
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "connected", "authenticated", "pass", "ok", "green", "healthy"}


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().upper() not in {"", "DATA UNAVAILABLE", "NONE", "NULL"}
    return True


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "LIVE_READINESS_STATES",
    "LiveReadinessState",
    "ReadinessChecklistItem",
    "evaluate_live_readiness_state",
    "publish_live_readiness_state",
]
