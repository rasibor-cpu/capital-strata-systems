from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class BenchmarkResult:
    learner_return_pct: Decimal
    benchmark_return_pct: Decimal
    excess_return_pct: Decimal
    observations: int


class BenchmarkEngine:
    @staticmethod
    def total_return(prices: Sequence[Decimal]) -> Decimal:
        if len(prices) < 2:
            raise ValueError("at least two benchmark observations are required")
        if prices[0] <= Decimal("0") or any(value <= Decimal("0") for value in prices):
            raise ValueError("benchmark prices must be positive")
        return (prices[-1] - prices[0]) / prices[0]

    @classmethod
    def compare(
        cls,
        learner_start_equity: Decimal,
        learner_end_equity: Decimal,
        benchmark_prices: Sequence[Decimal],
    ) -> BenchmarkResult:
        if learner_start_equity <= Decimal("0"):
            raise ValueError("learner_start_equity must be positive")
        learner_return = (
            learner_end_equity - learner_start_equity
        ) / learner_start_equity
        benchmark_return = cls.total_return(benchmark_prices)
        return BenchmarkResult(
            learner_return_pct=learner_return,
            benchmark_return_pct=benchmark_return,
            excess_return_pct=learner_return - benchmark_return,
            observations=len(benchmark_prices),
        )
