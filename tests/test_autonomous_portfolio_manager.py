from __future__ import annotations

import pytest

from backend.analytics.autonomous_portfolio_manager import (
    AutonomousPortfolioManager,
    AutonomousPortfolioManagerError,
)


def _opportunities() -> list[dict[str, object]]:
    return [
        {
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "selected_strategy": "momentum_breakout",
            "market_regime": "TRENDING",
            "confidence": 0.72,
            "opportunity_score": 78.0,
            "expected_reward": 120.0,
            "expected_risk": 45.0,
        },
        {
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "selected_strategy": "macro_trend",
            "market_regime": "RANGING",
            "confidence": 0.61,
            "opportunity_score": 64.0,
            "expected_reward": 40.0,
            "expected_risk": 30.0,
        },
        {
            "symbol": "ES",
            "asset_class": "FUTURES",
            "selected_strategy": "futures_trend",
            "market_regime": "BREAKOUT",
            "confidence": 0.67,
            "opportunity_score": 71.0,
            "expected_reward": 90.0,
            "expected_risk": 50.0,
        },
    ]


def _positions() -> list[dict[str, object]]:
    return [
        {"symbol": "BTC-USD", "asset_class": "CRYPTO", "market_value": 25000.0, "side": "LONG"},
        {"symbol": "EUR_USD", "asset_class": "FX", "market_value": 12000.0, "side": "SHORT"},
    ]


def _learning() -> list[dict[str, object]]:
    return [
        {"symbol": "BTC-USD", "strategy_id": "momentum_breakout", "market_regime": "TRENDING", "realized_pnl": 140.0},
        {"symbol": "BTC-USD", "strategy_id": "momentum_breakout", "market_regime": "TRENDING", "realized_pnl": -40.0},
        {"symbol": "EUR_USD", "strategy_id": "macro_trend", "market_regime": "RANGING", "realized_pnl": 20.0},
    ]


def test_portfolio_manager_recommendation_shape() -> None:
    manager = AutonomousPortfolioManager()
    result = manager.recommend(
        opportunities=_opportunities(),
        current_positions=_positions(),
        total_capital=100000.0,
        available_capital=70000.0,
        reserved_capital=30000.0,
        learning_records=_learning(),
    )

    assert "capital" in result
    assert "portfolio_allocation" in result
    assert "dynamic_position_sizing" in result
    assert "correlation" in result
    assert "diversification" in result
    assert "expected_model" in result
    assert "portfolio_optimizer" in result
    assert "capital_preservation" in result
    assert "explainability" in result

    assert result["capital"]["maximum_capital"] == 100000.0
    assert result["capital"]["available_capital"] == 70000.0
    assert result["capital"]["reserved_capital"] == 30000.0


def test_portfolio_manager_contains_diversification_and_explainability() -> None:
    manager = AutonomousPortfolioManager()
    result = manager.recommend(
        opportunities=_opportunities(),
        current_positions=_positions(),
        total_capital=100000.0,
        available_capital=70000.0,
        reserved_capital=30000.0,
        learning_records=_learning(),
    )

    diversification = result["diversification"]
    explainability = result["explainability"]

    assert 0.0 <= diversification["diversification_score"] <= 1.0
    assert isinstance(diversification["missing_asset_classes"], list)
    assert isinstance(diversification["suggested_rebalancing"], list)

    assert isinstance(explainability["why_allocated"], list)
    assert isinstance(explainability["why_not_allocated"], list)
    assert isinstance(explainability["expected_contribution"], list)
    assert "portfolio_impact" in explainability
    assert "diversification_impact" in explainability


def test_portfolio_manager_fail_closed_invalid_capital() -> None:
    manager = AutonomousPortfolioManager()
    with pytest.raises(AutonomousPortfolioManagerError):
        manager.recommend(
            opportunities=_opportunities(),
            current_positions=_positions(),
            total_capital=1000.0,
            available_capital=900.0,
            reserved_capital=200.0,
            learning_records=_learning(),
        )


def test_position_sizing_output_contains_units_notional_risk() -> None:
    manager = AutonomousPortfolioManager()
    result = manager.recommend(
        opportunities=_opportunities(),
        current_positions=_positions(),
        total_capital=100000.0,
        available_capital=70000.0,
        reserved_capital=30000.0,
        learning_records=_learning(),
    )

    rows = result["dynamic_position_sizing"]["rows"]
    assert rows
    first = rows[0]
    assert "suggested_units" in first
    assert "suggested_notional" in first
    assert "suggested_risk" in first
