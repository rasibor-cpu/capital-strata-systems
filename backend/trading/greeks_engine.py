from __future__ import annotations

from dataclasses import asdict, dataclass
from math import erf, exp, log, pi, sqrt
from typing import Any


@dataclass(frozen=True)
class GreeksResult:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    intrinsic_value: float
    extrinsic_value: float
    probability_itm: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GreeksEngine:
    """Reusable options Greeks calculator with broker-neutral interface."""

    @staticmethod
    def _normal_pdf(x: float) -> float:
        return exp(-(x * x) / 2.0) / sqrt(2.0 * pi)

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + erf(x / sqrt(2.0)))

    @staticmethod
    def intrinsic_value(*, option_type: str, spot_price: float, strike: float) -> float:
        normalized_type = str(option_type or "").strip().upper()
        if normalized_type == "CALL":
            return max(spot_price - strike, 0.0)
        if normalized_type == "PUT":
            return max(strike - spot_price, 0.0)
        raise ValueError("option_type must be CALL or PUT")

    @classmethod
    def extrinsic_value(cls, *, option_type: str, option_price: float, spot_price: float, strike: float) -> float:
        intrinsic = cls.intrinsic_value(option_type=option_type, spot_price=spot_price, strike=strike)
        return max(option_price - intrinsic, 0.0)

    @classmethod
    def probability_itm(
        cls,
        *,
        option_type: str,
        spot_price: float,
        strike: float,
        risk_free_rate: float,
        implied_volatility: float,
        time_to_expiry_years: float,
    ) -> float:
        if time_to_expiry_years <= 0.0:
            intrinsic = cls.intrinsic_value(option_type=option_type, spot_price=spot_price, strike=strike)
            return 1.0 if intrinsic > 0.0 else 0.0
        if implied_volatility <= 0.0 or spot_price <= 0.0 or strike <= 0.0:
            return 0.0

        d2 = (
            log(spot_price / strike)
            + (risk_free_rate - 0.5 * implied_volatility * implied_volatility) * time_to_expiry_years
        ) / (implied_volatility * sqrt(time_to_expiry_years))

        normalized_type = str(option_type or "").strip().upper()
        if normalized_type == "CALL":
            return cls._normal_cdf(d2)
        if normalized_type == "PUT":
            return cls._normal_cdf(-d2)
        raise ValueError("option_type must be CALL or PUT")

    @classmethod
    def calculate(
        cls,
        *,
        option_type: str,
        spot_price: float,
        strike: float,
        risk_free_rate: float,
        implied_volatility: float,
        time_to_expiry_years: float,
        option_price: float,
    ) -> GreeksResult:
        normalized_type = str(option_type or "").strip().upper()
        if normalized_type not in {"CALL", "PUT"}:
            raise ValueError("option_type must be CALL or PUT")
        if spot_price <= 0.0 or strike <= 0.0:
            raise ValueError("spot_price and strike must be positive")

        intrinsic = cls.intrinsic_value(option_type=normalized_type, spot_price=spot_price, strike=strike)
        extrinsic = cls.extrinsic_value(
            option_type=normalized_type,
            option_price=float(option_price),
            spot_price=spot_price,
            strike=strike,
        )

        if time_to_expiry_years <= 0.0 or implied_volatility <= 0.0:
            terminal_delta = 1.0 if intrinsic > 0.0 and normalized_type == "CALL" else 0.0
            if normalized_type == "PUT" and intrinsic > 0.0:
                terminal_delta = -1.0
            return GreeksResult(
                delta=terminal_delta,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                intrinsic_value=intrinsic,
                extrinsic_value=extrinsic,
                probability_itm=1.0 if intrinsic > 0.0 else 0.0,
            )

        vol_sqrt_t = implied_volatility * sqrt(time_to_expiry_years)
        d1 = (
            log(spot_price / strike)
            + (risk_free_rate + 0.5 * implied_volatility * implied_volatility) * time_to_expiry_years
        ) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t

        pdf_d1 = cls._normal_pdf(d1)
        cdf_d1 = cls._normal_cdf(d1)
        cdf_d2 = cls._normal_cdf(d2)
        discount = exp(-risk_free_rate * time_to_expiry_years)

        if normalized_type == "CALL":
            delta = cdf_d1
            theta = (
                -(spot_price * pdf_d1 * implied_volatility) / (2.0 * sqrt(time_to_expiry_years))
                - risk_free_rate * strike * discount * cdf_d2
            ) / 365.0
            rho = (strike * time_to_expiry_years * discount * cdf_d2) / 100.0
            probability = cdf_d2
        else:
            delta = cdf_d1 - 1.0
            theta = (
                -(spot_price * pdf_d1 * implied_volatility) / (2.0 * sqrt(time_to_expiry_years))
                + risk_free_rate * strike * discount * cls._normal_cdf(-d2)
            ) / 365.0
            rho = (-strike * time_to_expiry_years * discount * cls._normal_cdf(-d2)) / 100.0
            probability = cls._normal_cdf(-d2)

        gamma = pdf_d1 / (spot_price * vol_sqrt_t)
        vega = (spot_price * pdf_d1 * sqrt(time_to_expiry_years)) / 100.0

        return GreeksResult(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            intrinsic_value=intrinsic,
            extrinsic_value=extrinsic,
            probability_itm=probability,
        )
