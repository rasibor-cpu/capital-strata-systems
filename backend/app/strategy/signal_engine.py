"""
Signal Engine – REA Capital
Minimal deterministic signal scaffold
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import random


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    instrument: str
    signal: SignalType
    confidence: float


class SignalEngine:

    def __init__(self, instrument: str):
        self.instrument = instrument

    def generate_signal(self) -> TradeSignal:
        """
        Placeholder signal logic.
        Replace later with:
        - MA crossover
        - RSI
        - Regime detection
        - Multi-factor composite
        """

        # deterministic micro test
        r = random.random()

        if r > 0.6:
            sig = SignalType.BUY
        elif r < 0.4:
            sig = SignalType.SELL
        else:
            sig = SignalType.HOLD

        return TradeSignal(
            instrument=self.instrument,
            signal=sig,
            confidence=round(r, 3)
        )
