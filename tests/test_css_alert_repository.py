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