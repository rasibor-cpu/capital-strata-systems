"""
Broker Capability Gate Adapter (Fail-Closed)
-------------------------------------------

Purpose:
Prevent accidental routing of Futures into a non-futures-capable broker/adapter.

This is a structural safety gate. It does not enable execution.

Contract:
- Reads routing inputs ONLY from GateInputs (no dynamic attrs required)
- Uses GateInputs.state (dict) for adapter metadata
- Uses GateInputs.asset_class first, then state["asset_class"], then defaults to "fx"
- Fail-closed if adapter_name or adapter_capabilities are missing/invalid
"""

from __future__ import annotations

from typing import Any, Dict

from engine.decision_builder import GateInputs
from engine.gates.broker_capability_gate import BrokerCapabilityGate


def evaluate_broker_capability(inputs: GateInputs) -> Dict[str, Any]:
    """
    Expected inputs.state keys (fail-closed if missing):
      - adapter_name: str
      - adapter_capabilities: dict[str,bool] OR list[str]
        Examples:
          {"fx": True, "futures": False}
          ["fx"]

    Asset class routing:
      1) inputs.asset_class (preferred)
      2) inputs.state["asset_class"]
      3) "fx" default
    """

    # GateInputs.state is optional; normalize safely
    state = inputs.state or {}

    # Determine asset class deterministically
    asset_class = (inputs.asset_class or state.get("asset_class") or "fx")
    asset_class = str(asset_class).strip().lower() if asset_class is not None else "fx"

    gate = BrokerCapabilityGate()
    decision = gate.evaluate(asset_class=asset_class, state=state)

    # Normalize to the common adapter pattern (decision/reason)
    if decision.decision == "ALLOW":
        primary = decision.reasons[0] if decision.reasons else "adapter_capable"
        return {
            "ok": True,
            "decision": "ALLOW",
            "reason": primary,
        }

    primary = decision.reasons[0] if decision.reasons else "adapter_not_capable"
    return {
        "ok": False,
        "decision": "BLOCK",
        "reason": primary,
    }
