from __future__ import annotations

from backend.portfolio.diversification_optimizer import DiversificationOptimizer
from backend.portfolio.opportunity_portfolio_ranker import OpportunityPortfolioRanker
from backend.portfolio.portfolio_construction_intelligence import PortfolioConstructionIntelligenceEngine
from backend.portfolio.portfolio_intelligence_engine import PortfolioIntelligenceEngine
from backend.portfolio.portfolio_resilience_analyzer import PortfolioResilienceAnalyzer


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


def _diversified():
    return [
        _opp("crypto", symbol="BTC-USD", asset_class="CRYPTO", sector="DIGITAL", currency="USD", regime="RISK_ON", factor_exposure=["momentum"], expected_return=18),
        _opp("fx", symbol="EUR_USD", asset_class="FX", sector="MACRO", country="EU", currency="EUR", regime="RANGING", factor_exposure=["carry"], expected_return=8, beta=0.4),
        _opp("equity", symbol="SPY", asset_class="EQUITY", sector="INDEX", currency="USD", regime="LOW_VOLATILITY", factor_exposure=["quality"], expected_return=10, beta=0.8),
        _opp("bond", symbol="TLT", asset_class="FIXED_INCOME", sector="RATES", currency="USD", regime="RISK_OFF", factor_exposure=["duration"], expected_return=5, beta=0.2),
    ]


def _concentrated():
    return [
        _opp("tech_a", symbol="AAPL", asset_class="EQUITY", sector="TECHNOLOGY", industry="SOFTWARE", factor_exposure=["growth"], expected_return=12, correlations={"tech_b": 0.9, "tech_c": 0.85}),
        _opp("tech_b", symbol="MSFT", asset_class="EQUITY", sector="TECHNOLOGY", industry="SOFTWARE", factor_exposure=["growth"], expected_return=11, correlations={"tech_a": 0.9, "tech_c": 0.88}),
        _opp("tech_c", symbol="NVDA", asset_class="EQUITY", sector="TECHNOLOGY", industry="SEMIS", factor_exposure=["growth"], expected_return=16, expected_drawdown=8, correlations={"tech_a": 0.85, "tech_b": 0.88}),
    ]


def test_phase157b_highly_diversified_portfolio_scores_well() -> None:
    result = PortfolioConstructionIntelligenceEngine().analyze(_diversified())

    assert result["status"] == "OK"
    assert result["portfolio_quality"] >= 80.0
    assert result["diversification"] >= 70.0
    assert "Preferred portfolio identified" in result["recommendations"]
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False
    assert result["broker_execution_armed"] is False


def test_phase157b_highly_concentrated_portfolio_warns() -> None:
    result = PortfolioResilienceAnalyzer().analyze(_concentrated())

    assert result["status"] == "OK"
    assert result["concentration_score"] > 60.0
    assert "Over-concentrated portfolio" in result["recommendations"]
    assert any("TECHNOLOGY" in item for item in result["recommendations"])


def test_phase157b_correlated_opportunities_reduce_diversification() -> None:
    correlated = PortfolioResilienceAnalyzer().analyze(_concentrated())
    uncorrelated = PortfolioResilienceAnalyzer().analyze(_diversified())

    assert correlated["portfolio_correlation"] > uncorrelated["portfolio_correlation"]
    assert correlated["diversification"] < uncorrelated["diversification"]


def test_phase157b_conflicting_opportunities_are_penalized_by_correlation() -> None:
    opportunities = [
        _opp("long_usd", symbol="UUP", asset_class="FX", sector="USD", currency="USD", regime="RISK_OFF", factor_exposure=["usd_long"], correlations={"short_usd": 1.0}),
        _opp("short_usd", symbol="EUR_USD", asset_class="FX", sector="USD", currency="EUR", regime="RISK_ON", factor_exposure=["usd_short"], correlations={"long_usd": 1.0}),
    ]

    result = PortfolioResilienceAnalyzer().analyze(opportunities)

    assert result["portfolio_correlation"] == 1.0
    assert "Reduce correlation" in result["recommendations"]


