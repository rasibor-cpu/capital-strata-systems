"""
REA Capital Trading Engine
Liquidity Gate (Execution Veto Layer)

Purpose:
- Enforce market safety checks before any execution consideration
- READ-ONLY
- No broker calls
- No execution

Veto Rules (Hard):
1. Quote freshness (age <= MAX_QUOTE_AGE_MS)
2. Spread sanity (if available)

This gate is authoritative and blocks downstream execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# -----------------------------
# Policy Constants (LOCKED)
# -----------------------------
MAX_QUOTE_AGE_MS = 3000      # 3 seconds (institutional standard)
MAX_SPREAD_PCT = 0.002       # 0.20% max spread (defensive default)


# -----------------------------
# Snapshot Input
# -----------------------------
@dataclass(frozen=True)
class LiquiditySnapshot:
    quote_age_ms: int
    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]


# -----------------------------
# Decision Output
# -----------------------------
@dataclass(frozen=True)
class LiquidityDecision:
    allow: bool
    reason: str


# -----------------------------
# Liquidity Gate
# -----------------------------
class LiquidityGate:
    """
    Authoritative liquidity veto layer.
    """

    def evaluate(self, snap: LiquiditySnapshot) -> LiquidityDecision:
        # ---- Rule 1: Quote freshness ----
        if snap.quote_age_ms > MAX_QUOTE_AGE_MS:
            return LiquidityDecision(
                allow=False,
                reason=f"Stale quote: age={snap.quote_age_ms}ms exceeds {MAX_QUOTE_AGE_MS}ms",
            )

        # ---- Rule 2: Spread sanity (if available) ----
        if snap.bid is not None and snap.ask is not None and snap.mid:
            spread = snap.ask - snap.bid
            if spread < 0:
                return LiquidityDecision(
                    allow=False,
                    reason="Invalid spread (ask < bid)",
                )

            spread_pct = spread / snap.mid if snap.mid > 0 else 0.0
            if spread_pct > MAX_SPREAD_PCT:
                return LiquidityDecision(
                    allow=False,
                    reason=f"Excessive spread: {spread_pct:.4%}",
                )

        # ---- Passed ----
        return LiquidityDecision(
            allow=True,
            reason="Liquidity checks passed",
        )


if __name__ == "__main__":
    raise RuntimeError("LiquidityGate is a library module only.")
