from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from data.models import Bar
from .volatility import VolatilityPolicy, volatility_expansion_check


class RegimeDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RegimeResult:
    decision: RegimeDecision
    reasons: List[str]
    as_of_utc: datetime
    risk_recommendation: Optional[int] = None
    # risk_recommendation can only suggest lowering risk; user confirmation required later.


@dataclass
class RegimePolicy:
    """
    Regime filters.
    We start with volatility expansion; trend & macro/political hooks come next.
    """
    vol_policy: VolatilityPolicy = VolatilityPolicy()
    min_bars_5m: int = 40  # 40 x 5m = 200 minutes history; conservative baseline


class RegimeGate:
    """
    The Regime Gate decides whether the engine is allowed to trade.
    Primary inputs are 5-minute bars.
    """

    def __init__(self, policy: Optional[RegimePolicy] = None):
        self.policy = policy or RegimePolicy()

    def evaluate(self, bars_5m: List[Bar], as_of_utc: datetime) -> RegimeResult:
        reasons: List[str] = []

        if len(bars_5m) < self.policy.min_bars_5m:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[f"Insufficient 5m history (need >= {self.policy.min_bars_5m} bars)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        # 1) Volatility expansion filter (core for mean-reversion safety)
        is_expanding, why, ratio = volatility_expansion_check(bars_5m, self.policy.vol_policy)
        if is_expanding:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[why or "Volatility expanding (blocked)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        reasons.append("Volatility stable (no expansion block).")

        # Placeholder: other filters will be added next (trend day, macro/political risk)
        reasons.append("RegimeGate: trend + event filters pending implementation.")

        return RegimeResult(
            decision=RegimeDecision.ALLOW,
            reasons=reasons,
            as_of_utc=as_of_utc,
            risk_recommendation=None
        )
