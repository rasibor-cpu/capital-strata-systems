from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

from data.models import Bar
from .volatility import VolatilityPolicy, volatility_expansion_check
from .trend import TrendPolicy, trend_day_check
from .events import EventGate, EventPolicy


class RegimeDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RegimeResult:
    decision: RegimeDecision
    reasons: List[str]
    as_of_utc: datetime
    risk_recommendation: Optional[int] = None
    # risk_recommendation can only suggest LOWER risk (1–5); user confirmation required later.


@dataclass
class RegimePolicy:
    """
    Regime filters (Module 2).
    - Volatility expansion filter
    - Trend-day risk filter
    - Macro / political event gate (BLOCK-only)

    All filters are defensive.
    """
    vol_policy: VolatilityPolicy = VolatilityPolicy()
    trend_policy: TrendPolicy = TrendPolicy()
    event_policy: EventPolicy = EventPolicy()
    min_bars_5m: int = 40  # conservative baseline (≈200 minutes)


class RegimeGate:
    """
    Regime Gate (Module 2)

    Determines whether trading is allowed based on:
    1) Data sufficiency
    2) Volatility expansion
    3) Trend-day risk
    4) Macro / political event risk

    Primary input: 5-minute bars (chronological order: oldest → newest)
    """

    def __init__(self, policy: Optional[RegimePolicy] = None):
        self.policy = policy or RegimePolicy()
        self.event_gate = EventGate(policy=self.policy.event_policy)

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

        # 1) Volatility expansion filter (mean-reversion safety)
        is_expanding, why_vol, ratio = volatility_expansion_check(
            bars_5m, self.policy.vol_policy
        )
        if is_expanding:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[why_vol or "Volatility expanding (blocked)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        reasons.append("Volatility stable (no expansion block).")

        # 2) Trend-day risk filter
        is_trending, why_trend, eff = trend_day_check(
            bars_5m, self.policy.trend_policy
        )
        if is_trending:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[why_trend or "Trend-day risk detected (blocked)."],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        reasons.append("No trend-day risk (mean-reversion regime acceptable).")

        # 3) Macro / political event gate (BLOCK-only)
        event_block_reason = self.event_gate.evaluate(as_of_utc)
        if event_block_reason:
            return RegimeResult(
                decision=RegimeDecision.BLOCK,
                reasons=[event_block_reason],
                as_of_utc=as_of_utc,
                risk_recommendation=1
            )

        reasons.append("No blocking macro/political events detected.")

        # If we reach here, regime is acceptable
        return RegimeResult(
            decision=RegimeDecision.ALLOW,
            reasons=reasons,
            as_of_utc=as_of_utc,
            risk_recommendation=None
        )
