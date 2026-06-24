from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.monitoring.alert_repository import (
    AlertRepository,
    AlertRepositoryError,
    AlertCentreCompatibilityAdapter,
)


def test_persist_and_list_recent_alerts(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path))

    created = repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "RUNTIME_FAILURE",
            "source": "runtime",
            "message": "Engine failed",
            "details": {"component": "engine"},
            "dedupe_key": "runtime:engine:fail",
        }
    )

    assert created["alert_id"]
    assert created["severity"] == "CRITICAL"
    assert created["acknowledged"] is False

    recent = repo.list_recent_alerts(limit=5)
    assert len(recent) == 1
    assert recent[0]["message"] == "Engine failed"


def test_list_critical_alerts_and_acknowledge(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path))

    repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "BROKER_DISCONNECT",
            "source": "broker",
            "message": "Broker disconnected",
            "details": {},
            "dedupe_key": "broker:disconnect",
        }
    )
    repo.persist_alert(
        {
            "severity": "WARNING",
            "event_type": "HEARTBEAT_STALE",
            "source": "runtime",
            "message": "Heartbeat stale",
            "details": {},
            "dedupe_key": "runtime:heartbeat",
        }
    )

    critical = repo.list_critical_alerts(limit=5)
    assert len(critical) == 1
    assert critical[0]["event_type"] == "BROKER_DISCONNECT"

    acked = repo.acknowledge_alert(critical[0]["alert_id"])
    assert acked is True

    refreshed = repo.load_alerts()
    target = next(item for item in refreshed if item["alert_id"] == critical[0]["alert_id"])
    assert target["acknowledged"] is True


def test_deduplication_prevents_duplicate_records(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path))

    first = repo.persist_alert(
        {
            "severity": "WARNING",
            "event_type": "TRADE_REJECTED",
            "source": "gateway",
            "message": "Trade rejected",
            "details": {"symbol": "EUR/USD"},
            "dedupe_key": "trade:reject:1",
        }
    )
    second = repo.persist_alert(
        {
            "severity": "WARNING",
            "event_type": "TRADE_REJECTED",
            "source": "gateway",
            "message": "Trade rejected again",
            "details": {"symbol": "EUR/USD"},
            "dedupe_key": "trade:reject:1",
        }
    )

    assert first["alert_id"] == second["alert_id"]
    assert len(repo.load_alerts()) == 1


def test_corrupt_storage_fails_closed(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "bad.json"
    corrupt_file.write_text("{not-json", encoding="utf-8")

    repo = AlertRepository(storage_dir=str(tmp_path))

    with pytest.raises(AlertRepositoryError):
        repo.load_alerts()


def test_alert_centre_compatibility_adapter(tmp_path: Path) -> None:
    repo = AlertRepository(storage_dir=str(tmp_path))
    repo.persist_alert(
        {
            "severity": "CRITICAL",
            "event_type": "RISK_GATE_BLOCK",
            "source": "risk",
            "message": "Risk gate blocked",
            "details": {"symbol": "XAU/USD"},
            "dedupe_key": "risk:block:1",
        }
    )

    adapter = AlertCentreCompatibilityAdapter(repo)
    payload = adapter.build_payload(limit=5)

    assert len(payload) == 1
    assert payload[0]["severity"] == "CRITICAL"
    assert payload[0]["message"] == "Risk gate blocked"
