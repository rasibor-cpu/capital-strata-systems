from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class OptionPricingResult:
    premium: float
    intrinsic_value: float
    time_value: float
    volatility_multiplier: float
    decay_factor: float


class OptionPricingCalibrationEngine:
    """
    Capital Strata Systems
    Realistic Option Pricing Calibration Engine

    Produces market-like simulated option premiums using:
    - intrinsic value
    - strike distance
    - volatility scaling
    - expiry decay weighting
    """

    def __init__(self):
        self.base_time_value_floor = 0.75
        self.max_time_value = 12.0
        self.min_decay = 0.20
        self.max_decay = 1.00

    def _normalize_option_type(self, option_type: str) -> str:
        raw = str(option_type).strip().upper()
        if raw.startswith("C"):
            return "CALL"
        if raw.startswith("P"):
            return "PUT"
        return raw

    def _compute_intrinsic_value(
        self,
        underlying_price: float,
        strike: float,
        option_type: str
    ) -> float:
        option_type = self._normalize_option_type(option_type)

        if option_type == "CALL":
            return max(0.0, underlying_price - strike)

        if option_type == "PUT":
            return max(0.0, strike - underlying_price)

        return 0.0

    def _compute_moneyness_distance(
        self,
        underlying_price: float,
        strike: float
    ) -> float:
        if underlying_price <= 0:
            return 0.0
        return abs(strike - underlying_price) / underlying_price

    def _compute_decay_factor(self, days_to_expiry: int) -> float:
        if days_to_expiry <= 0:
            return self.min_decay

        decay = min(
            self.max_decay,
            max(
                self.min_decay,
                days_to_expiry / 30.0
            )
        )
        return round(decay, 4)

    def _compute_time_value(
        self,
        underlying_price: float,
        strike: float,
        volatility_multiplier: float,
        days_to_expiry: int
    ) -> float:
        distance = self._compute_moneyness_distance(
            underlying_price,
            strike
        )

        decay_factor = self._compute_decay_factor(days_to_expiry)

        proximity_bonus = max(0.25, 1.25 - distance)

        time_value = (
            self.base_time_value_floor *
            volatility_multiplier *
            proximity_bonus *
            decay_factor
        )

        time_value = min(self.max_time_value, time_value)

        return round(time_value, 4)

    def estimate_premium(
        self,
        *,
        underlying_price: float,
        strike: float,
        option_type: str,
        volatility_multiplier: float,
        days_to_expiry: int
    ) -> OptionPricingResult:

        option_type = self._normalize_option_type(option_type)

        intrinsic = self._compute_intrinsic_value(
            underlying_price,
            strike,
            option_type
        )

        decay_factor = self._compute_decay_factor(days_to_expiry)

        time_value = self._compute_time_value(
            underlying_price,
            strike,
            volatility_multiplier,
            days_to_expiry
        )

        premium = intrinsic + time_value

        premium = max(0.50, round(premium, 4))

        return OptionPricingResult(
            premium=premium,
            intrinsic_value=round(intrinsic, 4),
            time_value=time_value,
            volatility_multiplier=round(volatility_multiplier, 4),
            decay_factor=decay_factor
        )

    def estimate_from_selected_contract(
        self,
        *,
        selected: Dict,
        underlying_price: float,
        option_type: str,
        fallback_days_to_expiry: int = 14
    ) -> OptionPricingResult:

        strike = selected.get("strike")
        if strike is None:
            strike = selected.get("strike_price")

        if strike is None:
            strike = round(underlying_price)

        try:
            strike = float(strike)
        except Exception:
            strike = float(round(underlying_price))

        volatility_multiplier = selected.get("volatility_multiplier", 1.0)
        try:
            volatility_multiplier = float(volatility_multiplier)
        except Exception:
            volatility_multiplier = 1.0

        days_to_expiry = selected.get("days_to_expiry", fallback_days_to_expiry)
        try:
            days_to_expiry = int(days_to_expiry)
        except Exception:
            days_to_expiry = fallback_days_to_expiry

        return self.estimate_premium(
            underlying_price=underlying_price,
            strike=strike,
            option_type=option_type,
            volatility_multiplier=volatility_multiplier,
            days_to_expiry=days_to_expiry
        )