from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Deque, List, Literal, Optional


SignalType = Literal["LONG", "SHORT", "NEUTRAL"]


@dataclass(frozen=True)
class SignalResult:
    signal: SignalType
    price: float
    sma: Optional[float]
    upper_band: Optional[float]
    lower_band: Optional[float]
    window_size: int


class BollingerSignalEngine:
    """
    Minimal Phase 3 Signal Engine.

    - Rolling window
    - SMA
    - Population standard deviation
    - Bollinger bands
    """

    def __init__(self, window: int = 20, band_width: float = 2.0) -> None:
        self.window = window
        self.band_width = band_width
        self._prices: Deque[float] = deque(maxlen=window)

    def update(self, price: float) -> SignalResult:
        self._prices.append(price)

        if len(self._prices) < self.window:
            return SignalResult(
                signal="NEUTRAL",
                price=price,
                sma=None,
                upper_band=None,
                lower_band=None,
                window_size=len(self._prices),
            )

        prices: List[float] = list(self._prices)

        sma = mean(prices)
        std = pstdev(prices)

        upper = sma + self.band_width * std
        lower = sma - self.band_width * std

        if price > upper:
            signal: SignalType = "SHORT"
        elif price < lower:
            signal = "LONG"
        else:
            signal = "NEUTRAL"

        return SignalResult(
            signal=signal,
            price=price,
            sma=sma,
            upper_band=upper,
            lower_band=lower,
            window_size=len(self._prices),
        )
