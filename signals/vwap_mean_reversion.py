from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from data.models import Bar
from regime.gate import RegimeDecision, RegimeResult


# -----------------------------
# Configuration & Policy
# -----------------------------

@dataclass
class SignalPolicy:
    """
    Policy for VWAP + volatility-normalized mean reversion signals.
    """
    min_bars_5m: int = 30          # minimum history before signals are considered
    zscore_entry: float = 2.0      # baseline deviation threshold
    zscore_max: float = 4.0        # extreme deviation cap
    default_risk_level: int = 2    # advisory only (1–5)


# -----------------------------
# Signal Object
# -----------------------------

@dataclass(frozen=True)
class SignalPrompt:
    """
    Prompt-only signal object.
    """
    symbol: str
    direction: str                # "LONG_REVERT" or "SHORT_REVERT"
    zscore: float
    vwap: float
    last_price: float
    volatility: float
    suggested_risk_level: int
    confidence: float             # 0.0–1.0
    as_of_utc: datetime
    rationale: List[str]

    def summary(self) -> str:
        return (
            f"SIGNAL DETECTED ({self.symbol})\n"
            f"Type: {self.direction}\n"
            f"Deviation: {self.zscore:.2f}σ from VWAP\n"
            f"Suggested Risk Level: {self.suggested_risk_level}\n"
            f"Confidence: {self.confidence:.2f}\n"
            f"Rationale: {' | '.join(self.rationale)}"
        )


# -----------------------------
# Core Signal Engine
# -----------------------------

class VWAPMeanReversionEngine:
    """
    Module 3 — Signal Construction (Prompt-Only)

    Produces mean-reversion signal prompts
    ONLY when RegimeGate == ALLOW.
    """

    def __init__(self, policy: Optional[SignalPolicy] = None):
        self.policy = policy or SignalPolicy()

    def _compute_vwap(self, bars: List[Bar]) -> float:
        total_v = sum(b.v for b in bars)
        if total_v <= 0:
            return sum(b.c for b in bars) / len(bars)
        return sum(b.c * b.v for b in bars) / total_v

    def _compute_volatility(self, bars: List[Bar]) -> float:
        closes = [b.c for b in bars]
        if len(closes) < 2:
            return 0.0
        mean = sum(closes) / len(closes)
        var = sum((c - mean) ** 2 for c in closes) / (len(closes) - 1)
        return var ** 0.5

    def evaluate(
        self,
        symbol: str,
        bars_5m: List[Bar],
        regime: RegimeResult,
        as_of_utc: datetime,
        current_risk_level: int,
    ) -> Optional[SignalPrompt]:
        """
        Returns a SignalPrompt or None.
        """
        # Hard gate: regime must allow
        if regime.decision != RegimeDecision.ALLOW:
            return None

        if len(bars_5m) < self.policy.min_bars_5m:
            return None

        vwap = self._compute_vwap(bars_5m)
        vol = self._compute_volatility(bars_5m)
        if vol <= 0:
            return None

        last_price = bars_5m[-1].c
        zscore = (last_price - vwap) / vol

        abs_z = abs(zscore)
        if abs_z < self.policy.zscore_entry or abs_z > self.policy.zscore_max:
            return None

        direction = "SHORT_REVERT" if zscore > 0 else "LONG_REVERT"

        # Confidence scaling (bounded)
        confidence = min(1.0, abs_z / self.policy.zscore_max)

        rationale = [
            "RegimeGate = ALLOW",
            "VWAP defines fair value",
            f"Deviation = {abs_z:.2f}σ (vol-normalized)",
            "Mean-reversion candidate only (no execution)",
        ]

        # Risk suggestion logic (advisory only)
        suggested_risk = max(
            current_risk_level,
            self.policy.default_risk_level
        )

        return SignalPrompt(
            symbol=symbol,
            direction=direction,
            zscore=zscore,
            vwap=vwap,
            last_price=last_price,
            volatility=vol,
            suggested_risk_level=suggested_risk,
            confidence=confidence,
            as_of_utc=as_of_utc,
            rationale=rationale,
        )
