"""
REA Capital Trading Engine
Slippage Guard (Execution Veto Layer)

Purpose:
- Prevent execution when live price deviates materially from expected signal price
- READ-ONLY
- No broker calls
- No execution

Veto Rule (Hard):
- |live_mid - expected_price| / expected_price <= MAX_SLIPPAGE_PCT
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# -----------------------------
# Policy Constants (LOCKED)
# -----------------------------
MAX_SLIPPAGE_PCT = 0.0010  # 0.10% max deviation


# -----------------------------
# Decision Output
# -----------------------------
@dataclass(frozen=True)
class SlippageDecision:
    allow: bool
    reason: str
    slippage_pct: Optional[float]


# -----------------------------
# Slippage Guard
# -----------------------------
class SlippageGuard:
    """
    Authoritative slippage veto layer.
    """

    def pre_check(
        self,
        expected_price: Optional[float],
        live_mid: Optional[float],
    ) -> SlippageDecision:
        # If either price is missing, be conservative and veto
        if expected_price is None or live_mid is None:
            return SlippageDecision(
                allow=False,
                reason="Missing price for slippage check",
                slippage_pct=None,
            )

        if expected_price <= 0:
            return SlippageDecision(
                allow=False,
                reason="Invalid expected_price for slippage check",
                slippage_pct=None,
            )

        slippage_pct = abs(live_mid - expected_price) / expected_price

        if slippage_pct > MAX_SLIPPAGE_PCT:
            return SlippageDecision(
                allow=False,
                reason=(
                    f"Excessive slippage: {slippage_pct:.4%} "
                    f"exceeds {MAX_SLIPPAGE_PCT:.2%}"
                ),
                slippage_pct=slippage_pct,
            )

        return SlippageDecision(
            allow=True,
            reason="Slippage within tolerance",
            slippage_pct=slippage_pct,
        )


if __name__ == "__main__":
    raise RuntimeError("SlippageGuard is a library module only.")
