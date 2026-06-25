from __future__ import annotations

from pathlib import Path

from backend.monitoring.alert_bridge import CanonicalAlertBridge
from backend.monitoring.alert_repository import AlertRepository
from backend.runtime.runtime_recovery_manager import RuntimeRecoveryManager


def test_restart_recovery(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"runtime_restart": 3},
    )

    attempts = {"count": 0}

    def action(attempt: int):
        attempts["count"] += 1
        return attempt >= 2

    result = manager.recover_runtime_restart(action)

    assert result.success is True
    assert result.attempts_used == 2
    assert attempts["count"] == 2


def test_heartbeat_recovery(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"heartbeat": 2},
    )

    result = manager.recover_heartbeat(lambda _: True)

    assert result.success is True
    alerts = repo.load_alerts()
    assert any(item["event_type"] == "HEARTBEAT_RECOVERY" for item in alerts)


def test_session_recovery(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"session": 2},
    )

    result = manager.recover_session(lambda _: {"success": True, "reason": "session restored"})

    assert result.success is True
    alerts = repo.load_alerts()
    assert any(item["event_type"] == "SESSION_RECOVERY" for item in alerts)


def test_retry_exhaustion(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"runtime_restart": 2},
    )

    result = manager.recover_runtime_restart(lambda _: False)

    assert result.success is False
    assert result.exhausted is True
    assert result.attempts_used == 2


def test_recovery_success(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"repository": 1},
    )

    result = manager.recover_repository(lambda _: True)

    assert result.success is True
    assert result.reason == "RECOVERY_SUCCESS"


def test_recovery_failure(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"repository": 1},
    )

    result = manager.recover_repository(lambda _: {"success": False, "reason": "repo unavailable"})

    assert result.success is False
    assert result.exhausted is True
    assert "repo unavailable" in result.reason


def test_canonical_alert_generation(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={
            "supervisor": 1,
            "heartbeat": 1,
            "session": 1,
            "runtime_restart": 1,
        },
    )

    manager.recover_supervisor(lambda _: True)
    manager.recover_heartbeat(lambda _: True)
    manager.recover_session(lambda _: True)
    manager.recover_runtime_restart(lambda _: False)

    event_types = {item["event_type"] for item in repo.load_alerts()}
    assert "SUPERVISOR_RECOVERY" in event_types
    assert "HEARTBEAT_RECOVERY" in event_types
    assert "SESSION_RECOVERY" in event_types
    assert "RECOVERY_SUCCESS" in event_types
    assert "RECOVERY_FAILED" in event_types


def test_fail_closed_behavior(tmp_path: Path) -> None:
    alerts_dir = tmp_path / "alerts"
    alerts_dir.mkdir(parents=True, exist_ok=True)
    (alerts_dir / "bad.json").write_text("{not-json", encoding="utf-8")

    repo = AlertRepository(storage_dir=str(alerts_dir))
    manager = RuntimeRecoveryManager(
        alert_bridge=CanonicalAlertBridge(repo),
        max_retries={"session": 1},
    )

    result = manager.recover_session(lambda _: True)

    assert result.success is False
    assert result.exhausted is True
    assert result.reason.startswith("ALERT_EMISSION_FAILED")
