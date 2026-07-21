"""Questrade capability and canonical operational-state plugin."""

from __future__ import annotations

from typing import Any

from backend.app.brokers.operational_adapter import QuestradeOperationalAdapter
from backend.brokers.questrade.advisory_adapter import QuestradeAdvisoryAdapter
from backend.brokers.questrade.capability import questrade_capability_descriptor
from backend.brokers.questrade.readiness import questrade_advisory_readiness


def plugin_info() -> dict[str, Any]:
    caps = questrade_capability_descriptor()
    ready = questrade_advisory_readiness(probe_env=True)
    advisory = QuestradeAdvisoryAdapter()
    operational = QuestradeOperationalAdapter().operational_snapshot()
    return {
        "name": "questrade",
        "display_name": "Questrade",
        "plugin_module": "backend.app.brokers.plugins.questrade",
        "capability": caps,
        "readiness": ready,
        "adapter_state": ready["adapter_state"],
        "operational_adapter_available_via_get_adapter": True,
        "execution_capable": False,
        "executable_via_get_adapter": False,  # deprecated: means order-executable
        "advisory_adapter": "backend.brokers.questrade.QuestradeAdvisoryAdapter",
        "operational_adapter": "backend.app.brokers.operational_adapter.QuestradeOperationalAdapter",
        "operational": operational,
        "capability_states": operational["capability_states"],
        "secure_configuration": advisory.configuration_status(),
        "onboarding": advisory.onboarding_status(),
        "token_health": advisory.token_status(),
        "read_only_certification": advisory.certification(),
        "account_selection": {"selected": False, "masked_identifier": None},
        "read_only_http_allowlist": True,
        "oauth_launch_enabled": False,
        "credential_form_enabled": False,
        "advisory_only": True,
        "execution_allowed": False,
    }


__all__ = ["plugin_info"]
