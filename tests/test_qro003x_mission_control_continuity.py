from datetime import datetime, timezone

from backend.brokers.portfolio_continuity import AuditHistory, PortfolioContinuity, PortfolioSnapshotStore
from backend.brokers.replay_provider import ReplayBrokerProvider, ReplayScenario
from dashboard.runtime.mission_control_state import build_mission_control_state


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def test_mission_control_preserves_reloaded_snapshot_as_non_live(tmp_path):
    manager = PortfolioContinuity(PortfolioSnapshotStore(tmp_path / "snapshot.json"), AuditHistory(tmp_path / "audit.jsonl"))
    snapshot = ReplayBrokerProvider(ReplayScenario.STALE_DATA, now=NOW).snapshot()
    manager.accept(snapshot)
    status, loaded = PortfolioContinuity(PortfolioSnapshotStore(tmp_path / "snapshot.json"), AuditHistory(tmp_path / "audit.jsonl")).reload(now=NOW)
    state = build_mission_control_state({"broker_name": "REPLAY", "status": "AVAILABLE", "timestamp": NOW.isoformat(), "balances": {}, "positions": []}, portfolio_snapshot=loaded)
    assert status == "LAST_KNOWN_GOOD_STALE"
    assert state.portfolio_snapshot_source == "STALE"
    assert state.portfolio_data_freshness == "STALE"
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert state.advisory_only is True


def test_unavailable_state_remains_explicit_and_fail_closed():
    state = build_mission_control_state({"broker_name": "REPLAY", "status": "UNAVAILABLE"})
    assert state.portfolio_snapshot_source == "UNAVAILABLE"
    assert state.data_freshness == "UNAVAILABLE"
    assert state.execution_allowed is False
    assert state.live_trading_blocked is True
    assert state.broker_execution_armed is False
    assert state.advisory_only is True
