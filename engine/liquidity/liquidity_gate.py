"""
REA Capital Trading Engine
Liquidity Gate (Execution Safety Layer)

Constitutional Authority:
- Layer 5: Execution Control
- This module has VETO power only
- It NEVER authorizes trades, it only blocks unsafe execution

Design Principles:
- Default = BLOCK
- Liquidity uncertainty = NO EXECUTION
- No retries, no averaging, no assumptions
"""

from dataclasses import dataclass
from typing import Optional
import time


# -----------------------------
# Decision Object (Immutable)
# -----------------------------
@dataclass(frozen=True)
class LiquidityDecision:
    allow: bool
    reason: str
    timestamp: float


# -----------------------------
# Liquidity Snapshot
# -----------------------------
@dataclass
class LiquiditySnapshot:
    bid: Optional[float]
    ask: Optional[float]
    spread: Optional[float]
    volume: Optional[float]
    quote_age_ms: Optional[int]


# -----------------------------
# Liquidity Gate
# -----------------------------
class LiquidityGate:
    """
    LiquidityGate enforces execution safety.
    It does NOT optimize fills.
    It only answers: should execution be attempted at all?
    """

    def __init__(
        self,
        max_spread_pct: float,
        min_volume: float,
        max_quote_age_ms: int,
    ):
        self.max_spread_pct = max_spread_pct
        self.min_volume = min_volume
        self.max_quote_age_ms = max_quote_age_ms

    # -------------------------
    # Core Evaluation
    # -------------------------
    def evaluate(self, snapshot: LiquiditySnapshot) -> LiquidityDecision:
        now = time.time()

        # ---- Hard Fail: Missing Data ----
        if snapshot.bid is None or snapshot.ask is None:
            return self._block("Missing bid/ask data", now)

        if snapshot.spread is None:
            return self._block("Spread not computable", now)

        if snapshot.volume is None:
            return self._block("Volume data missing", now)

        if snapshot.quote_age_ms is None:
            return self._block("Quote age unknown", now)

        # ---- Spread Check ----
        mid_price = (snapshot.bid + snapshot.ask) / 2.0
        spread_pct = snapshot.spread / mid_price

        if spread_pct > self.max_spread_pct:
            return self._block(
                f"Spread too wide ({spread_pct:.4%})", now
            )

        # ---- Volume Check ----
        if snapshot.volume < self.min_volume:
            return self._block(
                f"Insufficient liquidity (volume={snapshot.volume})", now
            )

        # ---- Staleness Check ----
        if snapshot.quote_age_ms > self.max_quote_age_ms:
            return self._block(
                f"Stale quote ({snapshot.quote_age_ms}ms)", now
            )

        # ---- If ALL checks pass ----
        return LiquidityDecision(
            allow=True,
            reason="Liquidity conditions acceptable",
            timestamp=now,
        )

    # -------------------------
    # Internal Helper
    # -------------------------
    def _block(self, reason: str, ts: float) -> LiquidityDecision:
        return LiquidityDecision(
            allow=False,
            reason=reason,
            timestamp=ts,
        )


# -----------------------------
# Constitutional Assertion
# -----------------------------
if __name__ == "__main__":
    raise RuntimeError(
        "LiquidityGate is not executable standalone. "
        "It must be called by the Execution Control pipeline."
    )
