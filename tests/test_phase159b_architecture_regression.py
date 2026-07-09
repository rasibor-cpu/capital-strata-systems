from __future__ import annotations

from backend.portfolio.portfolio_construction_intelligence import PortfolioConstructionIntelligenceEngine
from backend.intelligence.investment_committee_engine import InvestmentCommitteeEngine
from backend.reporting.executive_decision_brief import ExecutiveDecisionBrief


def test_phase159b_safety_gate_enforcement_regressions() -> None:
    # 1. Verify Portfolio Construction Engine safety gates
    pc_engine = PortfolioConstructionIntelligenceEngine()
    pc_res = pc_engine.analyze(None)
    
    assert pc_res["advisory_only"] is True
    assert pc_res["execution_allowed"] is False
    assert pc_res["live_trading_blocked"] is True
    assert pc_res["broker_execution_armed"] is False

    # 2. Verify Investment Committee Engine safety gates
    committee_engine = InvestmentCommitteeEngine()
    comm_res = committee_engine.evaluate_portfolio(None, institutional_optimization=None)
    
    assert comm_res["advisory_only"] is True
    assert comm_res["execution_allowed"] is False
    assert comm_res["live_trading_blocked"] is True
    assert comm_res["broker_execution_armed"] is False

    # 3. Verify Executive Decision Brief safety gates
    brief_engine = ExecutiveDecisionBrief()
    brief_res = brief_engine.generate_brief(portfolio_construction=None, committee=None)
    
    assert brief_res["advisory_only"] is True
    assert brief_res["execution_allowed"] is False
    assert brief_res["live_trading_blocked"] is True
    assert brief_res["broker_execution_armed"] is False


def test_phase159b_component_integrity_checks() -> None:
    # Validate imports and class presence
    assert PortfolioConstructionIntelligenceEngine is not None
    assert InvestmentCommitteeEngine is not None
    assert ExecutiveDecisionBrief is not None
