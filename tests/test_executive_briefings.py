"""
Tests for CSS Executive Briefings (EWP-4/5A PART E)
"""

import pytest
from backend.intelligence.briefings import BriefingGenerator

def test_briefing_generations():
    # Mock intelligence report payload
    intel_report = {
        "market_regime": "BULLISH",
        "advisory_confidence_score": 0.85,
        "win_loss_statistics": {
            "total_trades": 10,
            "win_rate": 0.6
        },
        "drawdown_trends": {
            "cumulative_pnl": 450.0,
            "max_drawdown": 25.0
        },
        "portfolio_concentration": {
            "highest_exposure_asset": "EQUITIES",
            "risk_concentration_score": 45.0
        },
        "recommendations": [
            {"message": "Diversify equities"}
        ]
    }
    
    # 1. Morning Briefing
    morning = BriefingGenerator.generate_briefing("MORNING", intel_report)
    assert morning["title"] == "Morning Executive Briefing"
    assert "BULLISH" in morning["message"]
    assert "Diversify equities" in morning["message"]
    
    # 2. Evening Briefing
    evening = BriefingGenerator.generate_briefing("EVENING", intel_report)
    assert evening["title"] == "Evening Strategy Summary"
    assert "10 total trades" in evening["message"]
    assert "60.0%" in evening["message"]
    
    # 3. Incident Briefing
    incident = BriefingGenerator.generate_briefing("INCIDENT", intel_report)
    assert incident["title"] == "System Incident Alert"
    assert "heartbeat age" in incident["message"]
    
    # 4. Portfolio Briefing
    portfolio = BriefingGenerator.generate_briefing("PORTFOLIO", intel_report)
    assert portfolio["title"] == "Portfolio Concentration Report"
    assert "EQUITIES" in portfolio["message"]
    assert "45.0%" in portfolio["message"]
    
    # 5. Risk Briefing
    risk = BriefingGenerator.generate_briefing("RISK", intel_report)
    assert risk["title"] == "Risk Advisory Briefing"
    assert "25.00" in risk["message"]
    assert "45.0%" in risk["message"]
