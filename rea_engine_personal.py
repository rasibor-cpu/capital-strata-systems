from __future__ import annotations

"""
REA Core Engine — Personal Version (Registry-Wired, Feb 10 Baseline)

Purpose:
- Central decision engine for FX signals
- Registry-driven (pip size, epsilon, instruments)
- Exposes ALL attributes required by runners
- Per-instrument accuracy tracking
- Sanity-Probe aligned defaults

THIS FILE IS AUTHORITATIVE.
"""

from dataclasses import dataclass, field
from typing import Dict

import instrument_registry as ir


# -------------------------
# Result container
# -------------------------

@dataclass
class EngineResult:
    symbol: str
    price: float
    mean: float
    epsilon: float
    signal: str          # BUY / SELL / NO_TRADE
    bars_used: int


# -------------------------
# Core Engine
# -------------------------

class REAEngine:
    """
    Registry-wired FX decision engine
    """

    def __init__(
        self,
        accuracy_mode: str | None = None,
        lookback_bars: int | None = None,
    ):
        # ----- Locked defaults -----
        self.accuracy_mode = (
            accuracy_mode.strip().lower()
            if accuracy_mode
            else ir.DEFAULT_ACCURACY_MODE
        )

        self.lookback_bars = (
            int(lookback_bars)
            if lookback_bars is not None
            else ir.DEFAULT_LOOKBACK_BARS
        )

        # ----- Per-instrument stats -----
        self.stats: Dict[str, Dict[str, int]] = {}

    # -------------------------
    # Internal helpers
    # -------------------------

    def _init_symbol(self, symbol: str) -> None:
        if symbol not in self.stats:
            self.stats[symbol] = {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "no_trade": 0,
            }

    # -------------------------
    # Core signal logic
    # -------------------------

    def evaluate(
        self,
        symbol: str,
        price: float,
        mean_level: float,
    ) -> EngineResult:
        """
        Evaluate a single instrument at a point in time.
        """

        symbol = symbol.upper()
        self._init_symbol(symbol)

        epsilon_price = ir.epsilon_price(symbol, self.accuracy_mode)

        # ---- Sanity Probe Logic ----
        if abs(price - mean_level) < epsilon_price:
            signal = "NO_TRADE"
            self.stats[symbol]["no_trade"] += 1
        elif price < mean_level:
            signal = "BUY"
            self.stats[symbol]["total"] += 1
        else:
            signal = "SELL"
            self.stats[symbol]["total"] += 1

        return EngineResult(
            symbol=symbol,
            price=price,
            mean=mean_level,
            epsilon=epsilon_price,
            signal=signal,
            bars_used=self.lookback_bars,
        )

    # -------------------------
    # Accuracy update (manual)
    # -------------------------

    def record_outcome(self, symbol: str, win: bool) -> None:
        self._init_symbol(symbol)
        if win:
            self.stats[symbol]["wins"] += 1
        else:
            self.stats[symbol]["losses"] += 1

    # -------------------------
    # Reporting
    # -------------------------

    def accuracy(self, symbol: str) -> float:
        s = self.stats.get(symbol)
        if not s:
            return 0.0
        total = s["wins"] + s["losses"]
        return (s["wins"] / total) if total > 0 else 0.0