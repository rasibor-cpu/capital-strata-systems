from __future__ import annotations

from typing import Any, Mapping

from backend.runtime.canonical_broker_runtime_state import (
    OVERALL_GREEN,
    STATUS_PASS,
    CanonicalBrokerRuntimeState,
)
from backend.runtime.canonical_broker_state_builder import canonical_state_from_payload


def adapt_canonical_state_to_legacy_broker_payload(
    state: CanonicalBrokerRuntimeState | Mapping[str, Any],
    *,
    base_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = state if isinstance(state, CanonicalBrokerRuntimeState) else canonical_state_from_payload(state)
    base = dict(base_payload or {})
    account_snapshot = dict(canonical.account_snapshot) if isinstance(canonical.account_snapshot, Mapping) else {}
    balances_loaded = account_snapshot.get("balances_loaded") is True
    payload = {
        **base,
        "canonical_broker_runtime_state": canonical.to_dict(),
        "canonical_account_snapshot": account_snapshot,
        "account_snapshot": account_snapshot,
        "selected_broker": canonical.broker,
        "broker": canonical.broker,
        "broker_mode": canonical.mode,
        "credential_status": "PRESENT" if canonical.credential_status == STATUS_PASS else canonical.credential_status,
        "transport_status": "REACHABLE" if canonical.transport_status == STATUS_PASS else canonical.transport_status,
        "authentication_status": "AUTHENTICATED" if canonical.authentication_status == STATUS_PASS else canonical.authentication_status,
        "auth_status": "AUTHENTICATED" if canonical.authentication_status == STATUS_PASS else "NOT_AUTHENTICATED",
        "broker_authenticated": canonical.authentication_status == STATUS_PASS,
        "authenticated": canonical.authentication_status == STATUS_PASS,
        "connection_status": "CONNECTED" if canonical.connection_status == STATUS_PASS else canonical.connection_status,
        "broker_connected": canonical.connection_status == STATUS_PASS,
        "connected": canonical.connection_status == STATUS_PASS,
        "account_data_health": "READY" if canonical.account_status == STATUS_PASS else canonical.account_status,
        "balance_position_status": "OK" if canonical.balance_status == STATUS_PASS else canonical.balance_status,
        "market_data_status": "OK" if canonical.market_data_status == STATUS_PASS else canonical.market_data_status,
        "product_price_status": "OK" if canonical.product_status == STATUS_PASS else canonical.product_status,
        "broker_health": canonical.overall_status,
        "readiness_state": canonical.readiness_state,
        "readiness_score": canonical.readiness_score,
        "go_no_go": "GO" if canonical.overall_status == OVERALL_GREEN else "NO GO",
        "execution_scope": canonical.execution_scope,
        "order_submission_status": canonical.order_submission_status,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        "can_live_execute": False,
        "broker_execution_status": "DISABLED",
        "live_micro_pilot_state": canonical.pilot_state,
        "authority_reason": canonical.failure_reason or "Broker Execution Disabled",
        "connection_error": canonical.failure_reason,
        "http_status": canonical.http_status,
        "error_code": canonical.error_code,
        "failure_reason": canonical.failure_reason,
        "warning_reasons": list(canonical.warning_reasons),
        "environment_diagnostics": dict(canonical.environment_evidence),
        "broker_environment_profile": dict(canonical.environment_evidence),
        "profile": dict(canonical.environment_evidence).get("profile", "UNSELECTED"),
        "environment": dict(canonical.environment_evidence).get("environment", canonical.mode),
        "permissions_classification": dict(canonical.environment_evidence).get("permissions_classification", "UNKNOWN"),
        "profile_fingerprint": dict(canonical.environment_evidence).get("profile_fingerprint", ""),
        "contamination_status": dict(canonical.environment_evidence).get("status", "UNKNOWN"),
        "account_evidence": dict(canonical.account_evidence),
        "status_provenance": dict(canonical.status_provenance),
        "state_hash": canonical.stable_hash(),
    }
    if account_snapshot:
        payload["account_loaded"] = account_snapshot.get("account_loaded", canonical.account_status == STATUS_PASS)
        payload["balances_loaded"] = balances_loaded
        payload["portfolio_loaded"] = account_snapshot.get("portfolio_loaded", False)
        payload["market_data_loaded"] = account_snapshot.get("market_data_loaded", canonical.market_data_status == STATUS_PASS)
        payload["currency"] = account_snapshot.get("currency", base.get("currency"))
        if balances_loaded:
            payload["account_equity"] = account_snapshot.get("equity")
            payload["cash"] = account_snapshot.get("cash")
            payload["buying_power"] = account_snapshot.get("buying_power")
            payload["available_balance"] = account_snapshot.get("available_balance")
            payload["margin_available"] = account_snapshot.get("margin_available")
        elif canonical.mode == "live":
            payload["account_equity"] = None
            payload["cash"] = None
            payload["buying_power"] = None
            payload["available_balance"] = None
            payload["margin_available"] = None
    return payload


def adapt_legacy_payload_to_canonical_state(payload: Mapping[str, Any] | None = None) -> CanonicalBrokerRuntimeState:
    return canonical_state_from_payload(payload or {})


__all__ = [
    "adapt_canonical_state_to_legacy_broker_payload",
    "adapt_legacy_payload_to_canonical_state",
]
