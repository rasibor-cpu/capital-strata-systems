"""
Gates Registry – Adapter-Based (Fail-Closed)
===========================================

All gates are loaded via adapters to avoid brittle imports.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from engine.decision_builder import GateInputs
from engine.adapters.regime_gate_adapter import evaluate_regime

GateFn = Callable[[GateInputs], Any]


def get_configured_gates() -> Dict[str, GateFn]:
    return {
        "regime_gate": evaluate_regime,
        # Next adapters will be added here:
        # "volatility_gate": evaluate_volatility,
        # "liquidity_gate": evaluate_liquidity,
        # "slippage_guard": evaluate_slippage,
        # "risk_guard": evaluate_risk,
#from engine.adapters.volatility_gate_adapter import evaluate_volatility,

    }
