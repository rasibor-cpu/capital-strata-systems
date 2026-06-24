import json

from backend.monitoring.css_alert_repository import CSSAlertRepository


def test_repository_returns_latest_alerts(tmp_path):
    alert1 = tmp_path / "a.json"
    alert2 = tmp_path / "b.json"

    alert1.write_text(
        json.dumps({"message": "first"}),
        encoding="utf-8",
    )

    alert2.write_text(
        json.dumps({"message": "second"}),
        encoding="utf-8",
    )

    repo = CSSAlertRepository(str(tmp_path))

    alerts = repo.list_alerts(limit=10)

    assert len(alerts) == 2


def test_repository_returns_empty_when_missing_directory(tmp_path):
    repo = CSSAlertRepository(str(tmp_path / "missing"))

    alerts = repo.list_alerts()

    assert alerts == []


def test_get_unread_alerts_filters_acknowledged_alerts(tmp_path):
    (tmp_path / "a.json").write_text(
        json.dumps(
            {
                "alert_id": "A1",
                "message": "unread",
                "acknowledged": False,
            }
        ),
        encoding="utf-8",
    )

    (tmp_path / "b.json").write_text(
        json.dumps(
            {
                "alert_id": "A2",
                "message": "read",
                "acknowledged": True,
            }
        ),
        encoding="utf-8",
    )

    repo = CSSAlertRepository(str(tmp_path))

    unread = repo.get_unread_alerts()

    assert len(unread) == 1
    assert unread[0]["alert_id"] == "A1"


def test_acknowledge_alert_updates_file(tmp_path):
    path = tmp_path / "alert.json"

    path.write_text(
        json.dumps(
            {
                "alert_id": "ALERT-123",
                "message": "test alert",
                "acknowledged": False,
            }
        ),
        encoding="utf-8",
    )

    repo = CSSAlertRepository(str(tmp_path))

    assert repo.acknowledge_alert("ALERT-123") is True

    updated = json.loads(path.read_text(encoding="utf-8"))

    assert updated["acknowledged"] is True


def test_acknowledge_alert_returns_false_when_missing(tmp_path):
    repo = CSSAlertRepository(str(tmp_path))

    assert repo.acknowledge_alert("DOES-NOT-EXIST") is False


def test_purge_old_alerts_keeps_latest_files(tmp_path):
    for i in range(5):
        (tmp_path / f"{i}.json").write_text(
            json.dumps({"alert_id": str(i)}),
            encoding="utf-8",
        )

    repo = CSSAlertRepository(str(tmp_path))

    purged = repo.purge_old_alerts(keep_latest=2)

    assert purged == 3

    remaining = list(tmp_path.glob("*.json"))

    assert len(remaining) == 2