from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from data.models import Bar


class RegimeDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RegimeResult:
    decision: RegimeDecision
    reasons: List[str]
    as_of_utc: datetime
    risk_recommendation: Optional[int] = None
    # risk_recommendation is only used to suggest lowering risk (requires user confirmation later)


@dataclass
class RegimePolicy:
    """
    Module 2 policy placeholders.
    We will fill these in next (trend, vol, event/political risk).
    """
    # Example placeholders:
    max_allowed_vol_expansion: float = 0.0
    max_allowed_trend_strength: float = 0.0


class RegimeGate:
    """
    The Regime Gate decides whether the engine is allowed to trade.
    It uses 5-minute bars as the primary signal layer.
    The intelligence layer (macro/political risk) will plug in here later.
    """

    def __init__(self, policy: Optional[RegimePolicy] = None):
        self.policy = policy or RegimePolicy()

    def evaluate(self, bars_5m: List[Bar], as_of_utc: datetime) -> RegimeResult:
        """
        Evaluate regime using recent 5-minute bars.

        For now:
        - If insufficient data, BLOCK.
        - Otherwise ALLOW, with placeholders.
        """
        if len(bars_5m) < 20:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=["Insufficient 5m history for regime evaluation (need >= 20 bars)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        # Placeholder: allow by default until we implement the actual filters next step
        return RegimeResult(
            decision=RegimeDecision.ALLOW,
            reasons=["RegimeGate placeholder: no active blocks (filters to be implemented next)."],
            as_of_utc=as_of_utc,
            risk_recommendation=None
        )
