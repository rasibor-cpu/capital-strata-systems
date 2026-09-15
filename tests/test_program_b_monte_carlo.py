from decimal import Decimal

import pytest

from backend.research.monte_carlo import run_bootstrap_monte_carlo


RETURNS = (
    Decimal("0.01"),
    Decimal("-0.005"),
    Decimal("0.015"),
    Decimal("0.002"),
    Decimal("-0.003"),
)


def test_monte_carlo_is_deterministic_for_seed():
    a = run_bootstrap_monte_carlo(RETURNS, paths=200, horizon=20, seed=42)
    b = run_bootstrap_monte_carlo(RETURNS, paths=200, horizon=20, seed=42)
    assert a == b


def test_result_contains_bounded_probability_and_drawdowns():
    result = run_bootstrap_monte_carlo(RETURNS, paths=200, horizon=20, seed=1)
    assert Decimal("0") <= result.probability_of_loss <= Decimal("1")
    assert result.median_max_drawdown_pct >= 0
    assert result.p95_max_drawdown_pct >= result.median_max_drawdown_pct
    assert result.status == "RESEARCH_ONLY"


def test_percentile_ordering_is_valid():
    result = run_bootstrap_monte_carlo(RETURNS, paths=500, horizon=30, seed=9)
    assert result.p05_terminal_return_pct <= result.median_terminal_return_pct
    assert result.median_terminal_return_pct <= result.p95_terminal_return_pct


def test_positive_history_has_nonnegative_loss_probability():
    result = run_bootstrap_monte_carlo(
        (Decimal("0.01"), Decimal("0.02"), Decimal("0.005")),
        paths=100,
        horizon=10,
        seed=3,
    )
    assert result.probability_of_loss == Decimal("0.000000")


def test_invalid_history_fails_closed():
    with pytest.raises(ValueError):
        run_bootstrap_monte_carlo((Decimal("0.01"),))
    with pytest.raises(ValueError):
        run_bootstrap_monte_carlo((Decimal("NaN"), Decimal("0.01")))
    with pytest.raises(ValueError):
        run_bootstrap_monte_carlo((Decimal("-1"), Decimal("0.01")))


@pytest.mark.parametrize(("paths", "horizon"), [(0, 10), (10, 0), (-1, 10), (10, -1)])
def test_invalid_dimensions_fail_closed(paths, horizon):
    with pytest.raises(ValueError):
        run_bootstrap_monte_carlo(RETURNS, paths=paths, horizon=horizon)


def test_no_execution_surface():
    result = run_bootstrap_monte_carlo(RETURNS, paths=10, horizon=5)
    assert not hasattr(result, "place_order")
    assert not hasattr(result, "execute")
