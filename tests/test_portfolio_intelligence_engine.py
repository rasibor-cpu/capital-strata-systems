from __future__ import annotations

from backend.portfolio.portfolio_intelligence_engine import PortfolioIntelligenceEngine


def test_portfolio_intelligence_penalizes_risk_dimensions_deterministically() -> None:
    positions = [
        {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 70000.0},
        {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 20000.0},
        {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 10000.0},
    ]
    metrics = {
        "max_drawdown": 0.18,
        "sortino": 0.4,
        "capital_efficiency": 0.25,
        "correlation_score": 0.82,
    }

    first = PortfolioIntelligenceEngine().analyze(positions, metrics)
    second = PortfolioIntelligenceEngine().analyze(list(reversed(positions)), metrics)

    assert first == second
    assert first["status"] == "OK"
    assert first["advisory_only"] is True
    assert first["execution_allowed"] is False
    assert first["portfolio_status"] == "DEFENSIVE"
    assert first["recommendation"] == "REDUCE_RISK"
    assert first["penalties"]["drawdown"] > 0
    assert first["penalties"]["sortino"] > 0
    assert first["penalties"]["capital_efficiency"] > 0
    assert first["penalties"]["concentration"] > 0
    assert first["penalties"]["correlation"] > 0
    assert any("High drawdown" in item for item in first["explainability"])
    assert any("Weak Sortino" in item for item in first["explainability"])


def test_portfolio_intelligence_healthy_portfolio_is_explainable() -> None:
    result = PortfolioIntelligenceEngine().analyze(
        [
            {"symbol": "SPY", "asset_class": "EQUITIES", "market_value": 40000.0},
            {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 35000.0},
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 25000.0},
        ],
        {
            "max_drawdown": 0.02,
            "sortino": 2.1,
            "capital_efficiency": 0.75,
            "correlation_score": 0.20,
        },
    )

    assert result["portfolio_status"] == "HEALTHY"
    assert result["recommendation"] == "MAINTAIN"
    assert result["intelligence_score"] == 100.0
    assert result["by_asset_class"] == {"CRYPTO": 25.0, "EQUITIES": 40.0, "FX": 35.0}


def test_portfolio_intelligence_fails_closed_when_data_unavailable() -> None:
    result = PortfolioIntelligenceEngine().analyze(None, {})

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert result["recommendation"] == "NO_ACTION"
    assert result["intelligence_score"] == 0.0


def test_portfolio_intelligence_returns_limited_for_no_current_exposure() -> None:
    result = PortfolioIntelligenceEngine().analyze([], {})

    assert result["status"] == "LIMITED"
    assert result["portfolio_status"] == "NO_PORTFOLIO"
    assert result["recommendation"] == "HOLD_CURRENT"
    assert result["execution_allowed"] is False
