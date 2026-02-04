"""
Regime Gate Adapter
===================

Purpose:
- Provide a stable gate interface for the Decision Builder
- Allow wiring to the existing regime gate wherever it currently lives
- Fail-closed until wired (safest default)
"""

from __future__ import annotations

from typing import Dict

from engine.decision_builder import GateInputs


def evaluate_regime(inputs: GateInputs) -> Dict[str, str]:
    """
    Adapter entrypoint used by gates_registry.
    """
    try:
        # TODO: Wire to your real regime implementation once we confirm the path.
        # Examples (uncomment the correct one later):
        # from engine.regime.regime_gate_v3 import evaluate_regime as _impl
        # return _impl(inputs)

        return {"decision": "BLOCK", "reason": "regime_gate_adapter: NOT_YET_WIRED"}
    except Exception as e:
        return {
            "decision": "BLOCK",
            "reason": f"regime_gate_adapter: EXCEPTION {type(e).__name__}: {e}",
        }
