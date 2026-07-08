from __future__ import annotations

from backend.portfolio.portfolio_construction_intelligence import PortfolioConstructionIntelligenceEngine
from backend.portfolio.institutional_portfolio_optimizer import InstitutionalPortfolioOptimizer
from backend.intelligence.investment_committee_engine import InvestmentCommitteeEngine
from backend.intelligence.committee_member_models import (
    ChiefInvestmentOfficer,
    ChiefRiskOfficer,
    PortfolioManager,
    HeadOfTrading,
    QuantitativeResearchLead,
    GovernanceCompliance,
)
from backend.intelligence.committee_consensus_engine import CommitteeConsensusEngine
from backend.intelligence.committee_explainability import CommitteeExplainability


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
    capital_efficiency: float = 0.95,
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
        "capital_efficiency": capital_efficiency,
        "correlations": correlations or {},
    }


def _test_opportunities():
    return [
        _opp("bond_tlt", symbol="TLT", asset_class="FIXED_INCOME", sector="RATES", industry="GOVERNMENT", country="US", currency="USD", regime="RISK_OFF", factor_exposure=["duration"], expected_return=20.0, expected_drawdown=0.5, expected_volatility=1.0, beta=0.2, liquidity_score=95.0, weight=1.0, capital_efficiency=0.95, correlations={}),
        _opp("fx_eur", symbol="EUR_USD", asset_class="FX", sector="MACRO", industry="CURRENCIES", country="DE", currency="EUR", regime="RANGING", factor_exposure=["carry"], expected_return=22.0, expected_drawdown=0.5, expected_volatility=1.0, beta=0.2, liquidity_score=95.0, weight=1.0, capital_efficiency=0.95, correlations={}),
        _opp("equity_spy", symbol="SPY", asset_class="EQUITY", sector="INDEX", industry="LARGE_CAP", country="US", currency="USD", regime="RISK_ON", factor_exposure=["quality"], expected_return=24.0, expected_drawdown=0.5, expected_volatility=1.0, beta=0.2, liquidity_score=95.0, weight=1.0, capital_efficiency=0.95, correlations={}),
    ]


def test_phase158a_unanimous_approval() -> None:
    opps = _test_opportunities()
    opt_res = InstitutionalPortfolioOptimizer().optimize(opps, max_positions=3)
    
    # Context with good conditions
    context = {"confidence": 95.0, "broker_health": "GREEN"}
    res = InvestmentCommitteeEngine().evaluate_portfolio(
        opps,
        decision_confidence=context,
        broker_health={"broker_health": "GREEN"},
        institutional_optimization=opt_res,
    )

    assert res["status"] == "OK"
    assert res["overall_recommendation"] == "APPROVE"
    assert res["committee_vote"]["approve"] >= 5
    assert res["committee_vote"]["reject"] == 0
    assert res["advisory_only"] is True
    assert res["execution_allowed"] is False
    assert res["live_trading_blocked"] is True
    assert res["broker_execution_armed"] is False


def test_phase158a_rejection_due_to_non_advisory() -> None:
    opps = _test_opportunities()
    opt_res = InstitutionalPortfolioOptimizer().optimize(opps, max_positions=3)
    
    # Alter advisory flag to simulate compliance breach
    assert len(opt_res["recommended_portfolios"]) > 0
    opt_res["recommended_portfolios"][0]["advisory_only"] = False
    opt_res["recommended_portfolios"][0]["execution_allowed"] = True

    res = InvestmentCommitteeEngine().evaluate_portfolio(
        opps,
        institutional_optimization=opt_res,
    )

    assert res["status"] == "OK"
    assert res["overall_recommendation"] == "REJECT"
    assert res["committee_vote"]["reject"] > 0


def test_phase158a_cro_rejection_due_to_broker_health_red() -> None:
    opps = _test_opportunities()
    opt_res = InstitutionalPortfolioOptimizer().optimize(opps, max_positions=3)
    
    # Evaluate under RED broker health
    res = InvestmentCommitteeEngine().evaluate_portfolio(
        opps,
        broker_health={"broker_health": "RED"},
        institutional_optimization=opt_res,
    )

    # Risk drops which increases reject/conditional votes
    assert res["status"] == "OK"
    assert res["overall_recommendation"] in {"REJECT", "CONDITIONAL", "NEEDS_REVIEW"}


