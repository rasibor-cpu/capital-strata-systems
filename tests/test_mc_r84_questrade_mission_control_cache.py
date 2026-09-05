from datetime import datetime, timedelta, timezone

import pytest

from backend.brokers.questrade.mission_control_cache import QuestradeMissionControlCache


def _snapshot(*, age_seconds: float = 0.0) -> dict:
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        "status": "AVAILABLE",
        "selected_broker": "QUESTRADE",
        "canonical_mode": "LIVE_READ_ONLY",
        "acquisition_timestamp": ts.isoformat(),
        "balances": {"acquisition_timestamp": ts.isoformat(), "combinedBalances": []},
        "positions": {"acquisition_timestamp": ts.isoformat(), "positions": []},
    }


def test_r84_fresh_snapshot_round_trips():
    cache = QuestradeMissionControlCache()
    published = cache.publish(_snapshot())
    loaded = cache.read()
    assert loaded is not None
    assert loaded["selected_broker"] == "QUESTRADE"
    assert loaded["canonical_mode"] == "LIVE_READ_ONLY"
    assert published is not loaded


def test_r84_publish_rejects_stale_snapshot_fail_closed():
    cache = QuestradeMissionControlCache()
    with pytest.raises(ValueError, match="questrade_snapshot_rejected"):
        cache.publish(_snapshot(age_seconds=301))


def test_r84_read_hides_snapshot_that_becomes_stale():
    cache = QuestradeMissionControlCache()
    cache.publish(_snapshot())
    cache._snapshot = _snapshot(age_seconds=301)
    assert cache.read() is None


def test_r84_safety_flags_are_forced_on_publish_and_read():
    cache = QuestradeMissionControlCache()
    raw = _snapshot()
    raw.update({"execution_allowed": True, "live_trading_blocked": False, "broker_execution_armed": True, "advisory_only": False})
    published = cache.publish(raw)
    loaded = cache.read()
    for state in (published, loaded):
        assert state["execution_allowed"] is False
        assert state["live_trading_blocked"] is True
        assert state["broker_execution_armed"] is False
        assert state["advisory_only"] is True


def test_r84_clear_removes_cached_snapshot():
    cache = QuestradeMissionControlCache()
    cache.publish(_snapshot())
    cache.clear()
    assert cache.read() is None
