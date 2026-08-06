import pytest
from unittest.mock import MagicMock
import tempfile
import time
import os

from backend.runtime.css_runtime_supervisor import CSSRuntimeSupervisor
from backend.governance.css_unified_trade_gate import CSSUnifiedTradeGate
from backend.events.event_bus import EventBus
from backend.events.event_models import Event


class MockEventBus:
    def __init__(self, should_fail=False):
        self.published_events = []
        self.should_fail = should_fail

    def publish(self, event: Event) -> int:
        if self.should_fail:
            raise Exception("Event Bus publish failed")
        self.published_events.append(event)
        return 1


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


def test_supervisor_publishing(temp_dir):
    event_bus = MockEventBus()
    supervisor = CSSRuntimeSupervisor(
        state_dir=temp_dir,
        trusted_root=temp_dir,
        max_restart_limit=2,
        event_bus=event_bus
    )

    # 1. RUNTIME_STARTED
    supervisor.start()
    assert len(event_bus.published_events) == 1
    assert event_bus.published_events[0].event_type == "RUNTIME_STARTED"

    # 2. RUNTIME_STOPPED
    supervisor.stop()
    assert len(event_bus.published_events) == 2
    assert event_bus.published_events[1].event_type == "RUNTIME_STOPPED"

    # 3. HEARTBEAT_LOST
    supervisor.start()
    # Backdate last heartbeat to be stale
    supervisor.last_heartbeat_at = "2026-06-28T00:00:00+00:00"
    supervisor.check_stale_heartbeat(stale_threshold_seconds=10)
    assert any(e.event_type == "HEARTBEAT_LOST" for e in event_bus.published_events)

    # 4. RECOVERY_STARTED
    supervisor.record_restart_attempt("test_service", 1, 5.0)
    assert any(e.event_type == "RECOVERY_STARTED" for e in event_bus.published_events)

    # 5. RECOVERY_COMPLETE
    supervisor.record_restart_success("test_service", 1)
    assert any(e.event_type == "RECOVERY_COMPLETE" for e in event_bus.published_events)


def test_supervisor_publishing_failure_isolation(temp_dir):
    event_bus = MockEventBus(should_fail=True)
    supervisor = CSSRuntimeSupervisor(
        state_dir=temp_dir,
        trusted_root=temp_dir,
        max_restart_limit=2,
        event_bus=event_bus
    )

    # Calling lifecycle operations should not raise exceptions
    supervisor.start()
    assert supervisor.status == "RUNNING"
    supervisor.record_restart_attempt("test_service", 1, 5.0)
    supervisor.record_restart_success("test_service", 1)
    supervisor.stop()
    assert supervisor.status == "STOPPED"


def test_unified_trade_gate_publishing():
    event_bus = MockEventBus()
    gate = CSSUnifiedTradeGate(event_bus=event_bus)

    candidate = {
        "asset_class": "crypto",
        "expected_value": 100.0,
        "cost": 10.0,
        "probability": 0.8,
    }
    session = {
        "role": "TRADER",
        "created": time.time(),
    }
    portfolio = {
        "crypto": 0,
    }

    # 1. TRADE_APPROVED
    decision = gate.approve_trade(
        candidate=candidate,
        session=session,
        portfolio_state=portfolio,
        engine_mode="CONSERVATIVE"
    )
    assert decision.approved is True
    assert len(event_bus.published_events) == 1
    assert event_bus.published_events[0].event_type == "TRADE_APPROVED"

    # 2. TRADE_REJECTED (probability below threshold)
    low_prob_candidate = dict(candidate, probability=0.1)
    decision_rejected = gate.approve_trade(
        candidate=low_prob_candidate,
        session=session,
        portfolio_state=portfolio,
        engine_mode="CONSERVATIVE"
    )
    assert decision_rejected.approved is False
    assert len(event_bus.published_events) == 2
    assert event_bus.published_events[1].event_type == "TRADE_REJECTED"


def test_unified_trade_gate_failure_isolation():
    event_bus = MockEventBus(should_fail=True)
    gate = CSSUnifiedTradeGate(event_bus=event_bus)

    candidate = {
        "asset_class": "crypto",
        "expected_value": 100.0,
        "cost": 10.0,
        "probability": 0.8,
    }
    session = {
        "role": "TRADER",
        "created": time.time(),
    }
    portfolio = {
        "crypto": 0,
    }

    # Verify that decision executes successfully and is not blocked by EventBus crash
    decision = gate.approve_trade(
        candidate=candidate,
        session=session,
        portfolio_state=portfolio,
        engine_mode="CONSERVATIVE"
    )
    assert decision.approved is True
