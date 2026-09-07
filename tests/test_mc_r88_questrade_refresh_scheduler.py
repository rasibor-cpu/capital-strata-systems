from backend.brokers.questrade.mission_control_refresh_scheduler import (
    QuestradeMissionControlRefreshScheduler,
)


SAFETY = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}


class FakeCoordinator:
    def __init__(self, *, status="DISABLED", attempted=False, provider_available=False):
        self.state = {
            "status": status,
            "attempted": attempted,
            "provider_available": provider_available,
            **SAFETY,
        }
        self.refresh_calls = 0
        self.activate_calls = 0

    def status(self):
        return dict(self.state)

    def refresh(self):
        self.refresh_calls += 1
        return {"status": "READY", "reason": "refreshed", **SAFETY}

    def activate(self, **kwargs):
        self.activate_calls += 1
        raise AssertionError("scheduler must never activate Questrade")


def test_r88_refresh_scheduler_is_idle_before_explicit_activation():
    coordinator = FakeCoordinator(status="DISABLED")
    scheduler = QuestradeMissionControlRefreshScheduler(
        coordinator,
        interval_seconds=60,
    )

    result = scheduler.refresh_once()

    assert result["status"] == "IDLE"
    assert result["reason"] == "QUESTRADE_NOT_READY"
    assert coordinator.refresh_calls == 0
    assert coordinator.activate_calls == 0
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True


def test_r88_refresh_scheduler_reuses_ready_coordinator_only():
    coordinator = FakeCoordinator(
        status="READY",
        attempted=True,
        provider_available=True,
    )
    scheduler = QuestradeMissionControlRefreshScheduler(
        coordinator,
        interval_seconds=60,
    )

    result = scheduler.refresh_once()

    assert result["status"] == "READY"
    assert result["reason"] == "refreshed"
    assert coordinator.refresh_calls == 1
    assert coordinator.activate_calls == 0
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True


def test_r88_scheduler_start_is_idempotent_and_stop_is_clean():
    coordinator = FakeCoordinator(status="DISABLED")
    scheduler = QuestradeMissionControlRefreshScheduler(
        coordinator,
        interval_seconds=60,
    )

    assert scheduler.start() is True
    assert scheduler.start() is False
    assert scheduler.running is True

    scheduler.stop(timeout_seconds=1)

    assert scheduler.running is False
    assert coordinator.refresh_calls == 0
    assert coordinator.activate_calls == 0


def test_r88_transient_failure_state_can_retry_existing_provider_without_activation():
    coordinator = FakeCoordinator(
        status="UNAVAILABLE",
        attempted=True,
        provider_available=True,
    )
    scheduler = QuestradeMissionControlRefreshScheduler(
        coordinator,
        interval_seconds=60,
    )

    result = scheduler.refresh_once()

    assert result["status"] == "READY"
    assert result["reason"] == "refreshed"
    assert coordinator.refresh_calls == 1
    assert coordinator.activate_calls == 0
    assert result["execution_allowed"] is False
    assert result["live_trading_blocked"] is True
    assert result["broker_execution_armed"] is False
    assert result["advisory_only"] is True
