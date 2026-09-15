from datetime import datetime, timezone

import pytest

from backend.operations import ExecutiveCommandInput, build_executive_command_snapshot


NOW = datetime(2026, 9, 15, 1, 50, tzinfo=timezone.utc)


def healthy(**overrides):
    values = {
        "observed_at_utc": NOW,
        "runtime_health": "HEALTHY",
        "broker_health": "HEALTHY",
        "data_freshness": "HEALTHY",
        "governance_status": "PASS",
        "security_status": "PASS",
        "reconciliation_status": "PASS",
        "backup_status": "PASS",
        "recovery_status": "PASS",
        "capacity_status": "PASS",
        "open_critical_incidents": 0,
        "open_high_incidents": 0,
    }
    values.update(overrides)
    return ExecutiveCommandInput(**values)


def test_all_green_produces_stable_posture():
    snapshot = build_executive_command_snapshot(healthy())
    assert snapshot.operating_posture == "STABLE"
    assert snapshot.attention_level == "NORMAL"
    assert snapshot.blockers == ()
    assert snapshot.warnings == ()


def test_degraded_runtime_is_visible_without_becoming_execution_authority():
    snapshot = build_executive_command_snapshot(healthy(runtime_health="DEGRADED"))
    assert snapshot.operating_posture == "DEGRADED"
    assert "RUNTIME_HEALTH_DEGRADED" in snapshot.warnings
    assert snapshot.execution_allowed is False
    assert snapshot.broker_execution_armed is False
    assert snapshot.money_movement_authorized is False
    assert snapshot.live_trading_authorized is False


def test_unknown_broker_health_blocks():
    snapshot = build_executive_command_snapshot(healthy(broker_health="UNKNOWN"))
    assert snapshot.operating_posture == "BLOCKED"
    assert "BROKER_HEALTH_UNAVAILABLE" in snapshot.blockers


def test_failed_security_blocks():
    snapshot = build_executive_command_snapshot(healthy(security_status="FAIL"))
    assert snapshot.operating_posture == "BLOCKED"
    assert "SECURITY_STATUS_FAIL" in snapshot.blockers


def test_unknown_reconciliation_blocks():
    snapshot = build_executive_command_snapshot(healthy(reconciliation_status="UNKNOWN"))
    assert "RECONCILIATION_STATUS_UNKNOWN" in snapshot.blockers


def test_backup_warning_degrades():
    snapshot = build_executive_command_snapshot(healthy(backup_status="WARN"))
    assert snapshot.operating_posture == "DEGRADED"
    assert "BACKUP_STATUS_WARN" in snapshot.warnings


def test_open_critical_incident_blocks():
    snapshot = build_executive_command_snapshot(healthy(open_critical_incidents=1))
    assert snapshot.operating_posture == "BLOCKED"
    assert "CRITICAL_INCIDENT_OPEN" in snapshot.blockers


def test_open_high_incident_warns():
    snapshot = build_executive_command_snapshot(healthy(open_high_incidents=2))
    assert snapshot.operating_posture == "DEGRADED"
    assert "HIGH_INCIDENT_OPEN" in snapshot.warnings


def test_naive_timestamp_rejected():
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        build_executive_command_snapshot(
            healthy(observed_at_utc=datetime(2026, 9, 15, 1, 50))
        )


def test_negative_incident_count_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        build_executive_command_snapshot(healthy(open_high_incidents=-1))


def test_unsupported_status_rejected():
    with pytest.raises(ValueError, match="unsupported executive-command status"):
        build_executive_command_snapshot(healthy(capacity_status="MAYBE"))


def test_snapshot_is_read_only_authority_projection():
    snapshot = build_executive_command_snapshot(healthy())
    assert snapshot.execution_allowed is False
    assert snapshot.broker_execution_armed is False
    assert snapshot.money_movement_authorized is False
    assert snapshot.live_trading_authorized is False
    assert not hasattr(snapshot, "place_order")
    assert not hasattr(snapshot, "withdraw")
