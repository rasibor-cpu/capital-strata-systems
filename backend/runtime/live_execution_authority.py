from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from backend.runtime.broker_readiness_framework import build_broker_readiness_snapshot
from backend.runtime.broker_credential_diagnostics import authority_reason_from_diagnostics, diagnostics_payload

AUTHORITY_CONDITIONS = (
    ("operator_requested_live", "Operator Intent Missing"),
    ("credentials_present", "Credentials Missing"),
    ("authenticated", "Authentication Not Verified"),
    ("connected", "Broker Connection Not Verified"),
    ("account_loaded", "Account Data Missing"),
    ("market_data_ready", "Market Data Not Ready"),
    ("broker_execution_enabled", "Broker Execution Disabled"),
    ("live_micro_pilot_armed", "Pilot Disarmed"),
    ("capital_governor_pass", "Capital Governor"),
    ("unified_trade_gate_pass", "Unified Trade Gate"),
    ("margin_gate_pass", "Margin Gate"),
    ("anti_bleed_guard_pass", "AntiBleedGuard"),
    ("rbac_pass", "RBAC"),
    ("kill_switch_clear", "Kill Switch"),
    ("go_no_go_allows", "GO / NO GO"),
)


@dataclass(frozen=True)
class LiveExecutionAuthority:
    operator_requested_live: bool
    execution_authority: bool
    can_live_execute: bool
    live_authority_state: str
    authority_reason: str
    failed_conditions: tuple[str, ...] = field(default_factory=tuple)
    condition_status: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_live_execution_authority(evidence: Mapping[str, Any] | None) -> LiveExecutionAuthority:
    data = evidence if isinstance(evidence, Mapping) else {}
    diagnostics = data.get("startup_diagnostics") if isinstance(data.get("startup_diagnostics"), Mapping) else {}
    broker_readiness_source = data.get("broker_readiness") if isinstance(data.get("broker_readiness"), Mapping) else data
    readiness = build_broker_readiness_snapshot(broker_readiness_source)
    credential_source = data.get("broker_credential_diagnostics")
    if not isinstance(credential_source, Mapping):
        credential_source = data.get("credential_diagnostics") if isinstance(data.get("credential_diagnostics"), Mapping) else {}
    credential_payload = diagnostics_payload(credential_source)
    pilot_state = str(data.get("live_micro_pilot_state") or data.get("pilot_state") or diagnostics.get("pilot_state") or "").upper()
    go_no_go = str(data.get("go_no_go") or diagnostics.get("go_no_go") or "NO GO").upper()

    condition_status = {
        "operator_requested_live": _truthy(data.get("operator_requested_live", False)),
        "credentials_present": readiness.credentials_present,
        "authenticated": readiness.authenticated,
        "connected": readiness.connected,
        "account_loaded": readiness.account_loaded,
        "market_data_ready": readiness.market_data_ready,
        "broker_execution_enabled": readiness.execution_enabled,
        "live_micro_pilot_armed": pilot_state == "ARMED",
        "capital_governor_pass": _pass(data.get("capital_governor", diagnostics.get("capital_governor"))),
        "unified_trade_gate_pass": _pass(data.get("unified_trade_gate", diagnostics.get("unified_trade_gate"))),
        "margin_gate_pass": _pass(data.get("margin_gate", diagnostics.get("margin_gate"))),
        "anti_bleed_guard_pass": _pass(data.get("anti_bleed_guard", data.get("AntiBleedGuard", diagnostics.get("anti_bleed_guard")))),
        "rbac_pass": _pass(data.get("rbac", diagnostics.get("rbac"))),
        "kill_switch_clear": _clear(data.get("kill_switch", diagnostics.get("kill_switch"))),
        "go_no_go_allows": go_no_go != "NO GO",
    }
    failed = tuple(key for key, _reason in AUTHORITY_CONDITIONS if not condition_status.get(key, False))
    authority = not failed
    if authority:
        reason = "Authority Granted"
    elif failed[0] in {"credentials_present", "authenticated"}:
        reason = authority_reason_from_diagnostics(credential_payload)
    else:
        reason = next(reason for key, reason in AUTHORITY_CONDITIONS if key == failed[0])
    return LiveExecutionAuthority(
        operator_requested_live=condition_status["operator_requested_live"],
        execution_authority=authority,
        can_live_execute=authority,
        live_authority_state="AUTHORIZED" if authority else "BLOCKED",
        authority_reason=reason,
        failed_conditions=failed,
        condition_status=condition_status,
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "connected", "authenticated", "pass", "ok", "green", "healthy", "clear"}


def _pass(value: Any) -> bool:
    return str(value or "").strip().upper() in {"PASS", "PASSED", "OK", "GREEN", "CLEAR", "AUTHORIZED"}


def _clear(value: Any) -> bool:
    if value is None or value == "":
        return False
    return str(value).strip().upper() in {"CLEAR", "PASS", "OK", "FALSE", "DISABLED", "NOT_ENGAGED"}


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
    "AUTHORITY_CONDITIONS",
    "LiveExecutionAuthority",
    "evaluate_live_execution_authority",
]
