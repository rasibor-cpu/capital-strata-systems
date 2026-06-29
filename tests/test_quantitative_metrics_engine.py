from __future__ import annotations

from backend.portfolio.quantitative_metrics_engine import QuantitativeMetricsEngine


def test_quantitative_metrics_compute_normal_metrics() -> None:
    result = QuantitativeMetricsEngine().compute(
        portfolio_returns=[0.02, -0.01, 0.015, 0.01, -0.005],
        benchmark_returns=[0.01, -0.005, 0.01, 0.004, -0.002],
        asset_returns={
            "equities": [0.01, 0.02, -0.005],
            "fx": [0.002, -0.001, 0.003],
        },
    )

    assert result["status"] == "OK"
    assert result["sample_size"] == 5
    assert result["advisory_only"] is True
    assert result["metrics"]["rolling_sharpe"] is not None
    assert result["metrics"]["rolling_sortino"] is not None
    assert result["metrics"]["max_drawdown"] >= 0.0
    assert result["metrics"]["volatility"] > 0.0
    assert result["metrics"]["beta"] is not None
    assert result["correlation_matrix"]["EQUITIES"]["EQUITIES"] == 1.0


def test_quantitative_metrics_insufficient_data_fails_closed() -> None:
    result = QuantitativeMetricsEngine().compute([0.01])

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["metrics"] == {}
    assert result["advisory_only"] is True


def test_quantitative_metrics_malformed_input_fails_closed() -> None:
    result = QuantitativeMetricsEngine().compute("not-a-series")

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["sample_size"] == 0
