from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BenchmarkMetrics:
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    sharpe_ratio: Decimal


@dataclass(frozen=True)
class BenchmarkPolicy:
    min_excess_return_pct: Decimal = Decimal("0")
    min_sharpe_spread: Decimal = Decimal("0")
    max_drawdown_disadvantage_pct: Decimal = Decimal("0.02")


@dataclass(frozen=True)
class BenchmarkComparison:
    excess_return_pct: Decimal
    sharpe_spread: Decimal
    drawdown_difference_pct: Decimal
    status: str
    reason_codes: tuple[str, ...]
    approved_for_research: bool


def _validate(metrics: BenchmarkMetrics, prefix: str) -> list[str]:
    errors: list[str] = []
    for name, value in (
        ("total_return_pct", metrics.total_return_pct),
        ("max_drawdown_pct", metrics.max_drawdown_pct),
        ("sharpe_ratio", metrics.sharpe_ratio),
    ):
        if not value.is_finite():
            errors.append(f"{prefix}_{name}:NON_FINITE")
    if metrics.max_drawdown_pct < 0 or metrics.max_drawdown_pct > 1:
        errors.append(f"{prefix}_max_drawdown_pct:OUT_OF_RANGE")
    return errors


def compare_with_benchmark(
    strategy: BenchmarkMetrics,
    benchmark: BenchmarkMetrics,
    policy: BenchmarkPolicy | None = None,
) -> BenchmarkComparison:
    policy = policy or BenchmarkPolicy()
    errors = _validate(strategy, "strategy") + _validate(benchmark, "benchmark")

    excess = strategy.total_return_pct - benchmark.total_return_pct
    sharpe_spread = strategy.sharpe_ratio - benchmark.sharpe_ratio
    drawdown_difference = strategy.max_drawdown_pct - benchmark.max_drawdown_pct

    if errors:
        return BenchmarkComparison(
            excess_return_pct=excess,
            sharpe_spread=sharpe_spread,
            drawdown_difference_pct=drawdown_difference,
            status="INVALID",
            reason_codes=tuple(errors),
            approved_for_research=False,
        )

    reasons: list[str] = []
    if excess <= policy.min_excess_return_pct:
        reasons.append("EXCESS_RETURN_NOT_ABOVE_MINIMUM")
    if sharpe_spread < policy.min_sharpe_spread:
        reasons.append("SHARPE_SPREAD_BELOW_MINIMUM")
    if drawdown_difference > policy.max_drawdown_disadvantage_pct:
        reasons.append("DRAWDOWN_DISADVANTAGE_TOO_HIGH")

    passed = not reasons
    return BenchmarkComparison(
        excess_return_pct=excess,
        sharpe_spread=sharpe_spread,
        drawdown_difference_pct=drawdown_difference,
        status="OUTPERFORM" if passed else "REVIEW_REQUIRED",
        reason_codes=tuple(reasons),
        approved_for_research=passed,
    )
