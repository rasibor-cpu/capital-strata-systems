"""
Capital Strata Systems
Phase 93

Portfolio Value-at-Risk Engine
"""

from dataclasses import dataclass
from math import sqrt
from statistics import pstdev
from typing import Iterable, List


@dataclass(frozen=True)
class ReturnSeries:
    symbol: str
    returns: List[float]


@dataclass(frozen=True)
class VaRResult:
    confidence_level: float
    volatility: float
    portfolio_value: float
    one_day_var: float


class PortfolioVaREngine:
    """
    Deterministic historical-volatility VaR engine.

    Initial implementation:
    - population volatility
    - square-root-of-time
    - normal approximation
    """

    Z_SCORES = {
        0.90: 1.282,
        0.95: 1.645,
        0.99: 2.326,
    }

    def calculate_var(
        self,
        portfolio_value: float,
        returns: Iterable[float],
        confidence_level: float = 0.95,
    ) -> VaRResult:

        returns = list(returns)

        if len(returns) < 2:
            raise ValueError("At least two returns required")

        if confidence_level not in self.Z_SCORES:
            raise ValueError("Unsupported confidence level")

        volatility = pstdev(returns)

        z = self.Z_SCORES[confidence_level]

        var_amount = portfolio_value * volatility * z

        return VaRResult(
            confidence_level=confidence_level,
            volatility=round(volatility, 6),
            portfolio_value=round(portfolio_value, 2),
            one_day_var=round(var_amount, 2),
        )