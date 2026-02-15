"""
Gates Registry – Adapter-Based (Fail-Closed)
===========================================

All execution safety checks are loaded via adapters.

Order matters:
- Gates are evaluated in sequence
- First BLOCK becomes the primary_reason in the envelope
"""

from __future__ import annotations

from typing import Any, Callable, Dict

# Startup validation import (ensures canonical instruments load early)
import engine.instruments  # noqa: F401

from engine.decision_builder import GateInputs
from engine.adapters.broker_capability_gate_adapter import evaluate_broker_capability
from engine.adapters.regime_gate_adapter import evaluate_regime
from engine.adapters.volatility_gate_adapter import evaluate_volatility
from engine.adapters.liquidity_gate_adapter import evaluate_liquidity
from engine.adapters.slippage_guard_adapter import evaluate_slippage
from engine.adapters.risk_guard_adapter import evaluate_risk

GateFn = Callable[[GateInputs], Any]


def get_configured_gates() -> Dict[str, GateFn]:
    """
    Returns adapter-based gate functions in strict evaluation order.
    """
    return {
        # Structural gate (MUST RUN FIRST)
        "broker_capability_gate": evaluate_broker_capability,

        # Market condition gates
        "regime_gate": evaluate_regime,
        "volatility_gate": evaluate_volatility,

        # Execution quality gates
        "liquidity_gate": evaluate_liquidity,
        "slippage_guard": evaluate_slippage,

        # Portfolio protection gate (runs last)
        "risk_guard": evaluate_risk,
    }
