from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeVolatilityRiskError(ValueError):
    """Raised when volatility risk inputs are malformed."""


@dataclass(frozen=True)
class VolatilityRiskReport:
    status: str
    implied_volatility_exposure: float
    vega_concentration: dict[str, float]
    volatility_regime: str
    volatility_expansion_risk: float
    volatility_contraction_risk: float
    premium_adequacy: float
    short_volatility_concentration: float
    expiry_volatility_exposure: dict[str, float]
    unavailable: list[str]
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, **SAFE_FLAGS}


class OptionsIncomeVolatilityRiskAnalyzer:
    def analyze(
        self,
        portfolio: Mapping[str, Any],
        *,
        iv_by_symbol: Mapping[str, Any] | None,
        greeks: Mapping[str, Any],
        volatility_regime: str = "UNKNOWN",
    ) -> VolatilityRiskReport:
        ivs = iv_by_symbol or {}
        rows = list(portfolio.get("allocations", []) or [])
        unavailable: list[str] = []
        weighted_iv = 0.0
        total_collateral = 0.0
        expiry: dict[str, float] = {}
        for row in rows:
            symbol = str(row.get("option_symbol") or "")
            collateral = float(row.get("collateral", 0.0) or 0.0)
            total_collateral += collateral
            if symbol not in ivs:
                unavailable.append(symbol)
                continue
            iv = _iv(ivs[symbol])
            weighted_iv += iv * collateral
            expiry_key = str(row.get("expiry") or "UNKNOWN")
            expiry[expiry_key] = expiry.get(expiry_key, 0.0) + iv * collateral
        iv_exposure = weighted_iv / total_collateral if total_collateral > 0 else 0.0
        by_underlying = dict(greeks.get("by_underlying") or {})
        vega_total = sum(abs(float(row.get("vega", 0.0) or 0.0)) for row in by_underlying.values())
        vega_concentration = {key: round(abs(float(row.get("vega", 0.0) or 0.0)) / vega_total, 8) for key, row in sorted(by_underlying.items())} if vega_total > 0 else {}
        premium = sum(float(row.get("expected_premium", 0.0) or 0.0) for row in rows)
        premium_adequacy = premium / max(1.0, weighted_iv)
        status = "UNAVAILABLE" if unavailable else "GREEN"
        return VolatilityRiskReport(
            status=status,
            implied_volatility_exposure=round(iv_exposure, 8),
            vega_concentration=vega_concentration,
            volatility_regime=str(volatility_regime or "UNKNOWN").upper(),
            volatility_expansion_risk=round(iv_exposure * 1.25, 8),
            volatility_contraction_risk=round(iv_exposure * 0.75, 8),
            premium_adequacy=round(premium_adequacy, 8),
            short_volatility_concentration=round(max(vega_concentration.values(), default=0.0), 8),
            expiry_volatility_exposure={key: round(value / total_collateral, 8) for key, value in sorted(expiry.items())} if total_collateral > 0 else {},
            unavailable=sorted(unavailable),
        )


def _iv(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeVolatilityRiskError("Invalid implied volatility") from exc
    if not isfinite(number) or number <= 0.0:
        raise OptionsIncomeVolatilityRiskError("Invalid implied volatility")
    return number


__all__ = ["OptionsIncomeVolatilityRiskAnalyzer", "OptionsIncomeVolatilityRiskError", "VolatilityRiskReport"]
