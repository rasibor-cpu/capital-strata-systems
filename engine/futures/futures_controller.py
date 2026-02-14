"""
Capital Strata Systems
Futures Controller – Phase 2A Scaffold

Status: Dormant
Execution: Disabled
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Dict


# -------------------------------------------------------
# Configuration
# -------------------------------------------------------

FUTURES_CAPITAL_ALLOCATION = 0.25  # 25% allocation
FX_CAPITAL_ALLOCATION = 0.75       # 75% allocation


@dataclass
class FuturesState:
    activated: bool = False
    activation_timestamp: str | None = None
    activation_reason: str | None = None


class FuturesController:

    def __init__(self):
        self.state = FuturesState()

    # ---------------------------------------------------
    # Activation Guard
    # ---------------------------------------------------

    def can_activate(
        self,
        *,
        consecutive_fx_profitable_weeks: int,
        defensive_regime_active: bool,
    ) -> bool:
        """
        Futures can only activate if:
        - 4 consecutive profitable FX weeks
        - No defensive regime active
        """

        if consecutive_fx_profitable_weeks < 4:
            return False

        if defensive_regime_active:
            return False

        return True

    # ---------------------------------------------------
    # Activation Method
    # ---------------------------------------------------

    def attempt_activation(
        self,
        *,
        consecutive_fx_profitable_weeks: int,
        defensive_regime_active: bool,
    ) -> Dict[str, str]:
        """
        Attempts activation. Does NOT enable execution.
        Only sets structural flag.
        """

        if not self.can_activate(
            consecutive_fx_profitable_weeks=consecutive_fx_profitable_weeks,
            defensive_regime_active=defensive_regime_active,
        ):
            return {
                "status": "DENIED",
                "reason": "Activation criteria not satisfied",
            }

        self.state.activated = True
        self.state.activation_timestamp = datetime.utcnow().isoformat()
        self.state.activation_reason = "Activation criteria satisfied"

        return {
            "status": "APPROVED",
            "timestamp": self.state.activation_timestamp,
        }

    # ---------------------------------------------------
    # Execution Block (Hard Guard)
    # ---------------------------------------------------

    def execution_allowed(self) -> bool:
        """
        Even if activated, execution path is NOT implemented.
        This guarantees no accidental routing.
        """
        return False
