"""
Broker Capability Gate Adapter (Fail-Closed)
-------------------------------------------

Purpose:
Prevent accidental routing of Futures into a non-futures-capable broker/adapter.

This is a structural safety gate. It does not enable execution.
"""

from __future__ import annotations

from engine.decision_builder import GateInputs
from engine.gates.broker_capability_gate import BrokerCapabilityGate


def evaluate_broker_capability(inputs: GateInputs):
    """
    Expected inputs.state keys (fail-closed if missing):
      - adapter_name: str
      - adapter_capabilities: dict[str,bool] OR list[str]
        Examples:
          {"fx": True, "futures": False}
          ["fx"]
    """
    state = getattr(inputs, "state", {}) or {}

    # Default asset_class is fx unless explicitly specified in GateInputs
    asset_class = getattr(inputs, "asset_class", None) or state.get("asset_class") or "fx"

    gate = BrokerCapabilityGate()
    decision = gate.evaluate(asset_class=str(asset_class), state=state)

    # Normalize to the common envelope pattern used by other adapters
    if decision.decision == "ALLOW":
        return {
            "ok": True,
            "decision": "ALLOW",
            "primary_reason": (decision.reasons[0] if decision.reasons else "adapter_capable"),
            "reasons": decision.reasons,
            "gate": "broker_capability_gate",
        }

    return {
        "ok": False,
        "decision": "BLOCK",
        "primary_reason": (decision.reasons[0] if decision.reasons else "adapter_not_capable"),
        "reasons": decision.reasons,
        "gate": "broker_capability_gate",
    }
