import pytest
from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot
from engine.risk.margin_state import MarginState
from dashboard.runtime.portfolio_margin_risk_monitor import PortfolioMarginRiskMonitor

def test_portfolio_margin_risk_monitor_normal():
    monitor = PortfolioMarginRiskMonitor()
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=200000.0,
        portfolio_margin_used=10000.0,
        portfolio_margin_available=90000.0,
        portfolio_risk_state=MarginState.NORMAL,
        broker_count=2
    )
    result = monitor.evaluate(snapshot)
    
    assert result["risk_state"] == "NORMAL"
    assert result["escalation_level"] == 0
    assert result["escalation_required"] is False
    assert "No escalation required" in result["escalation_message"]
    assert "timestamp" in result

def test_portfolio_margin_risk_monitor_warning():
    monitor = PortfolioMarginRiskMonitor()
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=200000.0,
        portfolio_margin_used=70000.0,
        portfolio_margin_available=30000.0,
        portfolio_risk_state=MarginState.WARNING,
        broker_count=2
    )
    result = monitor.evaluate(snapshot)
    
    assert result["risk_state"] == "WARNING"
    assert result["escalation_level"] == 1
    assert result["escalation_required"] is True
    assert "Level 1" in result["escalation_message"]

def test_portfolio_margin_risk_monitor_restricted():
    monitor = PortfolioMarginRiskMonitor()
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=0.0,
        portfolio_margin_used=85000.0,
        portfolio_margin_available=15000.0,
        portfolio_risk_state=MarginState.RESTRICTED,
        broker_count=2
    )
    result = monitor.evaluate(snapshot)
    
    assert result["risk_state"] == "RESTRICTED"
    assert result["escalation_level"] == 2
    assert result["escalation_required"] is True
    assert "Level 2" in result["escalation_message"]

def test_portfolio_margin_risk_monitor_critical():
    monitor = PortfolioMarginRiskMonitor()
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=0.0,
        portfolio_margin_used=95000.0,
        portfolio_margin_available=5000.0,
        portfolio_risk_state=MarginState.CRITICAL,
        broker_count=2
    )
    result = monitor.evaluate(snapshot)
    
    assert result["risk_state"] == "CRITICAL"
    assert result["escalation_level"] == 3
    assert result["escalation_required"] is True
    assert "Level 3" in result["escalation_message"]

def test_portfolio_margin_risk_monitor_liquidation_risk():
    monitor = PortfolioMarginRiskMonitor()
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=0.0,
        portfolio_margin_used=105000.0,
        portfolio_margin_available=-5000.0,
        portfolio_risk_state=MarginState.LIQUIDATION_RISK,
        broker_count=2
    )
    result = monitor.evaluate(snapshot)
    
    assert result["risk_state"] == "LIQUIDATION_RISK"
    assert result["escalation_level"] == 4
    assert result["escalation_required"] is True
    assert "Level 4" in result["escalation_message"]

def test_portfolio_margin_risk_monitor_invalid_snapshot():
    monitor = PortfolioMarginRiskMonitor()
    with pytest.raises(ValueError):
        monitor.evaluate({"portfolio_risk_state": "NORMAL"})
        
def test_portfolio_margin_risk_monitor_none_snapshot():
    monitor = PortfolioMarginRiskMonitor()
    with pytest.raises(ValueError):
        monitor.evaluate(None)