def test_phase157b_sector_currency_factor_and_regime_concentration() -> None:
    concentrated = [
        _opp("a", symbol="AAPL", asset_class="EQUITY", sector="TECHNOLOGY", currency="USD", regime="RISK_ON", factor_exposure=["growth"]),
        _opp("b", symbol="MSFT", asset_class="EQUITY", sector="TECHNOLOGY", currency="USD", regime="RISK_ON", factor_exposure=["growth"]),
        _opp("c", symbol="NVDA", asset_class="EQUITY", sector="TECHNOLOGY", currency="USD", regime="RISK_ON", factor_exposure=["growth"]),
    ]

    result = PortfolioResilienceAnalyzer().analyze(concentrated)

    assert result["exposures"]["sector"]["TECHNOLOGY"] == 100.0
    assert result["exposures"]["currency"]["USD"] == 100.0
    assert result["factor_exposure"]["GROWTH"] == 100.0
    assert result["exposures"]["regime"]["RISK_ON"] == 100.0
    assert "Reduce GROWTH factor concentration" in result["recommendations"]


def test_phase157b_portfolio_ranking_prefers_diversifying_high_quality_opportunity() -> None:
    opportunities = [
        *_concentrated(),
        _opp("fx_diversifier", symbol="USD_JPY", asset_class="FX", sector="MACRO", currency="JPY", regime="RANGING", factor_exposure=["carry"], expected_return=9, expected_drawdown=2, beta=0.2),
    ]

    ranked = OpportunityPortfolioRanker().rank(opportunities)

    assert ranked["status"] == "OK"
    assert ranked["ranked_opportunities"][0]["opportunity_id"] == "fx_diversifier"
    assert ranked["ranked_opportunities"][0]["portfolio_diversification_contribution"] > 0.0


def test_phase157b_portfolio_replacement_recommendation() -> None:
    opportunities = [
        *_concentrated(),
        _opp("fx_diversifier", symbol="EUR_USD", asset_class="FX", sector="MACRO", currency="EUR", regime="RANGING", factor_exposure=["carry"], expected_return=9, expected_drawdown=2, beta=0.2),
    ]

    result = DiversificationOptimizer().optimize(opportunities, max_positions=3)

    assert result["status"] == "OK"
    assert result["replacement_candidates"]
    assert any(item.startswith("Replace ") for item in result["recommendations"])
    assert any(row["opportunity_id"] == "fx_diversifier" for row in result["preferred_portfolio"])


def test_phase157b_portfolio_resilience_scores_are_reported() -> None:
    result = PortfolioResilienceAnalyzer().analyze(_diversified())

    assert 0.0 <= result["resilience"] <= 100.0
    assert 0.0 <= result["expected_stability"] <= 100.0
    assert 0.0 <= result["overall_portfolio_intelligence_score"] <= 100.0
    assert result["portfolio_beta"] >= 0.0


def test_phase157b_fail_closed_behaviour() -> None:
    result = PortfolioConstructionIntelligenceEngine().analyze(None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["preferred_portfolio"] == []
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False


def test_phase157b_regression_existing_portfolio_framework_unchanged() -> None:
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
    assert result["execution_allowed"] is False


def test_phase157b_integration_flags_do_not_change_execution_or_allocation() -> None:
    result = PortfolioConstructionIntelligenceEngine().analyze(
        _diversified(),
        decision_confidence={"status": "OK"},
        adaptive_strategy_intelligence={"status": "OK"},
        opportunity_intelligence={"status": "OK"},
        dashboard_context={"view": "portfolio"},
    )

    assert result["integration"]["decision_confidence_consumed"] is True
    assert result["integration"]["adaptive_strategy_intelligence_consumed"] is True
    assert result["integration"]["opportunity_intelligence_consumed"] is True
    assert result["integration"]["portfolio_dashboard_ready"] is True
    assert result["integration"]["execution_decisions_changed"] is False
    assert result["integration"]["capital_allocation_changed"] is False
