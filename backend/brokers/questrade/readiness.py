"""Questrade advisory readiness and health checks."""

from __future__ import annotations

import os
from typing import Any

from backend.brokers.questrade.capability import questrade_capability_descriptor


def questrade_advisory_readiness(*, probe_env: bool = True) -> dict[str, Any]:
    """Readiness without initiating network auth or reading secret values into logs."""
    caps = questrade_capability_descriptor()
    present_keys: list[str] = []
    missing_keys: list[str] = []
    if probe_env:
        for key in caps["credential_env_keys"]:
            # Presence only — never capture values
            if os.environ.get(key):
                present_keys.append(key)
            else:
                missing_keys.append(key)

    configured = len(missing_keys) == 0
    state = "CREDENTIALS_PRESENT_BUT_AUTH_NOT_ACTIVATED" if configured else "CONFIGURATION_REQUIRED"
    return {
        "broker": "QUESTRADE",
        "state": state,
        "adapter_state": "CONFIGURATION_REQUIRED",
        "authentication_activated": False,
        "health": "NOT_CONNECTED",
        "credential_keys_present": present_keys,
        "credential_keys_missing": missing_keys,
        "network_probe_performed": False,
        "listed_equity_options_capability": True,
        "order_submission": "BLOCKED",
        "advisory_only": True,
        "execution_allowed": False,
        "certification_hook": "options_income_advisory_data",
        "capability": caps,
        "provenance": "CONFIGURATION",
    }


__all__ = ["questrade_advisory_readiness"]
