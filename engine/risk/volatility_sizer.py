"""
engine/risk/volatility_sizer.py

Realized Volatility-Based Position Sizing
------------------------------------------

Position size multiplier:

    multiplier = vol_target / realized_vol

Clamped between min_mult and max_mult.

Uses rolling standard deviation of log returns.
"""

from collections import deque
import math


class RealizedVolatilitySizer:
    def __init__(
        self,
        window: int = 96,
        vol_target: float = 0.002,
        min_mult: float = 0.5,
        max_mult: float = 2.0,
    ):
        self.window = window
        self.vol_target = vol_target
        self.min_mult = min_mult
        self.max_mult = max_mult
        self.returns = deque(maxlen=window)
        self.last_price = None

    def update(self, price: float):
        if self.last_price is not None and price > 0:
            r = math.log(price / self.last_price)
            self.returns.append(r)
        self.last_price = price

    def multiplier(self) -> float:
        if len(self.returns) < 10:
            return 1.0

        mean = sum(self.returns) / len(self.returns)
        var = sum((r - mean) ** 2 for r in self.returns) / len(self.returns)
        realized_vol = math.sqrt(var)

        if realized_vol == 0:
            return 1.0

        mult = self.vol_target / realized_vol
        return max(self.min_mult, min(self.max_mult, mult))