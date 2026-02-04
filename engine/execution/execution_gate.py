"""
EXECUTION GATE — canonical execution permission check.

Contract:
- MUST export: check_execution_gate()
- MUST NOT raise on import
- MUST return decision-like object
"""

from __future__ import annotations
from typing import Dict
import os


def check_execution_gate() -> Dict[str, str | bool]:
    """
    Determines whether execution is permitted.

    Returns:
        {
            "allowed": bool,
            "reason": str
        }
    """

    # Fail-closed default
    allowed = True
    reason = "ok"

    # Hard global kill-switch
    if os.getenv("REA_EXECUTION_DISABLED", "0") == "1":
        allowed = False
        reason = "execution_disabled"

    # Optional liquidity / volatility brakes (future hooks)
    if os.getenv("REA_VOLATILITY_HALT", "0") == "1":
        allowed = False
        reason = "volatility_halt"

    return {
        "allowed": allowed,
        "reason": reason,
    }
