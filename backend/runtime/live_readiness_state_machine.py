from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.runtime.broker_readiness_framework import build_broker_readiness_snapshot

LIVE_READINESS_STATES = (
    "NOT_INITIALIZED",
    "CREDENTIALS_PRESENT",
    "CLIENT_CREATED",
    "TRANSPORT_CONNECTED",
    "AUTHENTICATED",
    "ACCOUNT_ACCESSIBLE",
    "ACCOUNT_DATA_AVAILABLE",
    "MARKET_DATA_AVAILABLE",
    "FULLY_OPERATIONAL",
)

READ_ONLY_READY_STATES = {"FULLY_OPERATIONAL"}


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

    state = "NOT_INITIALIZED"
    if diagnostics["credentials"] == "PRESENT":
        state = "CREDENTIALS_PRESENT"
    if state == "CREDENTIALS_PRESENT" and diagnostics.get("client_created", True):
        state = "CLIENT_CREATED"
    if state == "CLIENT_CREATED" and diagnostics["connected"]:
        state = "TRANSPORT_CONNECTED"
    # Authentication becomes PASS only after authenticated account evidence exists
    if state == "TRANSPORT_CONNECTED" and diagnostics["authenticated"] and diagnostics["account_loaded"]:
        state = "AUTHENTICATED"
    if state == "AUTHENTICATED" and diagnostics["account_loaded"]:
        state = "ACCOUNT_ACCESSIBLE"
    
    has_account_data = diagnostics["account_loaded"] and diagnostics.get("account_balance") is not None
    if state == "ACCOUNT_ACCESSIBLE" and has_account_data:
        state = "ACCOUNT_DATA_AVAILABLE"
    if state == "ACCOUNT_DATA_AVAILABLE" and diagnostics["market_data"] == "READY":
        state = "MARKET_DATA_AVAILABLE"
    if state == "MARKET_DATA_AVAILABLE" and _read_only_safety_intact(diagnostics):
        state = "FULLY_OPERATIONAL"

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
    broker_readiness_source = data.get("broker_readiness") if isinstance(data.get("broker_readiness"), Mapping) else data
    readiness = build_broker_readiness_snapshot(broker_readiness_source)
    diagnostics = data.get("credential_diagnostics") if isinstance(data.get("credential_diagnostics"), Mapping) else {}
    credential_diag = (
        data.get("broker_credential_diagnostics")
        if isinstance(data.get("broker_credential_diagnostics"), Mapping)
        else diagnostics.get("broker_credential_diagnostics")
        if isinstance(diagnostics.get("broker_credential_diagnostics"), Mapping)
        else diagnostics
    )
    credential_status = str(
        data.get("credential_status")
        or (credential_diag.get("credential_status") if isinstance(credential_diag, Mapping) else "")
        or diagnostics.get("credential_status")
        or ""
    ).strip().upper()
    credentials_present = readiness.credentials_present or credential_status in {"PRESENT", "PASS", "READY"} or (
        isinstance(credential_diag, Mapping) and bool(credential_diag.get("credentials_present"))
    )
    credentials = "PRESENT" if credentials_present else ("MISSING" if credential_status in {"MISSING", "FAIL", "FAILED"} else (credential_status or "MISSING"))
    operator_requested_live = _truthy(data.get("operator_requested_live", False))
    execution_enabled = readiness.execution_enabled
    can_live_execute = _truthy(data.get("can_live_execute", False)) and execution_enabled
    authenticated = readiness.authenticated
    connected = readiness.connected
    products_loaded = readiness.products_loaded
    market_data_status = str(data.get("market_data_status", data.get("product_price_status", "NOT_TESTED"))).strip().upper()
    account_status = str(data.get("balance_position_status", data.get("account_read_status", ""))).strip().upper()
    account_loaded = readiness.account_loaded or account_status in {"OK", "PASS", "READY", "AVAILABLE"}
    market_ready = readiness.market_data_ready or (products_loaded > 0 and market_data_status in {"OK", "PASS", "READY", "AVAILABLE"})
    timestamp = str(data.get("timestamp") or datetime.now(timezone.utc).isoformat())
    pilot_state = str(data.get("live_micro_pilot_state", data.get("pilot_state", "DISARMED")) or "DISARMED").upper()
    broker_guard = str(data.get("broker_guard", data.get("broker_submission_guard", "REJECT_BEFORE_BROKER")) or "REJECT_BEFORE_BROKER")
    auth_attempted = _truthy(data.get("authentication_attempted")) or (
        isinstance(credential_diag, Mapping) and _truthy(credential_diag.get("authentication_attempted"))
    )
    if authenticated:
        authentication_status = "AUTHENTICATED"
    elif auth_attempted or operator_requested_live:
        authentication_status = str(data.get("auth_status", data.get("authentication_status", "NOT_AUTHENTICATED")))
    else:
        authentication_status = "NOT_TESTED"
    if connected:
        connection_status = "CONNECTED"
    elif auth_attempted or operator_requested_live:
        connection_status = str(data.get("connection_status", "NOT_CONNECTED"))
    else:
        connection_status = "NOT_TESTED"
    recommended_action = str(
        data.get("recommended_action")
        or (credential_diag.get("recommended_action") if isinstance(credential_diag, Mapping) else "")
        or readiness.authority_block_reason
        or ""
    )
    if credentials_present and "configure" in recommended_action.lower() and "credential" in recommended_action.lower():
        recommended_action = "No credential remediation required"
    if credentials_present and not recommended_action:
        recommended_action = "No credential remediation required"
    return {
        "broker": readiness.broker_name,
        "broker_mode": readiness.mode,
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
        "client_created": _truthy(data.get("client_created", True)),
        "account_balance": readiness.account_balance or readiness.equity or data.get("cash") or data.get("account_balance") or data.get("balance") or data.get("equity") or data.get("account_equity"),
        "market_data": "READY" if market_ready else market_data_status,
        "account_loaded": account_loaded,
        "products_loaded": products_loaded,
        "broker_guard": broker_guard,
        "broker_infrastructure_health": readiness.broker_health,
        "broker_ready": bool(readiness.credentials_present and readiness.authenticated and readiness.connected and readiness.account_loaded and readiness.market_data_ready),
        "readiness_score": readiness.readiness_score,
        "credential_status": credentials,
        "authentication_status": authentication_status,
        "connection_status": connection_status,
        "recommended_action": recommended_action,
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
