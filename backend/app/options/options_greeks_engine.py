from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class GreeksResult:
    symbol: str
    option_type: str
    strike: float
    spot: float
    time_to_expiry: float
    volatility: float
    risk_free_rate: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class OptionsGreeksEngine:
    """
    CSS Options Sandbox Phase 1:
    Greeks engine for long CALL and long PUT contracts only.

    Initial supported underlyings:
        - SPY
        - QQQ
        - AAPL
    """

    SUPPORTED_UNDERLYINGS = {"SPY", "QQQ", "AAPL"}

    def _norm_pdf(self, x: float) -> float:
        return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)

    def _norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _d1(
        self,
        spot: float,
        strike: float,
        t: float,
        r: float,
        sigma: float,
    ) -> float:
        return (
            math.log(spot / strike)
            + (r + 0.5 * sigma * sigma) * t
        ) / (sigma * math.sqrt(t))

    def _d2(
        self,
        d1: float,
        sigma: float,
        t: float,
    ) -> float:
        return d1 - sigma * math.sqrt(t)

    def compute_greeks(
        self,
        symbol: str,
        option_type: str,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float = 0.04,
    ) -> GreeksResult:
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

        pdf_d1 = self._norm_pdf(d1)
        sqrt_t = math.sqrt(time_to_expiry)

        if option_type == "CALL":
            delta = self._norm_cdf(d1)
            rho = strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * self._norm_cdf(d2)
            theta = (
                (-spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
                - risk_free_rate
                * strike
                * math.exp(-risk_free_rate * time_to_expiry)
                * self._norm_cdf(d2)
            )
        else:
            delta = self._norm_cdf(d1) - 1.0
            rho = -strike * time_to_expiry * math.exp(-risk_free_rate * time_to_expiry) * self._norm_cdf(-d2)
            theta = (
                (-spot * pdf_d1 * volatility) / (2.0 * sqrt_t)
                + risk_free_rate
                * strike
                * math.exp(-risk_free_rate * time_to_expiry)
                * self._norm_cdf(-d2)
            )

        gamma = pdf_d1 / (spot * volatility * sqrt_t)
        vega = spot * pdf_d1 * sqrt_t

        return GreeksResult(
            symbol=symbol,
            option_type=option_type,
            strike=strike,
            spot=spot,
            time_to_expiry=time_to_expiry,
            volatility=volatility,
            risk_free_rate=risk_free_rate,
            delta=round(delta, 6),
            gamma=round(gamma, 6),
            theta=round(theta, 6),
            vega=round(vega, 6),
            rho=round(rho, 6),
        )
