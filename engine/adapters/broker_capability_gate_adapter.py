"""
Broker Capability Gate Adapter (Fail-Closed)
-------------------------------------------

Purpose:
Prevent accidental routing of Futures into a non-futures-capable broker/adapter.

Phase 2B:
- Mapping-aware enforcement for futures:
  Strategy Concept → Canonical → Broker Symbol
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
      - asset_class: "fx" | "futures" | ...
      - strategy_id: required when asset_class == "futures" (mapping-aware)
    """
    state = getattr(inputs, "state", {}) or {}
    if not isinstance(state, dict):
        state = {}

    asset_class = str(state.get("asset_class") or "fx").lower().strip()

    # Phase 2B: ensure strategy_id is present for futures.
    # Preferred: state["strategy_id"] set by caller.
    # Secondary: inputs.snapshot["strategy_id"]
    # Fallback: use inputs.instrument (fail-closed if not a real strategy_id).
    if asset_class == "futures":
        if "strategy_id" not in state or not isinstance(state.get("strategy_id"), str):
            snap = getattr(inputs, "snapshot", None) or {}
            if isinstance(snap, dict) and isinstance(snap.get("strategy_id"), str):
                state["strategy_id"] = snap["strategy_id"]
            else:
                # last-resort fallback (likely to BLOCK unless it matches a real strategy_id)
                state["strategy_id"] = str(getattr(inputs, "instrument", "") or "")

        # write back
        inputs.state = state

    gate = BrokerCapabilityGate()
    decision = gate.evaluate(asset_class=asset_class, state=state)

    # Normalize to common envelope output
    if decision.decision == "ALLOW":
        return {
            "ok": True,
            "decision": "ALLOW",
            "reason": (decision.reasons[0] if decision.reasons else "adapter_capable"),
        }

    return {
        "ok": False,
        "decision": "BLOCK",
        "reason": (decision.reasons[0] if decision.reasons else "adapter_not_capable"),
    }
