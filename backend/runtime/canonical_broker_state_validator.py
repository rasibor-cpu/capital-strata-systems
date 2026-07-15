from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from backend.runtime.canonical_broker_runtime_state import (
    OVERALL_CONTRADICTORY,
    OVERALL_FAIL_CLOSED,
    SCHEMA_VERSION,
    STATUS_BLOCKED,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_UNAVAILABLE,
    CanonicalBrokerRuntimeState,
)


def validate_canonical_broker_state(state: CanonicalBrokerRuntimeState | Mapping[str, Any]) -> dict[str, Any]:
    canonical = state if isinstance(state, CanonicalBrokerRuntimeState) else CanonicalBrokerRuntimeState(**dict(state))
    reasons = contradiction_reasons(canonical)
    valid = not reasons and canonical.schema_version == SCHEMA_VERSION
    return {
        "valid": valid,
        "contradictory": bool(reasons),
        "reasons": reasons,
        "overall_status": canonical.overall_status if valid else OVERALL_CONTRADICTORY,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
    }


def contradiction_reasons(state: CanonicalBrokerRuntimeState) -> list[str]:
    reasons: list[str] = []
    if state.schema_version != SCHEMA_VERSION:
        reasons.append("unsupported_schema_version")
    if state.broker not in {"NONE", "COINBASE", "OANDA", "IBKR", "DEMO"}:
        reasons.append("invalid_broker_identity")
    if not _finite(state.readiness_score):
        reasons.append("non_finite_readiness_score")
    if state.latency_ms is not None and not _finite(state.latency_ms):
        reasons.append("non_finite_latency")
    if state.credential_status in {STATUS_FAIL, STATUS_UNAVAILABLE} and state.authentication_status == STATUS_PASS:
        reasons.append("credentials_missing_but_authentication_pass")
    if state.authentication_status == STATUS_FAIL and state.account_status == STATUS_PASS:
        reasons.append("authentication_failed_but_account_ready")
    if state.balance_status == STATUS_UNAVAILABLE and state.margin_status == STATUS_PASS and _positive_live_buying_power(state.environment_evidence):
        reasons.append("balance_unavailable_but_positive_live_margin")
    if state.execution_allowed and state.live_trading_blocked:
        reasons.append("execution_allowed_while_live_trading_blocked")
    if state.broker_execution_armed and str(state.pilot_state).upper() == "DISARMED":
        reasons.append("broker_execution_armed_while_pilot_disarmed")
    if state.mode == "live" and _contamination_present(state.environment_evidence):
        reasons.append("live_mode_environment_contamination")
    if state.order_submission_status == STATUS_PASS and "READ" in state.execution_scope.upper():
        reasons.append("order_submission_enabled_in_read_only_scope")
    if state.environment_evidence.get("positive_simulated_live_margin") is True:
        reasons.append("positive_simulated_live_margin")
    return reasons


def fail_closed_state(state: CanonicalBrokerRuntimeState, reasons: list[str] | tuple[str, ...]) -> CanonicalBrokerRuntimeState:
    contradictory = bool(reasons)
    return state.with_fail_closed(reasons, contradictory=contradictory)


def _contamination_present(evidence: Mapping[str, Any]) -> bool:
    keys = evidence.get("contamination_keys")
    if isinstance(keys, list) and keys:
        return True
    findings = evidence.get("findings")
    return isinstance(findings, list) and any(isinstance(item, Mapping) and item.get("severity") in {"ERROR", "CRITICAL"} for item in findings)


def _positive_live_buying_power(evidence: Mapping[str, Any]) -> bool:
    value = evidence.get("live_buying_power")
    try:
        return value is not None and float(value) > 0
    except (TypeError, ValueError):
        return False


def _finite(value: Any) -> bool:
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


__all__ = [
    "contradiction_reasons",
    "fail_closed_state",
    "validate_canonical_broker_state",
]
