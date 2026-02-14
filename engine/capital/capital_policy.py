"""
Capital Strata Systems
Capital Policy Profile

Implements:
- 75% FX / 25% Futures allocation
- Session-level policy lock
- No runtime mutation allowed
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalPolicy:
    total_equity: float

    fx_allocation_ratio: float = 0.75
    futures_allocation_ratio: float = 0.25

    def fx_capital(self) -> float:
        return self.total_equity * self.fx_allocation_ratio

    def futures_capital(self) -> float:
        return self.total_equity * self.futures_allocation_ratio


def build_policy(total_equity: float) -> CapitalPolicy:
    return CapitalPolicy(total_equity=total_equity)

