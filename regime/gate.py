from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from data.models import Bar
from .volatility import VolatilityPolicy, volatility_expansion_check
from .trend import TrendPolicy, trend_day_check


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
    Regime filters (Module 2).
    - Volatility expansion filter
    - Trend-day risk filter
    Macro/political hooks will be added next.
    """
    vol_policy: VolatilityPolicy = VolatilityPolicy()
    trend_policy: TrendPolicy = TrendPolicy()
    min_bars_5m: int = 40  # conservative baseline history requirement


class RegimeGate:
    """
    The Regime Gate decides whether the engine is allowed to trade.
    Primary inputs are 5-minute bars (chronological order: oldest -> newest).
    """

    def __init__(self, policy: Optional[RegimePolicy] = None):
        self.policy = policy or RegimePolicy()

    def evaluate(self, bars_5m: List[Bar], as_of_utc: datetime) -> RegimeResult:
        reasons: List[str] = []

        # 0) Minimum history requirement
        if len(bars_5m) < self.policy.min_bars_5m:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[f"Insufficient 5m history (need >= {self.policy.min_bars_5m} bars)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        # 1) Volatility expansion filter (core for mean-reversion safety)
        is_expanding, why_vol, ratio = volatility_expansion_check(bars_5m, self.policy.vol_policy)
        if is_expanding:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[why_vol or "Volatility expanding (blocked)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        reasons.append("Volatility stable (no expansion block).")

        # 2) Trend-day risk filter (mean-reversion safety)
        is_trending, why_trend, eff = trend_day_check(bars_5m, self.policy.trend_policy)
        if is_trending:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[why_trend or "Trend-day risk detected (blocked)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        reasons.append("No trend-day risk (mean-reversion regime acceptable).")

        # 3) Placeholder: macro/political risk hooks (added next)
        reasons.append("RegimeGate: macro/political event filters pending implementation.")

        return RegimeResult(
            decision=RegimeDecision.ALLOW,
            reasons=reasons,
            as_of_utc=as_of_utc,
            risk_recommendation=None
        )
