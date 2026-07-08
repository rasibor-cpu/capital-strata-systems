from __future__ import annotations

from backend.portfolio.portfolio_construction_intelligence import PortfolioConstructionIntelligenceEngine
from backend.portfolio.institutional_portfolio_optimizer import InstitutionalPortfolioOptimizer
from backend.portfolio.portfolio_scenario_generator import PortfolioScenarioGenerator
from backend.portfolio.portfolio_tradeoff_analyzer import PortfolioTradeoffAnalyzer
from backend.portfolio.portfolio_efficiency_frontier import PortfolioEfficiencyFrontier


def _opp(
    opportunity_id: str,
    *,
    symbol: str,
    asset_class: str,
    sector: str,
    industry: str = "GENERAL",
    country: str = "US",
    currency: str = "USD",
    regime: str = "RISK_ON",
    factor_exposure=None,
    expected_return: float = 12.0,
    expected_drawdown: float = 3.0,
    expected_volatility: float = 8.0,
    beta: float = 1.0,
    liquidity_score: float = 80.0,
    weight: float = 1.0,
    correlations=None,
):
    return {
        "opportunity_id": opportunity_id,
        "symbol": symbol,
        "approved": True,
        "asset_class": asset_class,
        "sector": sector,
        "industry": industry,
        "country": country,
        "currency": currency,
        "market_regime": regime,
        "factor_exposure": factor_exposure or [],
        "expected_return": expected_return,
        "expected_drawdown": expected_drawdown,
        "expected_volatility": expected_volatility,
        "beta": beta,
        "liquidity_score": liquidity_score,
        "weight": weight,
        "correlations": correlations or {},
    }


def _test_opportunities():
    return [
        # Conservative
        _opp("bond_tlt", symbol="TLT", asset_class="FIXED_INCOME", sector="RATES", factor_exposure=["duration"], expected_return=4.0, expected_drawdown=1.5, expected_volatility=3.0, beta=0.15),
        # Balanced / Income
        _opp("fx_eur", symbol="EUR_USD", asset_class="FX", sector="MACRO", factor_exposure=["carry"], expected_return=7.5, expected_drawdown=3.0, expected_volatility=5.5, beta=0.45),
        # Growth / High Sharpe
        _opp("equity_spy", symbol="SPY", asset_class="EQUITY", sector="INDEX", factor_exposure=["quality", "momentum"], expected_return=12.0, expected_drawdown=5.0, expected_volatility=8.5, beta=0.85),
        # High Risk Growth
        _opp("crypto_btc", symbol="BTC-USD", asset_class="CRYPTO", sector="DIGITAL", factor_exposure=["momentum"], expected_return=28.0, expected_drawdown=18.0, expected_volatility=25.0, beta=1.65),
    ]


def test_phase157c_scenario_generation() -> None:
    opps = _test_opportunities()
    res = PortfolioScenarioGenerator().generate_scenarios(opps, max_positions=3)

    assert res["status"] == "OK"
    scenarios = res["scenarios"]
    assert len(scenarios) == 6

    for name in ["Conservative", "Balanced", "Growth", "Income", "High Sharpe", "High Sortino"]:
        assert name in scenarios
        p = scenarios[name]
        assert p["name"] == name
        assert "expected_return" in p
        assert "expected_volatility" in p
        assert "expected_drawdown" in p
        assert "sharpe" in p
        assert "sortino" in p
        assert "portfolio_beta" in p
        assert "diversification_score" in p
        assert "resilience_score" in p
        assert "concentration_score" in p
        assert "portfolio_quality_score" in p
        assert "capital_efficiency_score" in p
        assert p["advisory_only"] is True
        assert p["execution_allowed"] is False


def test_phase157c_profile_optimality() -> None:
    opps = _test_opportunities()
    res = PortfolioScenarioGenerator().generate_scenarios(opps, max_positions=3)
    scenarios = res["scenarios"]

    # Growth expected return should be higher than Conservative expected return
    assert scenarios["Growth"]["expected_return"] > scenarios["Conservative"]["expected_return"]

    # Conservative expected drawdown should be lower than Growth expected drawdown
    assert scenarios["Conservative"]["expected_drawdown"] < scenarios["Growth"]["expected_drawdown"]

    # Income should select the FX/Fixed Income carry assets
    income_opps = [o["opportunity_id"] for o in scenarios["Income"]["opportunities"]]
    assert any(x in income_opps for x in ["bond_tlt", "fx_eur"])


