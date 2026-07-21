"""Questrade onboarding, read-only readiness, and certification."""

from __future__ import annotations

from enum import Enum
import os
from typing import Any, Mapping

from backend.brokers.questrade.capability import questrade_capability_descriptor
from backend.brokers.questrade.configuration import QuestradeSecureConfiguration
from backend.brokers.questrade.token_lifecycle import TokenLifecycle


class QuestradeOnboardingState(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
    TOKEN_AVAILABLE = "TOKEN_AVAILABLE"
    TOKEN_REFRESH_REQUIRED = "TOKEN_REFRESH_REQUIRED"
    AUTHENTICATING = "AUTHENTICATING"
    AUTHENTICATED = "AUTHENTICATED"
    ACCOUNT_SELECTION_REQUIRED = "ACCOUNT_SELECTION_REQUIRED"
    READ_ONLY_VALIDATION_REQUIRED = "READ_ONLY_VALIDATION_REQUIRED"
    READ_ONLY_READY = "READ_ONLY_READY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


def questrade_advisory_readiness(
    *,
    probe_env: bool = True,
    configuration: QuestradeSecureConfiguration | None = None,
    tokens: TokenLifecycle | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Readiness without initiating network auth or reading secret values into logs."""
    caps = questrade_capability_descriptor()
    config = configuration or (
        QuestradeSecureConfiguration.from_environment_presence() if probe_env else QuestradeSecureConfiguration()
    )
    config_check = config.validate()
    present_keys: list[str] = []
    missing_keys: list[str] = []
    if probe_env:
        for key in caps["credential_env_keys"]:
            # Presence only — never capture values
            if os.environ.get(key):
                present_keys.append(key)
            else:
                missing_keys.append(key)

    token_status = (tokens or TokenLifecycle()).status()
    token_state = str(token_status.get("state") or "")
    proof = dict(evidence or {})
    account_count = int(proof.get("account_count") or 0)
    selected = bool(proof.get("selected_account"))
    required_checks = {
        "api_server_valid": bool(proof.get("api_server_valid")),
        "balances_fresh": bool(proof.get("balances_fresh")),
        "holdings_fresh": bool(proof.get("holdings_fresh")),
        "quotes_fresh": bool(proof.get("quotes_fresh")),
        "option_chain_ready": bool(proof.get("option_chain_ready")),
        "read_only_allowlist_active": bool(proof.get("read_only_allowlist_active", True)),
        "write_methods_blocked": not bool(proof.get("write_methods_exposed")),
        "execution_authority_blocked": not bool(proof.get("execution_authority")),
        "micro_pilot_disarmed": not bool(proof.get("micro_pilot_armed")),
    }
    if not config_check["valid"] or not config_check["token_reference_present"]:
        state = QuestradeOnboardingState.CONFIGURATION_REQUIRED
    elif token_state in {"CREDENTIALS_REQUIRED", "AUTHENTICATION_REQUIRED"}:
        state = QuestradeOnboardingState.AUTHORIZATION_REQUIRED
    elif token_state in {"TOKEN_EXPIRED", "TOKEN_REFRESH_REQUIRED"}:
        state = QuestradeOnboardingState.TOKEN_REFRESH_REQUIRED
    elif token_state != "AUTHENTICATED":
        state = QuestradeOnboardingState.AUTHENTICATING
    elif account_count < 1 or not selected:
        state = QuestradeOnboardingState.ACCOUNT_SELECTION_REQUIRED
    elif not all(required_checks.values()):
        state = QuestradeOnboardingState.READ_ONLY_VALIDATION_REQUIRED
    else:
        state = QuestradeOnboardingState.READ_ONLY_READY
    return {
        "broker": "QUESTRADE",
        "state": state.value,
        "adapter_state": state.value,
        "authentication_activated": False,
        "authorization_state": token_state,
        "token_health": token_status,
        "health": "READ_ONLY_READY" if state is QuestradeOnboardingState.READ_ONLY_READY else "NOT_CONNECTED",
        "credential_keys_present": present_keys,
        "credential_keys_missing": missing_keys,
        "secure_configuration": config.sanitized_summary(),
        "account_count": account_count,
        "selected_account": "MASKED_REFERENCE_PRESENT" if selected else None,
        "validation_checks": required_checks,
        "network_probe_performed": False,
        "listed_equity_options_capability": True,
        "order_submission": "BLOCKED",
        "advisory_only": True,
        "execution_allowed": False,
        "certification_hook": "options_income_advisory_data",
        "capability": caps,
        "provenance": "CONFIGURATION",
    }


def questrade_read_only_certification(readiness: Mapping[str, Any]) -> dict[str, Any]:
    state = str(readiness.get("state") or QuestradeOnboardingState.CONFIGURATION_REQUIRED.value)
    outcome = {
        "CONFIGURATION_REQUIRED": "CONFIGURATION_REQUIRED",
        "AUTHORIZATION_REQUIRED": "AUTHORIZATION_REQUIRED",
        "TOKEN_REFRESH_REQUIRED": "AUTHORIZATION_REQUIRED",
        "ACCOUNT_SELECTION_REQUIRED": "ACCOUNT_SELECTION_REQUIRED",
        "READ_ONLY_VALIDATION_REQUIRED": "PARTIALLY_READY",
        "READ_ONLY_READY": "CERTIFIED_ADVISORY",
        "DEGRADED": "DEGRADED",
        "FAILED": "FAILED",
    }.get(state, "DATA_DEPENDENCY_BLOCKED")
    return {
        "broker": "QUESTRADE",
        "outcome": outcome,
        "readiness_state": state,
        "read_only_certified": outcome == "CERTIFIED_ADVISORY",
        "live_ready": False,
        "execution_certified": False,
        "execution_allowed": False,
        "micro_pilot_armed": False,
        "network_probe_performed": False,
        "required_action": _recommended_action(state),
        "provenance": "QUESTRADE_READ_ONLY_CERTIFICATION",
    }


def _recommended_action(state: str) -> str:
    return {
        "CONFIGURATION_REQUIRED": "Configure approved secret-store references",
        "AUTHORIZATION_REQUIRED": "Complete separately authorized Questrade OAuth onboarding",
        "TOKEN_REFRESH_REQUIRED": "Authorize one bounded token refresh",
        "ACCOUNT_SELECTION_REQUIRED": "Select one approved masked account",
        "READ_ONLY_VALIDATION_REQUIRED": "Validate balances, holdings, quotes, and option chains",
        "READ_ONLY_READY": "Maintain read-only monitoring; execution remains blocked",
    }.get(state, "Review sanitized Questrade diagnostics")


__all__ = [
    "QuestradeOnboardingState",
    "questrade_advisory_readiness",
    "questrade_read_only_certification",
]
