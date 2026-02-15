"""
Broker Capability Gate
----------------------

Fail-closed protection to prevent routing an asset_class
to a broker/adapter that does not explicitly support it.

Policy:
- adapter_capabilities must be provided
- capability must explicitly be True
- anything missing or malformed => BLOCK
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class BrokerCapabilityDecision:
    decision: str
    reasons: List[str]


class BrokerCapabilityGate:

    def evaluate(self, *, asset_class: str, state: Dict[str, Any]) -> BrokerCapabilityDecision:

        if not isinstance(state, dict):
            return BrokerCapabilityDecision(
                decision="BLOCK",
                reasons=["state_missing_or_invalid"]
            )

        adapter_name = state.get("adapter_name")
        capabilities = state.get("adapter_capabilities")

        if not adapter_name:
            return BrokerCapabilityDecision(
                decision="BLOCK",
                reasons=["adapter_name_missing"]
            )

        if not isinstance(capabilities, dict):
            return BrokerCapabilityDecision(
                decision="BLOCK",
                reasons=["adapter_capabilities_missing_or_invalid"]
            )

        asset_class = str(asset_class).strip().lower()

        # explicit capability check
        supported = capabilities.get(asset_class)

        if supported is True:
            return BrokerCapabilityDecision(
                decision="ALLOW",
                reasons=[f"{asset_class}_supported_by_{adapter_name}"]
            )

        return BrokerCapabilityDecision(
            decision="BLOCK",
            reasons=[f"{asset_class}_not_supported_by_{adapter_name}"]
        )
