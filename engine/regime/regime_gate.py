"""
Regime Gate (Pre-Strategy)
--------------------------
Conservative market-regime filter that determines whether strategies are allowed
to act on signals.

Design goals:
- Deterministic and auditable
- Conservative defaults (BLOCK unless conditions are met)
- No execution logic
- Can be driven by: volatility proxy, spread/liquidity hints, news risk flags,
  and minimum data sufficiency.

Output:
- "ALLOW" or "BLOCK" with a reason string
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class RegimeDecision:
    decision: str               # "ALLOW" | "BLOCK"
    reason: str                 # short reason code
    meta: Dict[str, Any]


class RegimeGate:
    """
    Minimal, safe regime gate.
    You can extend inputs over time; keep defaults conservative.
    """

    # Safe defaults
    MIN_BARS_5M: int = 40                # require at least 40 x 5m bars
    MAX_VOL_NORM: float = 0.75           # normalized vol (-1..+1 mapped use) treated conservatively
    MAX_SPREAD_BPS: float = 25.0         # block if spread too wide (bps)
    NEWS_RISK_BLOCK: bool = True         # if high-risk news flag present, block

    @classmethod
    def evaluate(
        cls,
        *,
        bars_5m: int,
        vol_norm_0_1: Optional[float] = None,
        spread_bps: Optional[float] = None,
        high_risk_news: Optional[bool] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> RegimeDecision:
        """
        Inputs:
        - bars_5m: data sufficiency check
        - vol_norm_0_1: volatility proxy normalized to [0,1] where 1 is extreme
        - spread_bps: current spread estimate in basis points
        - high_risk_news: boolean flag from news layer
        """
        meta = extra.copy() if extra else {}
        meta.update(
            {
                "bars_5m": bars_5m,
                "vol_norm_0_1": vol_norm_0_1,
                "spread_bps": spread_bps,
                "high_risk_news": high_risk_news,
            }
        )

        # 1) Data sufficiency
        if bars_5m < cls.MIN_BARS_5M:
            return RegimeDecision("BLOCK", "insufficient_bars", meta)

        # 2) News risk
        if cls.NEWS_RISK_BLOCK and high_risk_news is True:
            return RegimeDecision("BLOCK", "news_risk", meta)

        # 3) Spread / liquidity
        if spread_bps is not None and spread_bps > cls.MAX_SPREAD_BPS:
            return RegimeDecision("BLOCK", "spread_too_wide", meta)

        # 4) Volatility proxy (if provided)
        if vol_norm_0_1 is not None:
            if not (0.0 <= vol_norm_0_1 <= 1.0):
                return RegimeDecision("BLOCK", "vol_out_of_range", meta)
            if vol_norm_0_1 > cls.MAX_VOL_NORM:
                return RegimeDecision("BLOCK", "vol_too_high", meta)

        return RegimeDecision("ALLOW", "ok", meta)


# Safety invariant
if __name__ == "__main__":
    raise RuntimeError("regime_gate.py is a library module only and must not be executed directly.")
