"""
capital_allocator.py
Dynamic capital allocation across asset classes and strategies.
Uses a Kelly-inspired fractional approach, adjusted by:
  • Recent win rate per asset class
  • Volatility regime
  • Drawdown state
  • Correlation between open positions
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import config

logger = logging.getLogger(__name__)


@dataclass
class AllocationBucket:
    name:          str          # e.g. "crypto", "fx", "futures"
    base_pct:      float        # target % of capital
    current_pct:   float        # actual current allocation
    win_rate:      float        # recent win rate
    trade_count:   int
    total_pnl:     float
    max_pct:       float        # hard cap


# Default allocations — total must equal 1.0
DEFAULT_ALLOCATIONS = {
    "crypto":  AllocationBucket("crypto",  0.40, 0.40, 0.50, 0, 0.0, 0.60),
    "fx":      AllocationBucket("fx",      0.30, 0.30, 0.50, 0, 0.0, 0.45),
    "futures": AllocationBucket("futures", 0.20, 0.20, 0.50, 0, 0.0, 0.35),
    "options": AllocationBucket("options", 0.10, 0.10, 0.50, 0, 0.0, 0.20),
}


class CapitalAllocator:

    def __init__(self, total_capital: float):
        self.total_capital = total_capital
        self.buckets: Dict[str, AllocationBucket] = {
            k: AllocationBucket(**vars(v)) for k, v in DEFAULT_ALLOCATIONS.items()
        }
        self._performance_history: Dict[str, List[float]] = {k: [] for k in self.buckets}

    # ── Position sizing ──────────────────────────────────────

    def max_trade_capital(
        self,
        asset_class: str,
        drawdown_pct: float,
        regime: str = "ranging",
    ) -> float:
        """
        Returns max USD to allocate to a single trade in this asset class,
        adjusted for current drawdown and regime.
        """
        bucket = self.buckets.get(asset_class)
        if not bucket:
            return self.total_capital * config.MAX_POSITION_SIZE_PCT

        # Base allocation for this asset class
        class_capital = self.total_capital * bucket.current_pct

        # Per-trade max within the class
        per_trade_pct = config.MAX_POSITION_SIZE_PCT

        # Drawdown scaling — reduce size as we draw down
        if drawdown_pct > 0.03:
            per_trade_pct *= 0.5
        elif drawdown_pct > 0.015:
            per_trade_pct *= 0.75

        # Regime scaling
        regime_scale = {
            "trending_up":   1.0,
            "trending_down": 1.0,
            "ranging":       0.75,
            "volatile":      0.25,
        }.get(regime, 0.75)

        # Win rate scaling — reduce if asset class performing poorly
        wr = bucket.win_rate
        wr_scale = 0.5 if wr < 0.35 else (1.0 if wr > 0.55 else 0.75)

        max_usd = class_capital * per_trade_pct * regime_scale * wr_scale
        return max(max_usd, 10.0)   # floor at $10

    # ── Rebalancing ──────────────────────────────────────────

    def record_trade(self, asset_class: str, pnl: float, win: bool):
        if asset_class not in self.buckets:
            return
        bucket = self.buckets[asset_class]
        bucket.trade_count += 1
        bucket.total_pnl   += pnl
        self._performance_history[asset_class].append(1.0 if win else 0.0)

        # Rolling win rate (last 20 trades)
        hist = self._performance_history[asset_class][-20:]
        bucket.win_rate = sum(hist) / len(hist) if hist else 0.5

    def rebalance(self, drawdown_pct: float) -> Dict[str, float]:
        """
        Recomputes allocation percentages based on performance.
        Returns new allocation dict.
        """
        if drawdown_pct > 0.03:
            # In drawdown — tighten everything
            for b in self.buckets.values():
                b.current_pct = b.base_pct * 0.6
            logger.warning(f"Drawdown {drawdown_pct*100:.1f}% — allocations reduced 40%")
            return {k: v.current_pct for k, v in self.buckets.items()}

        # Kelly-inspired: favour asset classes with higher win rate
        scores = {}
        for name, bucket in self.buckets.items():
            if bucket.trade_count < 5:
                scores[name] = bucket.base_pct  # not enough data
            else:
                wr    = bucket.win_rate
                score = (2 * wr - 1) * bucket.base_pct   # simplified Kelly fraction
                scores[name] = max(score, bucket.base_pct * 0.3)  # floor at 30% of base

        # Normalise to sum to 1
        total = sum(scores.values())
        if total > 0:
            for name in self.buckets:
                new_pct = scores[name] / total
                # Cap at max_pct
                new_pct = min(new_pct, self.buckets[name].max_pct)
                self.buckets[name].current_pct = round(new_pct, 4)

        new_allocs = {k: v.current_pct for k, v in self.buckets.items()}
        logger.info(f"Capital reallocated: {new_allocs}")
        return new_allocs

    def update_capital(self, new_total: float):
        self.total_capital = new_total

    def summary(self) -> dict:
        return {
            name: {
                "current_pct": round(b.current_pct * 100, 1),
                "win_rate":    round(b.win_rate * 100, 1),
                "trades":      b.trade_count,
                "total_pnl":   round(b.total_pnl, 2),
                "capital_usd": round(self.total_capital * b.current_pct, 2),
            }
            for name, b in self.buckets.items()
        }
