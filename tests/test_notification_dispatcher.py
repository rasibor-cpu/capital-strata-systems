from __future__ import annotations

from pathlib import Path

import pytest

from backend.monitoring.alert_repository import AlertRepository
from backend.monitoring.notification_dispatcher import (
    NotificationDispatcher,
    NotificationDispatcherError,
    dispatch_critical_alerts,
)


def _make_alert(
    repository: AlertRepository,
    *,
    severity: str,
    event_type: str,
    dedupe_key: str,
) -> dict[str, str]:
    return repository.persist_alert(
        {
            "severity": severity,
            "event_type": event_type,
            "source": "runtime",
            "message": f"{event_type} happened",
            "details": {"component": "runtime"},
            "dedupe_key": dedupe_key,
        }
    )


def test_critical_alert_dispatches(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))

    _make_alert(
        repo,
        severity="CRITICAL",
        event_type="RUNTIME_FAILURE",
        dedupe_key="dispatch:critical:1",
    )

    dispatched = dispatch_critical_alerts(repo, dispatcher)

    assert len(dispatched) == 2
    channels = {item["channel"] for item in dispatched}
    assert channels == {"FILE_LOG", "CONSOLE_LOG"}


def test_warning_info_do_not_dispatch_by_default(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))

    _make_alert(
        repo,
        severity="WARNING",
        event_type="HEARTBEAT_STALE",
        dedupe_key="dispatch:warning:1",
    )
    _make_alert(
        repo,
        severity="INFO",
        event_type="SUPERVISOR_RECOVERY",
        dedupe_key="dispatch:info:1",
    )

    dispatched = dispatch_critical_alerts(repo, dispatcher)

    assert dispatched == []
    assert dispatcher.load_notifications() == []


def test_acknowledged_alert_does_not_dispatch(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))

    alert = _make_alert(
        repo,
        severity="CRITICAL",
        event_type="BROKER_DISCONNECT",
        dedupe_key="dispatch:ack:1",
    )
    assert repo.acknowledge_alert(alert["alert_id"]) is True

    dispatched = dispatch_critical_alerts(repo, dispatcher)

    assert dispatched == []
    assert dispatcher.load_notifications() == []


def test_dedupe_by_alert_id_and_channel(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))

    _make_alert(
        repo,
        severity="CRITICAL",
        event_type="RUNTIME_FAILURE",
        dedupe_key="dispatch:dedupe:1",
    )

    first = dispatch_critical_alerts(repo, dispatcher)
    second = dispatch_critical_alerts(repo, dispatcher)

    assert len(first) == 2
    assert second == []
    assert len(dispatcher.load_notifications()) == 2


def test_file_log_written(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))

    _make_alert(
        repo,
        severity="CRITICAL",
        event_type="RUNTIME_FAILURE",
        dedupe_key="dispatch:file:1",
    )

    dispatch_critical_alerts(repo, dispatcher, channels=["FILE_LOG"])

    notifications = dispatcher.load_notifications()
    assert len(notifications) == 1
    assert notifications[0]["channel"] == "FILE_LOG"


def test_console_log_channel_accepted(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path / "alerts"))
    dispatcher = NotificationDispatcher(storage_dir=str(tmp_path / "notifications"))

    _make_alert(
        repo,
        severity="CRITICAL",
        event_type="RUNTIME_FAILURE",
        dedupe_key="dispatch:console:1",
    )

    dispatched = dispatch_critical_alerts(repo, dispatcher, channels=["CONSOLE_LOG"])

    assert len(dispatched) == 1
    assert dispatched[0]["channel"] == "CONSOLE_LOG"


def test_corrupt_notification_storage_fail_closed(tmp_path: Path) -> None:
    notifications_dir = tmp_path / "notifications"
    notifications_dir.mkdir(parents=True, exist_ok=True)
    log_path = notifications_dir / "notifications.jsonl"
    log_path.write_text("{bad-json\n", encoding="utf-8")

    dispatcher = NotificationDispatcher(storage_dir=str(notifications_dir))

    with pytest.raises(NotificationDispatcherError):
        dispatcher.load_notifications()
