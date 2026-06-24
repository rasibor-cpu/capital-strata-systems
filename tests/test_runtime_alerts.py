from __future__ import annotations

from pathlib import Path

from backend.monitoring.alert_repository import AlertRepository


def test_runtime_alerts_repository_shape(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path))
    alert = repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "LIVE_MODE_BLOCKED",
            "source": "runtime",
            "message": "Live mode blocked",
            "details": {"requested_mode": "live"},
            "dedupe_key": "runtime:live_blocked",
        }
    )

    alerts = repo.list_recent_alerts(limit=10)
    assert alerts[0]["alert_id"] == alert["alert_id"]
    assert alerts[0]["event_type"] == "LIVE_MODE_BLOCKED"
    assert alerts[0]["acknowledged"] is False
