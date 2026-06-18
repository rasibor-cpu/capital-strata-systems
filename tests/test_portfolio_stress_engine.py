import pytest

from engine.risk.portfolio_stress_engine import (
    PortfolioExposure,
    PortfolioStressEngine,
)


def test_portfolio_stress_engine_equity_down_5():
    engine = PortfolioStressEngine()
    exposures = [
        PortfolioExposure(
            symbol="SPY",
            asset_class="ETF",
            delta_exposure=10000.0,
        )
    ]

    result = engine.stress_one(exposures, "SPY_DOWN_5")

    assert result.scenario == "SPY_DOWN_5"
    assert result.equity_impact == -500.0
    assert result.estimated_pnl == -500.0


def test_portfolio_stress_engine_vol_plus_20():
    engine = PortfolioStressEngine()
    exposures = [
        PortfolioExposure(
            symbol="SPY_CALL",
            asset_class="OPTIONS",
            vega_exposure=2500.0,
        )
    ]

    result = engine.stress_one(exposures, "VOL_PLUS_20")

    assert result.scenario == "VOL_PLUS_20"
    assert result.volatility_impact == 500.0
    assert result.estimated_pnl == 500.0


def test_portfolio_stress_engine_fx_usd_plus_10():
    engine = PortfolioStressEngine()
    exposures = [
        PortfolioExposure(
            symbol="EUR_USD",
            asset_class="FX",
            fx_exposure=7000.0,
        )
    ]

    result = engine.stress_one(exposures, "FX_USD_PLUS_10")

    assert result.scenario == "FX_USD_PLUS_10"
    assert result.fx_impact == 700.0
    assert result.estimated_pnl == 700.0


def test_portfolio_stress_engine_unknown_scenario_raises():
    engine = PortfolioStressEngine()

    with pytest.raises(ValueError):
        engine.stress_one([], "UNKNOWN_SCENARIO")


def test_portfolio_stress_engine_stress_all_returns_all_scenarios():
    engine = PortfolioStressEngine()
    results = engine.stress_all([])

    assert len(results) == len(engine.scenarios)