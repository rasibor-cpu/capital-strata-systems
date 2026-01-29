from __future__ import annotations
"""
REA Engine — Personal Core (Registry-Wired, Locked Baseline)

Role:
- Central decision engine for REA Capital
- Consumes price + mean levels
- Uses instrument_registry as the ONLY source of:
  • instruments
  • pip sizing
  • epsilon logic
- Produces deterministic signals
- Tracks per-instrument accuracy stats (in-memory, append-ready)

NO broker execution
NO MT5 dependency
NO CSV logic
Pure decision + accounting layer
"""

from dataclasses import dataclass, field
from typing import Dict, Literal
import time

import instrument_registry as ir


Signal = Literal["BUY", "SELL", "NO_TRADE"]


# -------------------------------------------------
# Data structures
# -------------------------------------------------

@dataclass
class SignalDecision:
    instrument: str
    signal: Signal
    price: float
    mean_level: float
    epsilon_price: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class InstrumentStats:
    total_signals: int = 0
    correct_signals: int = 0

    @property
    def accuracy(self) -> float:
        if self.total_signals == 0:
            return 0.0
        return self.correct_signals / self.total_signals


# -------------------------------------------------
# Engine
# -------------------------------------------------

class REAEngine:
    """
    Registry-driven decision engine.
    """

    def __init__(self, accuracy_mode: str = ir.DEFAULT_ACCURACY_MODE):
        self.accuracy_mode = accuracy_mode
        self.stats: Dict[str, InstrumentStats] = {}

    # -------------------------
    # Core signal logic
    # -------------------------

    def decide(
        self,
        instrument: str,
        price: float,
        mean_level: float,
    ) -> SignalDecision:

        spec = ir.get_instrument(instrument)
        epsilon_price = ir.epsilon_price(instrument, self.accuracy_mode)

        if abs(price - mean_level) < epsilon_price:
            signal: Signal = "NO_TRADE"
        elif price < mean_level:
            signal = "BUY"
        else:
            signal = "SELL"

        return SignalDecision(
            instrument=instrument,
            signal=signal,
            price=price,
            mean_level=mean_level,
            epsilon_price=epsilon_price,
        )

    # -------------------------
    # Accuracy tracking
    # -------------------------

    def record_outcome(
        self,
        instrument: str,
        was_correct: bool,
    ) -> None:
        if instrument not in self.stats:
            self.stats[instrument] = InstrumentStats()

        s = self.stats[instrument]
        s.total_signals += 1
        if was_correct:
            s.correct_signals += 1

    def get_accuracy(self, instrument: str) -> float:
        if instrument not in self.stats:
            return 0.0
        return self.stats[instrument].accuracy

    def summary(self) -> Dict[str, float]:
        """
        Returns accuracy per instrument.
        """
        return {k: v.accuracy for k, v in self.stats.items()}


# -------------------------------------------------
# Self-test (SAFE)
# -------------------------------------------------

if __name__ == "__main__":
    engine = REAEngine()

    decision = engine.decide(
        instrument="EURUSD",
        price=1.0000,
        mean_level=1.0020,
    )

    print(decision)