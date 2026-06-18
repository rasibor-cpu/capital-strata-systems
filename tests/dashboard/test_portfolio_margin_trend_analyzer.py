import pytest
from unittest.mock import MagicMock
from dashboard.runtime.portfolio_margin_trend_analyzer import PortfolioMarginTrendAnalyzer

class MockHistoryStore:
    def __init__(self, snapshots=None, events=None):
        self._snapshots = snapshots if snapshots is not None else []
        self._events = events if events is not None else []

    def list_snapshots(self, limit=None):
        return self._snapshots

    def list_risk_events(self, limit=None):
        return self._events

@pytest.fixture
def analyzer():
    return PortfolioMarginTrendAnalyzer(MockHistoryStore())

def get_valid_snapshot(overrides=None):
    snap = {
        "portfolio_equity": 100000.0,
        "portfolio_buying_power": 200000.0,
        "portfolio_margin_used": 10000.0,
        "portfolio_margin_available": 90000.0,
        "portfolio_risk_state": "NORMAL",
        "timestamp": "2026-06-17T20:00:00Z"
    }
    if overrides:
        snap.update(overrides)
    return snap

def get_valid_event(overrides=None):
    evt = {
        "risk_state": "WARNING",
        "escalation_level": 1,
        "timestamp": "2026-06-17T20:00:00Z"
    }
    if overrides:
        evt.update(overrides)
    return evt

def test_empty_history(analyzer):
    assert analyzer.calculate_margin_utilization_trend() == "DATA_UNAVAILABLE"
    assert analyzer.calculate_buying_power_trend() == "DATA_UNAVAILABLE"
    assert analyzer.calculate_equity_trend() == "DATA_UNAVAILABLE"
    assert analyzer.calculate_risk_state_trend() == "DATA_UNAVAILABLE"
    assert analyzer.calculate_escalation_frequency() == 0.0
    
    summary = analyzer.generate_early_warning_summary()
    assert summary["warning_level"] == "DATA_UNAVAILABLE"

def test_malformed_history_raises_error():
    store = MockHistoryStore(snapshots=[{"bad": "data"}])
    analyzer = PortfolioMarginTrendAnalyzer(store)
    with pytest.raises(ValueError, match="Malformed snapshot: missing portfolio_equity"):
         analyzer.calculate_margin_utilization_trend()

def test_single_snapshot_is_flat():
    store = MockHistoryStore(snapshots=[get_valid_snapshot()])
    analyzer = PortfolioMarginTrendAnalyzer(store)
    assert analyzer.calculate_margin_utilization_trend() == "FLAT"

def test_margin_utilization_deteriorating():
    s1 = get_valid_snapshot({"portfolio_margin_used": 10000, "portfolio_margin_available": 90000}) # ratio 0.1
    s2 = get_valid_snapshot({"portfolio_margin_used": 20000, "portfolio_margin_available": 80000}) # ratio 0.2
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore([s1, s2]))
    assert analyzer.calculate_margin_utilization_trend() == "DETERIORATING"

def test_buying_power_improving():
    s1 = get_valid_snapshot({"portfolio_buying_power": 10000})
    s2 = get_valid_snapshot({"portfolio_buying_power": 20000})
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore([s1, s2]))
    assert analyzer.calculate_buying_power_trend() == "IMPROVING"

def test_escalation_frequency():
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore(events=[get_valid_event(), get_valid_event()]))
    assert analyzer.calculate_escalation_frequency() == 2.0

def test_warning_level_green():
    s1 = get_valid_snapshot({"portfolio_risk_state": "NORMAL"})
    s2 = get_valid_snapshot({"portfolio_risk_state": "NORMAL"})
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore([s1, s2], []))
    summary = analyzer.generate_early_warning_summary()
    assert summary["warning_level"] == "GREEN"

def test_warning_level_yellow():
    s1 = get_valid_snapshot({"portfolio_risk_state": "NORMAL"})
    s2 = get_valid_snapshot({"portfolio_risk_state": "WARNING", "portfolio_margin_used": 20000, "portfolio_margin_available": 80000})
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore([s1, s2], []))
    summary = analyzer.generate_early_warning_summary()
    assert summary["warning_level"] == "YELLOW"

def test_warning_level_orange():
    s1 = get_valid_snapshot({"portfolio_risk_state": "NORMAL"})
    s2 = get_valid_snapshot({"portfolio_risk_state": "RESTRICTED"})
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore([s1, s2], [get_valid_event(), get_valid_event()]))
    summary = analyzer.generate_early_warning_summary()
    assert summary["warning_level"] == "ORANGE"

def test_warning_level_red():
    s1 = get_valid_snapshot({"portfolio_risk_state": "NORMAL"})
    s2 = get_valid_snapshot({"portfolio_risk_state": "LIQUIDATION_RISK"})
    analyzer = PortfolioMarginTrendAnalyzer(MockHistoryStore([s1, s2], []))
    summary = analyzer.generate_early_warning_summary()
    assert summary["warning_level"] == "RED"
