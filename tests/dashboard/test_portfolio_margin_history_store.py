import os
import pytest
import json
import tempfile
from engine.risk.portfolio_margin_snapshot import PortfolioMarginSnapshot
from engine.risk.margin_state import MarginState
from dashboard.runtime.portfolio_margin_history_store import PortfolioMarginHistoryStore

@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = PortfolioMarginHistoryStore(storage_dir=temp_dir)
        yield store

def test_append_valid_portfolio_margin_snapshot(temp_store):
    """Test 1: append valid PortfolioMarginSnapshot"""
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=200000.0,
        portfolio_margin_used=10000.0,
        portfolio_margin_available=90000.0,
        portfolio_risk_state=MarginState.NORMAL,
        broker_count=2,
        timestamp="2026-06-17T20:00:00Z"
    )
    temp_store.append_snapshot(snapshot)
    snapshots = temp_store.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0]["portfolio_risk_state"] == "NORMAL"
    assert snapshots[0]["timestamp"] == "2026-06-17T20:00:00Z"

def test_reject_none_snapshot(temp_store):
    """Test 2: reject None snapshot"""
    with pytest.raises(ValueError, match="Invalid snapshot"):
        temp_store.append_snapshot(None)

def test_reject_dict_snapshot(temp_store):
    """Test 3: reject dict snapshot"""
    with pytest.raises(ValueError, match="Invalid snapshot"):
        temp_store.append_snapshot({"portfolio_equity": 100})

def test_reject_malformed_snapshot(temp_store):
    """Test 4: reject malformed snapshot (missing timestamp)"""
    snapshot = PortfolioMarginSnapshot(
        portfolio_equity=100000.0,
        portfolio_buying_power=200000.0,
        portfolio_margin_used=10000.0,
        portfolio_margin_available=90000.0,
        portfolio_risk_state=MarginState.NORMAL,
        broker_count=2
    )
    with pytest.raises(ValueError, match="missing timestamp"):
        temp_store.append_snapshot(snapshot)

def test_append_valid_risk_event(temp_store):
    """Test 5: append valid risk event"""
    event = {
        "risk_state": "WARNING",
        "escalation_level": 1,
        "timestamp": "2026-06-17T20:01:00Z"
    }
    temp_store.append_risk_event(event)
    events = temp_store.list_risk_events()
    assert len(events) == 1
    assert events[0]["risk_state"] == "WARNING"
    assert events[0]["escalation_level"] == 1

def test_reject_malformed_risk_event(temp_store):
    """Test 6: reject malformed risk event"""
    event = {
        "risk_state": "WARNING"
    }
    with pytest.raises(ValueError, match="missing escalation_level"):
        temp_store.append_risk_event(event)
        
    with pytest.raises(ValueError, match="Invalid event"):
        temp_store.append_risk_event(None)

def test_latest_snapshot_returns_newest(temp_store):
    """Test 7: latest_snapshot returns newest snapshot"""
    s1 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.NORMAL, 1, "T1")
    s2 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.WARNING, 1, "T2")
    temp_store.append_snapshot(s1)
    temp_store.append_snapshot(s2)
    latest = temp_store.latest_snapshot()
    assert latest["timestamp"] == "T2"
    assert latest["portfolio_risk_state"] == "WARNING"

def test_latest_risk_event_returns_newest(temp_store):
    """Test 8: latest_risk_event returns newest event"""
    e1 = {"risk_state": "NORMAL", "escalation_level": 0, "timestamp": "T1"}
    e2 = {"risk_state": "WARNING", "escalation_level": 1, "timestamp": "T2"}
    temp_store.append_risk_event(e1)
    temp_store.append_risk_event(e2)
    latest = temp_store.latest_risk_event()
    assert latest["timestamp"] == "T2"

def test_list_snapshots_limit_behavior(temp_store):
    """Test 9: list_snapshots limit behavior"""
    s1 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.NORMAL, 1, "T1")
    s2 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.WARNING, 1, "T2")
    s3 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.CRITICAL, 1, "T3")
    temp_store.append_snapshot(s1)
    temp_store.append_snapshot(s2)
    temp_store.append_snapshot(s3)
    
    limited = temp_store.list_snapshots(limit=2)
    assert len(limited) == 2
    assert limited[0]["timestamp"] == "T2"
    assert limited[1]["timestamp"] == "T3"

def test_list_risk_events_limit_behavior(temp_store):
    """Test 10: list_risk_events limit behavior"""
    e1 = {"risk_state": "NORMAL", "escalation_level": 0, "timestamp": "T1"}
    e2 = {"risk_state": "WARNING", "escalation_level": 1, "timestamp": "T2"}
    e3 = {"risk_state": "CRITICAL", "escalation_level": 3, "timestamp": "T3"}
    temp_store.append_risk_event(e1)
    temp_store.append_risk_event(e2)
    temp_store.append_risk_event(e3)
    
    limited = temp_store.list_risk_events(limit=2)
    assert len(limited) == 2
    assert limited[0]["timestamp"] == "T2"
    assert limited[1]["timestamp"] == "T3"

def test_jsonl_file_creation(temp_store):
    """Test 11: JSONL file creation"""
    assert not os.path.exists(temp_store.snapshots_file)
    s1 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.NORMAL, 1, "T1")
    temp_store.append_snapshot(s1)
    assert os.path.exists(temp_store.snapshots_file)

def test_append_only_behavior(temp_store):
    """Test 12: append-only behavior"""
    s1 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.NORMAL, 1, "T1")
    temp_store.append_snapshot(s1)
    with open(temp_store.snapshots_file, "r") as f:
        lines1 = f.readlines()
        
    s2 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.WARNING, 1, "T2")
    temp_store.append_snapshot(s2)
    with open(temp_store.snapshots_file, "r") as f:
        lines2 = f.readlines()
        
    assert len(lines1) == 1
    assert len(lines2) == 2
    assert lines1[0] == lines2[0]  # first line remains unchanged

def test_no_synthetic_values_introduced(temp_store):
    """Test 13: no synthetic values introduced"""
    s1 = PortfolioMarginSnapshot(10, 20, 10, 10, MarginState.NORMAL, 1, "T1")
    temp_store.append_snapshot(s1)
    latest = temp_store.latest_snapshot()
    
    # Should contain exactly the fields extracted without synthetic margin values
    assert latest["portfolio_equity"] == 10
    assert "synthetic" not in str(latest)
    assert "projected" not in str(latest)
