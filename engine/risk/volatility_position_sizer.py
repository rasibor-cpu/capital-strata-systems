"""
engine/risk/volatility_position_sizer.py

VolatilityPositionSizer
-----------------------
Instrument-aware notional scaler based on coarse volatility regimes.

Purpose (Phase C2/C3):
- Sit between Allocator and DrawdownScaler
- Reduce exposure in HIGH volatility regimes
- Allow slightly larger exposure in LOW volatility regimes
- Keep behavior deterministic and fail-safe

API (used by engine/execution/execution_gate.py):
    VolatilityPositionSizer().size(
        instrument=...,
        base_notional=...,
        volatility_state=...
    ) -> float
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class VolatilitySizingPolicy:
    low_mult: float = 1.10
    medium_mult: float = 1.00
    high_mult: float = 0.75
    extreme_mult: float = 0.50

    # Safety rails
    min_notional: float = 100.0
    max_mult: float = 2.00   # cap upside
    min_mult: float = 0.10   # cap downside (but keep non-zero)


class VolatilityPositionSizer:
    """
    Deterministic volatility-based notional scaler.

    Notes:
    - volatility_state is expected to be one of:
        "LOW" | "MEDIUM" | "HIGH" | "EXTREME"
      Any unknown value defaults to "MEDIUM".
    - instrument overrides can be used later (e.g., JPY pairs often move differently).
    """

    def __init__(self, policy: VolatilitySizingPolicy | None = None) -> None:
        self.policy = policy or VolatilitySizingPolicy()

        # Optional per-instrument multipliers (relative tweak on top of regime multiplier).
        # Keep neutral for now; we can tune later with observed behavior.
        self.instrument_bias: Dict[str, float] = {
            "EUR_USD": 1.00,
            "GBP_USD": 1.00,
            "USD_JPY": 1.00,
            "AUD_USD": 1.00,
            "USD_CHF": 1.00,
        }

    def size(self, *, instrument: str, base_notional: float, volatility_state: str) -> float:
        """
        Returns a volatility-adjusted notional.

        Fail-closed behavior:
        - If base_notional invalid -> returns 0.0
        """
        try:
            base = float(base_notional)
        except Exception:
            return 0.0

        if base <= 0:
            return 0.0

        state = (volatility_state or "MEDIUM").strip().upper()

        if state == "LOW":
            mult = self.policy.low_mult
        elif state == "HIGH":
            mult = self.policy.high_mult
        elif state == "EXTREME":
            mult = self.policy.extreme_mult
        else:
            mult = self.policy.medium_mult

        # Apply instrument bias (default 1.0 if unknown)
        bias = float(self.instrument_bias.get(str(instrument), 1.0))
        mult = mult * bias

        # Clamp multiplier
        if mult > self.policy.max_mult:
            mult = self.policy.max_mult
        if mult < self.policy.min_mult:
            mult = self.policy.min_mult

        sized = base * mult

        # Clamp absolute notional floor
        if sized < self.policy.min_notional:
            sized = self.policy.min_notional

        return float(sized)