def test_phase157c_tradeoff_analysis() -> None:
    opps = _test_opportunities()
    scenarios = PortfolioScenarioGenerator().generate_scenarios(opps, max_positions=3)["scenarios"]
    tradeoffs = PortfolioTradeoffAnalyzer().analyze_tradeoffs(scenarios)

    assert len(tradeoffs) > 0
    assert any("Growth" in t for t in tradeoffs)
    assert any("Conservative" in t for t in tradeoffs)


def test_phase157c_efficiency_frontier() -> None:
    opps = _test_opportunities()
    res = PortfolioEfficiencyFrontier().construct_frontier(opps, max_positions=3)

    assert res["status"] == "OK"
    assert len(res["efficient_portfolios"]) > 0

    rankings = res["rankings"]
    assert "by_return" in rankings
    assert "by_risk" in rankings
    assert "by_efficiency" in rankings
    assert "by_resilience" in rankings

    # Verify return ranking sorts descending
    returns = [p["expected_return"] for p in rankings["by_return"]]
    assert returns == sorted(returns, reverse=True)

    # Verify risk ranking sorts ascending
    vols = [p["expected_volatility"] for p in rankings["by_risk"]]
    assert vols == sorted(vols)


def test_phase157c_orchestrator_success() -> None:
    opps = _test_opportunities()
    res = InstitutionalPortfolioOptimizer().optimize(opps, max_positions=3)

    assert res["status"] == "OK"
    assert len(res["recommended_portfolios"]) == 6
    assert res["best_overall"] in ["Conservative", "Balanced", "Growth", "Income", "High Sharpe", "High Sortino"]
    assert len(res["tradeoffs"]) > 0
    assert len(res["efficient_frontier"]) > 0
    assert res["advisory_only"] is True
    assert res["execution_allowed"] is False
    assert res["live_trading_blocked"] is True
    assert res["broker_execution_armed"] is False


def test_phase157c_fail_closed() -> None:
    # Test with None
    res = InstitutionalPortfolioOptimizer().optimize(None)
    assert res["status"] == "DATA UNAVAILABLE"
    assert res["recommended_portfolios"] == []
    assert res["best_overall"] == "DATA UNAVAILABLE"
    assert res["tradeoffs"] == []
    assert res["advisory_only"] is True
    assert res["execution_allowed"] is False
    assert res["live_trading_blocked"] is True
    assert res["broker_execution_armed"] is False

    # Test with empty list
    res2 = InstitutionalPortfolioOptimizer().optimize([])
    assert res2["status"] == "DATA UNAVAILABLE"
    assert res2["recommended_portfolios"] == []
    assert res2["best_overall"] == "DATA UNAVAILABLE"


def test_phase157c_portfolio_construction_intelligence_integration() -> None:
    opps = _test_opportunities()
    res = PortfolioConstructionIntelligenceEngine().analyze(opps, max_positions=3)

    assert res["status"] in {"OK", "PARTIAL"}
    assert "institutional_portfolio_optimization" in res
    inst_res = res["institutional_portfolio_optimization"]
    assert inst_res["status"] == "OK"
    assert len(inst_res["recommended_portfolios"]) == 6
    assert inst_res["advisory_only"] is True
    assert inst_res["execution_allowed"] is False

    # Verify 157B regression: original fields are still present and correct
    assert "preferred_portfolio" in res
    assert "portfolio_quality" in res
    assert "resilience" in res
    assert "diversification" in res
    assert "expected_return" in res
    assert "expected_drawdown" in res
    assert res["advisory_only"] is True
    assert res["execution_allowed"] is False
    assert res["live_trading_blocked"] is True
    assert res["broker_execution_armed"] is False


def test_phase157c_integration_fail_closed() -> None:
    res = PortfolioConstructionIntelligenceEngine().analyze(None)
    assert res["status"] == "DATA UNAVAILABLE"
    assert "institutional_portfolio_optimization" in res
    inst_res = res["institutional_portfolio_optimization"]
    assert inst_res["status"] == "DATA UNAVAILABLE"
    assert res["execution_allowed"] is False
    assert res["live_trading_blocked"] is True
    assert res["broker_execution_armed"] is False
