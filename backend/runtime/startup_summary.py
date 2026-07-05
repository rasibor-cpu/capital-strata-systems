from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from backend.runtime.live_execution_authority import evaluate_live_execution_authority
from backend.runtime.live_readiness_state_machine import evaluate_live_readiness_state


STARTUP_SUMMARY_FIELDS = (
    "Broker",
    "Broker Mode",
    "Execution Scope",
    "Operator Requested Live",
    "Execution Authority",
    "Can Live Execute",
    "Authority Reason",
    "Pilot State",
    "Capital Governor",
    "Unified Trade Gate",
    "Margin Gate",
    "AntiBleedGuard",
    "Broker Guard",
    "Credentials",
    "Authentication",
    "Connection",
    "Account Data",
    "Market Data",
    "Readiness State",
    "GO / NO GO",
)


def build_live_startup_summary(
    state: Mapping[str, Any] | None = None,
    *,
    broker_status: Mapping[str, Any] | None = None,
    pilot_status: Mapping[str, Any] | None = None,
    gate_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = dict(state or {})
    broker = dict(broker_status or {})
    pilot = dict(pilot_status or {})
    gates = dict(gate_status or {})
    merged = {
        **source,
        **broker,
        "live_micro_pilot_state": pilot.get("pilot_state", broker.get("live_micro_pilot_state", "DISARMED")),
        "pilot_state": pilot.get("pilot_state", broker.get("live_micro_pilot_state", "DISARMED")),
        "capital_governor": gates.get("capital_governor", broker.get("capital_governor", "PHASE_152A_CAD20_GUARD_ONLY")),
        "unified_trade_gate": gates.get("unified_trade_gate", broker.get("unified_trade_gate", "AUTHORITATIVE_FAIL_CLOSED")),
        "margin_gate": gates.get("margin_gate", broker.get("margin_gate", "AUTHORITATIVE_FAIL_CLOSED")),
        "anti_bleed_guard": gates.get("anti_bleed_guard", broker.get("anti_bleed_guard", "AUTHORITATIVE_FAIL_CLOSED")),
        "kill_switch": gates.get("kill_switch", broker.get("kill_switch", "AUTHORITATIVE_FAIL_CLOSED")),
        "rbac": gates.get("rbac", broker.get("rbac", "AUTHORITATIVE_FAIL_CLOSED")),
    }
    readiness = evaluate_live_readiness_state(merged)
    readiness_payload = readiness.as_dict()
    diagnostics = readiness_payload["startup_diagnostics"]

    operator_requested = _truthy(source.get("operator_requested_live", broker.get("operator_requested_live", False)))
    broker_execution_enabled = _truthy(source.get("broker_execution_enabled", broker.get("broker_execution_enabled", False)))
    authority_input = {
        **merged,
        **diagnostics,
        "operator_requested_live": operator_requested,
        "broker_execution_enabled": broker_execution_enabled,
        "go_no_go": readiness.go_no_go,
    }
    authority = evaluate_live_execution_authority(authority_input)
    authority_payload = authority.as_dict()
    can_live_execute = authority.execution_authority

    summary = {
        "Broker": diagnostics["broker"],
        "Broker Mode": diagnostics["broker_mode"],
        "Execution Scope": diagnostics["execution_scope"],
        "Operator Requested Live": "YES" if authority.operator_requested_live else "NO",
        "Execution Authority": "YES" if authority.execution_authority else "NO",
        "Can Live Execute": "YES" if can_live_execute else "NO",
        "Authority Reason": authority.authority_reason,
        "Pilot State": diagnostics["pilot_state"],
        "Capital Governor": str(merged.get("capital_governor", "PHASE_152A_CAD20_GUARD_ONLY")),
        "Unified Trade Gate": str(merged.get("unified_trade_gate", "AUTHORITATIVE_FAIL_CLOSED")),
        "Margin Gate": str(merged.get("margin_gate", "AUTHORITATIVE_FAIL_CLOSED")),
        "AntiBleedGuard": str(merged.get("anti_bleed_guard", "AUTHORITATIVE_FAIL_CLOSED")),
        "Broker Guard": diagnostics["broker_guard"],
        "Credentials": diagnostics["credential_status"],
        "Authentication": diagnostics["authentication_status"],
        "Connection": diagnostics["connection_status"],
        "Account Data": "READY" if diagnostics["account_loaded"] else "NOT_READY",
        "Market Data": diagnostics["market_data"],
        "Readiness State": readiness.readiness_state,
        "GO / NO GO": readiness.go_no_go,
        "execution_allowed": False,
        "advisory_only": True,
        "broker_execution_status": "ENABLED" if authority.execution_authority else "DISABLED",
        "operator_requested_live": authority.operator_requested_live,
        "execution_authority": authority.execution_authority,
        "authority_reason": authority.authority_reason,
        "live_authority_state": authority.live_authority_state,
        "live_execution_authority": authority_payload,
        "can_live_execute": can_live_execute,
        "readiness_state": readiness.readiness_state,
        "go_no_go": readiness.go_no_go,
        "readiness_checklist": readiness_payload["readiness_checklist"],
        "startup_diagnostics": {
            **diagnostics,
            "operator_requested_live": authority.operator_requested_live,
            "execution_enabled": authority.execution_authority,
            "broker_execution_enabled": broker_execution_enabled,
            "execution_authority": authority.execution_authority,
            "authority_reason": authority.authority_reason,
            "live_authority_state": authority.live_authority_state,
            "can_live_execute": can_live_execute,
            "timestamp": diagnostics.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        },
    }
    return summary


def format_live_startup_summary(summary: Mapping[str, Any]) -> list[str]:
    lines = ["========== LIVE STARTUP SUMMARY =========="]
    for field in STARTUP_SUMMARY_FIELDS:
        lines.append(f"{field}: {summary.get(field, 'DATA UNAVAILABLE')}")
    lines.append("=========================================")
    return lines


def publish_startup_diagnostics(path: str | Path, summary: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = dict(summary.get("startup_diagnostics", {})) if isinstance(summary.get("startup_diagnostics"), Mapping) else {}
    if not diagnostics:
        diagnostics = build_live_startup_summary(summary).get("startup_diagnostics", {})
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(diagnostics, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return diagnostics


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "armed", "connected", "authenticated", "pass", "ok", "green", "healthy"}


__all__ = [
    "STARTUP_SUMMARY_FIELDS",
    "build_live_startup_summary",
    "format_live_startup_summary",
    "publish_startup_diagnostics",
]
