"""
Capital Strata Systems
Broker Capability Gate – Phase 2A

Goal:
Prevent accidental routing of Futures flow into non-futures adapters.

Design:
- Pure python / stdlib only
- Fail-closed by default
- No backend imports
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class CapabilityDecision:
    ok: bool
    decision: str            # "ALLOW" | "BLOCK"
    reasons: List[str]


class BrokerCapabilityGate:
    """
    Gate checks whether the selected adapter/broker is permitted
    to execute a given asset class.

    Expected state keys (fail-closed if missing):
      - adapter_name: str
      - adapter_capabilities: dict[str,bool] OR list[str]
        Examples:
          {"fx": True, "futures": False}
          ["fx"]
    """

    def evaluate(
        self,
        *,
        asset_class: str,          # "fx" | "futures" | "equities" | etc
        state: Dict[str, Any],
    ) -> CapabilityDecision:

        reasons: List[str] = []

        adapter_name = state.get("adapter_name")
        if not adapter_name or not isinstance(adapter_name, str):
            return CapabilityDecision(
                ok=False,
                decision="BLOCK",
                reasons=["missing_adapter_name"],
            )

        caps = state.get("adapter_capabilities")

        # Case 1: dict capabilities
        if isinstance(caps, dict):
            allowed = bool(caps.get(asset_class, False))
            if not allowed:
                reasons.append(f"adapter_not_capable:{adapter_name}:{asset_class}")
                return CapabilityDecision(ok=False, decision="BLOCK", reasons=reasons)
            return CapabilityDecision(ok=True, decision="ALLOW", reasons=[f"adapter_capable:{adapter_name}:{asset_class}"])

        # Case 2: list/set/tuple of capability strings
        if isinstance(caps, (list, set, tuple)):
            allowed = asset_class in [str(x) for x in caps]
            if not allowed:
                reasons.append(f"adapter_not_capable:{adapter_name}:{asset_class}")
                return CapabilityDecision(ok=False, decision="BLOCK", reasons=reasons)
            return CapabilityDecision(ok=True, decision="ALLOW", reasons=[f"adapter_capable:{adapter_name}:{asset_class}"])

        # Missing or invalid capabilities → fail-closed
        return CapabilityDecision(
            ok=False,
            decision="BLOCK",
            reasons=["missing_or_invalid_adapter_capabilities"],
        )
