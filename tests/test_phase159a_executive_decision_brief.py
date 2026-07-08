from __future__ import annotations

import json
from backend.reporting.executive_decision_brief import ExecutiveDecisionBrief
from backend.reporting.executive_summary_formatter import ExecutiveSummaryFormatter
from backend.reporting.executive_recommendations import ExecutiveRecommendations


def _mock_portfolio_construction():
    return {
        "status": "OK",
        "portfolio_quality": 95.4,
        "expected_return": 12.5,
        "expected_drawdown": 4.5,
        "preferred_portfolio": [
            {"symbol": "SPY", "weight": 0.5},
            {"symbol": "TLT", "weight": 0.5},
        ],
        "ranked_opportunities": [
            {"symbol": "SPY", "expected_return": 18.0},
            {"symbol": "EUR_USD", "expected_return": 8.0},
        ],
        "portfolio_resilience": {
            "market_regime": "Risk-On",
        },
        "diversification_optimization": {
            "concentration_score": 35.0,
        }
    }


def _mock_committee():
    return {
        "status": "OK",
        "overall_recommendation": "APPROVE",
        "committee_vote": {
            "approve": 5,
            "conditional": 1,
            "reject": 0,
        },
        "member_comments": [
            "CIO: Portfolio quality meets expectations.",
            "CRO: Drawdown and concentration are within bounds.",
        ]
    }


def test_phase159a_complete_briefing_generation() -> None:
    brief_engine = ExecutiveDecisionBrief()
    
    pc = _mock_portfolio_construction()
    comm = _mock_committee()
    dc = {"confidence": 91.3}
    bh = {
        "health": "GREEN",
        "brokers": {
            "OANDA": {"health": "GREEN"},
            "Coinbase": {"health": "AMBER"},
        }
    }
    rh = {"status": "GREEN"}
    opt = {
        "best_overall": "Balanced",
        "recommended_portfolios": [
            {"name": "Balanced", "quality_score": 95.4, "expected_return": 12.5},
        ]
    }

    brief = brief_engine.generate_brief(
        portfolio_construction=pc,
        committee=comm,
        decision_confidence=dc,
        broker_health=bh,
        runtime_health=rh,
        optimizer=opt,
    )

    assert brief["status"] == "OK"
    assert brief["overall_status"] == "AMBER"  # Amber due to Coinbase AMBER health
    assert brief["market_regime"] == "Risk-On"
    assert brief["decision_confidence"] == 91.3
    assert brief["broker_health"] == "GREEN"
    assert brief["broker_health_details"] == {"OANDA": "GREEN", "COINBASE": "AMBER"}
    assert brief["runtime_health"] == "GREEN"
    assert brief["portfolio_quality"] == 95.4
    assert brief["preferred_portfolio"] == "Balanced"
    assert brief["investment_committee"] == "APPROVE"
    
    # Check safety boundaries
    assert brief["advisory_only"] is True
    assert brief["execution_allowed"] is False
    assert brief["live_trading_blocked"] is True
    assert brief["broker_execution_armed"] is False


def test_phase159a_missing_module_handling_and_fail_closed() -> None:
    brief_engine = ExecutiveDecisionBrief()
    
    # Missing pc and committee
    brief = brief_engine.generate_brief(
        portfolio_construction=None,
        committee=None,
    )

    assert brief["status"] == "DATA UNAVAILABLE"
    assert brief["overall_status"] == "RED"
    assert brief["investment_committee"] == "REJECT"
    assert brief["preferred_portfolio"] == "DATA UNAVAILABLE"
    assert len(brief["top_risks"]) > 0
    
    # Check safety gates in fail-closed state
    assert brief["advisory_only"] is True
    assert brief["execution_allowed"] is False
    assert brief["live_trading_blocked"] is True
    assert brief["broker_execution_armed"] is False


def test_phase159a_json_serialization() -> None:
    brief_engine = ExecutiveDecisionBrief()
    formatter = ExecutiveSummaryFormatter()
    
    brief = brief_engine.generate_brief(
        portfolio_construction=_mock_portfolio_construction(),
        committee=_mock_committee(),
    )

    json_str = formatter.to_json(brief)
    parsed = json.loads(json_str)
    
    assert parsed["status"] == "OK"
    assert parsed["advisory_only"] is True
    assert parsed["execution_status"]["live_trading"] == "BLOCKED"


def test_phase159a_markdown_generation() -> None:
    brief_engine = ExecutiveDecisionBrief()
    formatter = ExecutiveSummaryFormatter()
    
    brief = brief_engine.generate_brief(
        portfolio_construction=_mock_portfolio_construction(),
        committee=_mock_committee(),
    )

    md = formatter.to_markdown(brief)
    
    assert "# CSS Executive Decision Brief" in md
    assert "System Overview" in md
    assert "Advisory Execution Status" in md
    assert "Live Trading" in md


def test_phase159a_console_formatting() -> None:
    brief_engine = ExecutiveDecisionBrief()
    formatter = ExecutiveSummaryFormatter()
    
    brief = brief_engine.generate_brief(
        portfolio_construction=_mock_portfolio_construction(),
        committee=_mock_committee(),
        broker_health={
            "health": "GREEN",
            "brokers": {
                "OANDA": {"health": "GREEN"},
                "Coinbase": {"health": "AMBER"},
            }
        }
    )

    console = formatter.to_console(brief)

    # Validate layout headers
    assert "CSS EXECUTIVE DECISION BRIEF" in console
    assert "Overall Status" in console
    assert "Market Regime" in console
    assert "Decision Confidence" in console
    assert "Broker Health" in console
    assert "OANDA" in console
    assert "GREEN" in console
    assert "Coinbase" in console
    assert "AMBER" in console
    assert "Runtime Health" in console
    assert "Portfolio Quality" in console
    assert "Preferred Portfolio" in console
    assert "Investment Committee" in console
    assert "Committee Vote" in console
    assert "Top Opportunities" in console
    assert "Top Risks" in console
    assert "Recommended Actions" in console
    assert "Execution Status" in console
    assert "Execution Authority" in console
    assert "NOT GRANTED" in console
    assert "Live Trading" in console
    assert "BLOCKED" in console
    assert "Broker Execution" in console
    assert "DISARMED" in console