def test_phase158a_split_committee_and_conditional() -> None:
    opps = _test_opportunities()
    # Modify opportunities to trigger elevated risk (high drawdown, volatility)
    high_risk_opps = [
        _opp("speculative", symbol="SPEC", asset_class="CRYPTO", sector="DIGITAL", expected_return=30.0, expected_drawdown=15.0, expected_volatility=45.0, beta=2.5)
    ]
    opt_res = InstitutionalPortfolioOptimizer().optimize(high_risk_opps, max_positions=1)

    res = InvestmentCommitteeEngine().evaluate_portfolio(
        high_risk_opps,
        decision_confidence={"confidence": 40.0},
        institutional_optimization=opt_res,
    )

    # Some members approve return, CRO/Trading reject/conditional
    assert res["status"] == "OK"
    assert res["overall_recommendation"] in {"REJECT", "CONDITIONAL", "NEEDS_REVIEW"}


def test_phase158a_explainability() -> None:
    opps = _test_opportunities()
    opt_res = InstitutionalPortfolioOptimizer().optimize(opps, max_positions=3)
    res = InvestmentCommitteeEngine().evaluate_portfolio(
        opps,
        institutional_optimization=opt_res,
    )

    assert res["status"] == "OK"
    comments = res["member_comments"]
    assert len(comments) >= 6

    # Verify that different roles commented
    assert any("Chief Investment Officer" in c for c in comments)
    assert any("Chief Risk Officer" in c for c in comments)
    assert any("Portfolio Manager" in c for c in comments)
    assert any("Head of Trading" in c for c in comments)
    assert any("Quantitative Research Lead" in c for c in comments)
    assert any("Governance & Compliance" in c for c in comments)


def test_phase158a_consensus_generation() -> None:
    engine = CommitteeConsensusEngine()
    
    # 6 approvals
    res = engine.compile_consensus({
        "CIO": "Approve",
        "CRO": "Strong Approve",
        "PM": "Approve",
        "Trading": "Approve",
        "Quant": "Approve",
        "Compliance": "Approve",
    })
    assert res["committee_vote"]["approve"] == 6
    assert res["overall_recommendation"] == "APPROVE"

    # 1 reject
    res2 = engine.compile_consensus({
        "CIO": "Approve",
        "CRO": "Reject",
        "PM": "Approve",
        "Trading": "Approve",
        "Quant": "Approve",
        "Compliance": "Approve",
    })
    assert res2["committee_vote"]["reject"] == 1
    assert res2["overall_recommendation"] == "REJECT"

    # 3 conditionals
    res3 = engine.compile_consensus({
        "CIO": "Approve",
        "CRO": "Conditional Approve",
        "PM": "Approve",
        "Trading": "Conditional Approve",
        "Quant": "Needs Review",
        "Compliance": "Approve",
    })
    assert res3["committee_vote"]["conditional"] == 3
    assert res3["overall_recommendation"] == "NEEDS_REVIEW"


def test_phase158a_fail_closed() -> None:
    # Evaluate with None inputs
    res = InvestmentCommitteeEngine().evaluate_portfolio(None, institutional_optimization=None)
    assert res["status"] == "DATA UNAVAILABLE"
    assert res["overall_recommendation"] == "REJECT"
    assert res["committee_vote"]["reject"] == 6
    assert res["advisory_only"] is True
    assert res["execution_allowed"] is False
    assert res["live_trading_blocked"] is True
    assert res["broker_execution_armed"] is False


def test_phase158a_portfolio_construction_integration() -> None:
    opps = _test_opportunities()
    res = PortfolioConstructionIntelligenceEngine().analyze(
        opps,
        max_positions=3,
        decision_confidence={"confidence": 85.0},
        broker_health={"broker_health": "GREEN"},
    )

    assert res["status"] in {"OK", "PARTIAL"}
    assert "investment_committee_intelligence" in res
    
    committee_res = res["investment_committee_intelligence"]
    assert committee_res["status"] == "OK"
    assert "overall_recommendation" in committee_res
    assert "committee_vote" in committee_res
    assert "member_comments" in committee_res
    
    # Verify safety flags on integration output
    assert committee_res["advisory_only"] is True
    assert committee_res["execution_allowed"] is False
    assert committee_res["live_trading_blocked"] is True
    assert committee_res["broker_execution_armed"] is False

    # Check that previous phase optimizer scenarios are still present
    assert "institutional_portfolio_optimization" in res
    assert res["advisory_only"] is True
    assert res["execution_allowed"] is False
