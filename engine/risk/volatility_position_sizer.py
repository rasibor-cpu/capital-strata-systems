"""
engine/risk/volatility_position_sizer.py

Realized Volatility Position Sizer (Std of Log Returns)
-------------------------------------------------------

Purpose:
- Provide volatility-based notional scaling that compresses exposure during
  volatility expansions (vol clustering), addressing portfolio drawdown blowups
  under breadth (e.g., 12-instrument stacking).

ExecutionGate integration:
- ExecutionGate instantiates:
      self.vol_sizer = VolatilityPositionSizer()
- ExecutionGate calls:
      vol_scaled_notional = self.vol_sizer.size(notional=<base>, price=<last>, debug=<dict>)

Sizing rule:
    mult = vol_target / realized_vol
    mult clipped to [min_mult, max_mult]
    vol_scaled_notional = notional * mult

Notes:
- Uses rolling std of log returns (no annualization needed; relative scaling only).
- Low-overhead, dependency-free.
- Safe warmup: returns 1.0 multiplier until enough observations exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections import deque
from typing import Deque, Optional, Dict, Any


@dataclass(frozen=True)
class VolatilitySizingPolicy:
    window: int = 96           # ~8 trading hours on M5
    vol_target: float = 0.002  # target per-bar log-return stdev (tunable)
    min_mult: float = 0.50     # compress size in high vol
    max_mult: float = 2.00     # allow expansion in low vol
    warmup_min_obs: int = 10   # minimum returns before enabling scaling


class RealizedVolatilitySizer:
    """
    Rolling realized volatility estimator using log returns.
    """
    def __init__(self, policy: VolatilitySizingPolicy):
        self.policy = policy
        self._rets: Deque[float] = deque(maxlen=policy.window)
        self._last_price: Optional[float] = None

    def update(self, price: float) -> None:
        if price is None:
            return
        if price <= 0:
            return

        if self._last_price is not None and self._last_price > 0:
            r = math.log(price / self._last_price)
            self._rets.append(r)

        self._last_price = price

    def realized_vol(self) -> Optional[float]:
        n = len(self._rets)
        if n < self.policy.warmup_min_obs:
            return None

        mean = sum(self._rets) / n
        var = sum((x - mean) ** 2 for x in self._rets) / n
        vol = math.sqrt(var)
        return vol

    def multiplier(self) -> float:
        vol = self.realized_vol()
        if vol is None or vol <= 0:
            return 1.0

        mult = self.policy.vol_target / vol
        if mult < self.policy.min_mult:
            return self.policy.min_mult
        if mult > self.policy.max_mult:
            return self.policy.max_mult
        return mult


class VolatilityPositionSizer:
    """
    ExecutionGate-facing volatility position sizer.

    API:
        size(notional: float, price: float, debug: Optional[dict]) -> float
    """
    def __init__(self, policy: Optional[VolatilitySizingPolicy] = None):
        self.policy = policy or VolatilitySizingPolicy()
        self._sizer = RealizedVolatilitySizer(self.policy)

    def size(self, notional: float, price: float, debug: Optional[Dict[str, Any]] = None) -> float:
        """
        Scale `notional` based on realized volatility computed from `price` stream.
        """
        # Update the volatility state with the latest price
        self._sizer.update(price)

        mult = self._sizer.multiplier()
        scaled = float(notional) * float(mult)

        if debug is not None:
            # Keep keys stable and informative
            debug["vol_window"] = self.policy.window
            debug["vol_target"] = self.policy.vol_target
            debug["vol_mult"] = mult
            rv = self._sizer.realized_vol()
            debug["realized_vol"] = rv if rv is not None else 0.0
            debug["vol_scaled_notional"] = scaled

        return scaled