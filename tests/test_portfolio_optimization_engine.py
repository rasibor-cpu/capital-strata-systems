import pytest

from backend.analytics import PortfolioOptimizationEngine, PortfolioOptimizationError


def test_approved_portfolio_recommendation():
    engine = PortfolioOptimizationEngine()
    recommendations = engine.optimize(
        [
            {
                "symbol": "AAPL",
                "asset_class": "equity",
                "strategy_id": "mean",
                "allocation_weight": 0.6,
            }
        ],
        [{"symbol": "AAPL", "recommended_position_size": 120.0}],
        [{"symbol": "AAPL", "recommendation": "PROMOTE"}],
        asset_class_exposure_limits={"equity": 1000.0},
        max_symbol_exposure=250.0,
        max_total_allocation=1000.0,
    )

    assert recommendations[0]["portfolio_status"] == "APPROVED"
    assert recommendations[0]["recommended_position_size"] == pytest.approx(120.0)


def test_symbol_exposure_cap():
    engine = PortfolioOptimizationEngine()
    recommendations = engine.optimize(
        [{"symbol": "AAPL", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.6}],
        [{"symbol": "AAPL", "recommended_position_size": 400.0}],
        [{"symbol": "AAPL", "recommendation": "PROMOTE"}],
        asset_class_exposure_limits={"equity": 1000.0},
        max_symbol_exposure=250.0,
        max_total_allocation=1000.0,
    )

    assert recommendations[0]["portfolio_status"] == "REDUCED"
    assert recommendations[0]["recommended_position_size"] == pytest.approx(250.0)


def test_asset_class_exposure_cap():
    engine = PortfolioOptimizationEngine()
    recommendations = engine.optimize(
        [
            {"symbol": "AAPL", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.6},
            {"symbol": "MSFT", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.4},
        ],
        [{"symbol": "AAPL", "recommended_position_size": 150.0}, {"symbol": "MSFT", "recommended_position_size": 150.0}],
        [{"symbol": "AAPL", "recommendation": "PROMOTE"}, {"symbol": "MSFT", "recommendation": "PROMOTE"}],
        asset_class_exposure_limits={"equity": 200.0},
        max_symbol_exposure=500.0,
        max_total_allocation=1000.0,
    )

    assert recommendations[0]["portfolio_status"] == "APPROVED"
    assert recommendations[1]["portfolio_status"] == "REDUCED"
    assert recommendations[1]["recommended_position_size"] == pytest.approx(50.0)


def test_demoted_strategy_reduction():
    engine = PortfolioOptimizationEngine()
    recommendations = engine.optimize(
        [{"symbol": "AAPL", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.6}],
        [{"symbol": "AAPL", "recommended_position_size": 100.0}],
        [{"symbol": "AAPL", "recommendation": "DEMOTE"}],
        asset_class_exposure_limits={"equity": 1000.0},
        max_symbol_exposure=500.0,
        max_total_allocation=1000.0,
    )

    assert recommendations[0]["portfolio_status"] == "REDUCED"
    assert recommendations[0]["recommended_position_size"] == pytest.approx(50.0)


def test_disabled_strategy_block():
    engine = PortfolioOptimizationEngine()
    recommendations = engine.optimize(
        [{"symbol": "AAPL", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.6}],
        [{"symbol": "AAPL", "recommended_position_size": 100.0}],
        [{"symbol": "AAPL", "recommendation": "DISABLE"}],
        asset_class_exposure_limits={"equity": 1000.0},
        max_symbol_exposure=500.0,
        max_total_allocation=1000.0,
    )

    assert recommendations[0]["portfolio_status"] == "BLOCKED"
    assert recommendations[0]["recommended_position_size"] == pytest.approx(0.0)


def test_restricted_symbol_block():
    engine = PortfolioOptimizationEngine()
    recommendations = engine.optimize(
        [{"symbol": "AAPL", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.0}],
        [{"symbol": "AAPL", "recommended_position_size": 100.0}],
        [{"symbol": "AAPL", "recommendation": "PROMOTE"}],
        asset_class_exposure_limits={"equity": 1000.0},
        max_symbol_exposure=500.0,
        max_total_allocation=1000.0,
    )

    assert recommendations[0]["portfolio_status"] == "RESTRICTED"
    assert recommendations[0]["recommended_position_size"] == pytest.approx(0.0)


def test_empty_input_behavior():
    engine = PortfolioOptimizationEngine()
    assert engine.optimize([], [], [], asset_class_exposure_limits={"equity": 1000.0}, max_symbol_exposure=500.0, max_total_allocation=1000.0) == []


def test_invalid_exposure_limits_fail_closed():
    engine = PortfolioOptimizationEngine()

    with pytest.raises(PortfolioOptimizationError):
        engine.optimize(
            [{"symbol": "AAPL", "asset_class": "equity", "strategy_id": "mean", "allocation_weight": 0.6}],
            [{"symbol": "AAPL", "recommended_position_size": 100.0}],
            [{"symbol": "AAPL", "recommendation": "PROMOTE"}],
            asset_class_exposure_limits={"equity": -1.0},
            max_symbol_exposure=500.0,
            max_total_allocation=1000.0,
        )
