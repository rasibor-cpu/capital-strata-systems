from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class OptionQuote:
    symbol: str
    option_type: str   # CALL or PUT
    strike: float
    spot: float
    time_to_expiry: float
    volatility: float
    risk_free_rate: float
    theoretical_price: float


class OptionsPricingEngine:
    """
    CSS Options Sandbox Phase 1:
    Black-Scholes pricing engine for long CALL and long PUT contracts only.
    Initial supported underlyings:
        - SPY
        - QQQ
        - AAPL
    """

    SUPPORTED_UNDERLYINGS = {"SPY", "QQQ", "AAPL"}

    def __init__(self):
        pass

    def _norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _d1(
        self,
        spot: float,
        strike: float,
        t: float,
        r: float,
        sigma: float
    ) -> float:
        return (
            math.log(spot / strike)
            + (r + 0.5 * sigma * sigma) * t
        ) / (sigma * math.sqrt(t))

    def _d2(
        self,
        d1: float,
        sigma: float,
        t: float
    ) -> float:
        return d1 - sigma * math.sqrt(t)

    def price_option(
        self,
        symbol: str,
        option_type: str,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float = 0.04,
    ) -> OptionQuote:

        symbol = symbol.upper()
        option_type = option_type.upper()

        if symbol not in self.SUPPORTED_UNDERLYINGS:
            raise ValueError(f"Unsupported underlying: {symbol}")

        if option_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")

        if time_to_expiry <= 0:
            raise ValueError("time_to_expiry must be > 0")

        if volatility <= 0:
            raise ValueError("volatility must be > 0")

        d1 = self._d1(
            spot,
            strike,
            time_to_expiry,
            risk_free_rate,
            volatility,
        )
        d2 = self._d2(d1, volatility, time_to_expiry)

        if option_type == "CALL":
            price = (
                spot * self._norm_cdf(d1)
                - strike
                * math.exp(-risk_free_rate * time_to_expiry)
                * self._norm_cdf(d2)
            )
        else:
            price = (
                strike
                * math.exp(-risk_free_rate * time_to_expiry)
                * self._norm_cdf(-d2)
                - spot * self._norm_cdf(-d1)
            )

        return OptionQuote(
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            spot=spot,
            time_to_expiry=time_to_expiry,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
            theoretical_price=round(price, 4),
        )
