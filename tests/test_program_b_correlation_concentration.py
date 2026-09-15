from decimal import Decimal

import pytest

from backend.research.correlation_analysis import (
    classify_correlation,
    correlation_pairs,
    detect_hidden_concentration,
    pearson_correlation,
)


def D(*values):
    return tuple(Decimal(str(v)) for v in values)


def test_perfect_positive_correlation():
    result = pearson_correlation(D(1, 2, 3, 4), D(2, 4, 6, 8))
    assert result == Decimal("1.000000")


def test_perfect_negative_correlation():
    result = pearson_correlation(D(1, 2, 3, 4), D(8, 6, 4, 2))
    assert result == Decimal("-1.000000")


def test_neutralish_relationship_classification():
    assert classify_correlation(Decimal("0.20")) == "NEUTRAL"
    assert classify_correlation(Decimal("0.80")) == "STRONGLY_POSITIVE"
    assert classify_correlation(Decimal("-0.80")) == "STRONGLY_NEGATIVE"


def test_pair_generation_is_deterministic():
    pairs = correlation_pairs({
        "MSFT": D(1, 2, 3, 4),
        "AAPL": D(2, 4, 6, 8),
        "BTC": D(4, 3, 2, 1),
    })
    assert [(p.asset_a, p.asset_b) for p in pairs] == [
        ("AAPL", "BTC"),
        ("AAPL", "MSFT"),
        ("BTC", "MSFT"),
    ]


def test_hidden_concentration_detects_correlated_heavy_pair():
    pairs = correlation_pairs({
        "AAPL": D(1, 2, 3, 4),
        "MSFT": D(2, 4, 6, 8),
    })
    alerts = detect_hidden_concentration(
        pairs,
        {"AAPL": Decimal("0.25"), "MSFT": Decimal("0.25")},
    )
    assert len(alerts) == 1
    assert alerts[0].severity == "HIGH"
    assert alerts[0].combined_weight == Decimal("0.50")


def test_small_correlated_weights_do_not_alert():
    pairs = correlation_pairs({
        "AAPL": D(1, 2, 3, 4),
        "MSFT": D(2, 4, 6, 8),
    })
    alerts = detect_hidden_concentration(
        pairs,
        {"AAPL": Decimal("0.10"), "MSFT": Decimal("0.10")},
    )
    assert alerts == ()


def test_negative_correlation_does_not_trigger_hidden_concentration():
    pairs = correlation_pairs({
        "A": D(1, 2, 3, 4),
        "B": D(8, 6, 4, 2),
    })
    alerts = detect_hidden_concentration(
        pairs,
        {"A": Decimal("0.30"), "B": Decimal("0.30")},
    )
    assert alerts == ()


def test_mismatched_series_fail_closed():
    with pytest.raises(ValueError, match="lengths"):
        pearson_correlation(D(1, 2, 3), D(1, 2))


def test_zero_variance_fails_closed():
    with pytest.raises(ValueError, match="zero-variance"):
        pearson_correlation(D(1, 1, 1), D(1, 2, 3))


def test_overallocated_portfolio_fails_closed():
    pairs = correlation_pairs({
        "A": D(1, 2, 3),
        "B": D(2, 4, 6),
    })
    with pytest.raises(ValueError, match="cannot exceed"):
        detect_hidden_concentration(
            pairs,
            {"A": Decimal("0.70"), "B": Decimal("0.50")},
        )


def test_invalid_thresholds_fail_closed():
    with pytest.raises(ValueError):
        detect_hidden_concentration((), {}, correlation_threshold=Decimal("1.1"))
    with pytest.raises(ValueError):
        detect_hidden_concentration((), {}, combined_weight_threshold=Decimal("0"))
