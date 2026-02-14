"""
Capital Strata Systems
Gates Registry

Central registry of gate evaluators used by governance lattice.
Pure python / stdlib only.
"""

from __future__ import annotations
from typing import Any, Dict

# Gate imports (pure engine modules only)
from engine.gates.broker_capability_gate import BrokerCapabilityGate


def build_gates() -> Dict[str, Any]:
    """
    Returns instantiated gate objects.
    Keys are stable gate IDs for logging and enforcement.
    """
    return {
        "broker_capability": BrokerCapabilityGate(),
    }
