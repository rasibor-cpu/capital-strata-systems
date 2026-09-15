from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import random
from typing import Sequence


@dataclass(frozen=True)
class MonteCarloResult:
    paths: int
    horizon: int
    seed: int
    median_terminal_return_pct: Decimal
    p05_terminal_return_pct: Decimal
    p95_terminal_return_pct: Decimal
    probability_of_loss: Decimal
    median_max_drawdown_pct: Decimal
    p95_max_drawdown_pct: Decimal
    status: str


def _quantile(sorted_values: Sequence[Decimal], q: Decimal) -> Decimal:
    if not sorted_values:
        raise ValueError("quantile requires values")
    if not (Decimal("0") <= q <= Decimal("1")):
        raise ValueError("q must be in [0,1]")
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = int((Decimal(len(sorted_values) - 1) * q).to_integral_value(rounding="ROUND_HALF_UP"))
    return sorted_values[idx]


def run_bootstrap_monte_carlo(
    historical_returns: Sequence[Decimal],
    *,
    paths: int = 1000,
    horizon: int = 50,
    seed: int = 155,
) -> MonteCarloResult:
    if len(historical_returns) < 2:
        raise ValueError("at least two historical returns are required")
    if any(not x.is_finite() for x in historical_returns):
        raise ValueError("historical returns must be finite")
    if any(x <= Decimal("-1") for x in historical_returns):
        raise ValueError("returns must be greater than -100%")
    if paths <= 0 or horizon <= 0:
        raise ValueError("paths and horizon must be positive")

    rng = random.Random(seed)
    terminal: list[Decimal] = []
    max_drawdowns: list[Decimal] = []

    for _ in range(paths):
        equity = Decimal("1")
        peak = Decimal("1")
        max_dd = Decimal("0")

        for _ in range(horizon):
            r = historical_returns[rng.randrange(len(historical_returns))]
            equity *= Decimal("1") + r
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else Decimal("1")
            if drawdown > max_dd:
                max_dd = drawdown

        terminal.append(equity - Decimal("1"))
        max_drawdowns.append(max_dd)

    terminal.sort()
    max_drawdowns.sort()
    loss_count = sum(1 for value in terminal if value < 0)
    probability_of_loss = Decimal(loss_count) / Decimal(paths)

    q = Decimal("0.000001")
    return MonteCarloResult(
        paths=paths,
        horizon=horizon,
        seed=seed,
        median_terminal_return_pct=_quantile(terminal, Decimal("0.50")).quantize(q),
        p05_terminal_return_pct=_quantile(terminal, Decimal("0.05")).quantize(q),
        p95_terminal_return_pct=_quantile(terminal, Decimal("0.95")).quantize(q),
        probability_of_loss=probability_of_loss.quantize(q),
        median_max_drawdown_pct=_quantile(max_drawdowns, Decimal("0.50")).quantize(q),
        p95_max_drawdown_pct=_quantile(max_drawdowns, Decimal("0.95")).quantize(q),
        status="RESEARCH_ONLY",
    )
