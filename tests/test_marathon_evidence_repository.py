from __future__ import annotations

from pathlib import Path

import pytest

from backend.validation.marathon_evidence_repository import MarathonEvidenceRepository, MarathonEvidenceRepositoryError


def _snapshot(cycle_number: int, equity: float = 100000.0, drawdown: float = 0.0) -> dict[str, object]:
    return {
        "cycle_number": cycle_number,
        "timestamp": f"2026-06-24T12:00:0{cycle_number}+00:00",
        "runtime_duration_seconds": 60.0,
        "cycle_duration_seconds": 60.0,
        "heartbeat_age_seconds": 5.0,
        "restart_count": 1,
        "recovery_count": 1,
        "alert_count": 1,
        "trade_count": 2,
        "approved_trades": 2,
        "blocked_trades": 0,
        "capital": equity,
        "equity": equity,
        "drawdown": drawdown,
        "decision_latency_seconds": 0.2,
        "runtime_latency_seconds": 0.4,
        "trade_statistics": {"trade_count": 2, "realized_pnl": 12.5},
    }


def test_normal_marathon_evidence(tmp_path: Path) -> None:
    repository = MarathonEvidenceRepository(tmp_path / "marathon_evidence.json")
    repository.create_storage()
    repository.record_event({"event_type": "heartbeat", "timestamp": "2026-06-24T12:00:00+00:00", "payload": {"age_seconds": 5.0}})
    repository.record_snapshot(_snapshot(1))
    repository.record_snapshot(_snapshot(2, equity=100050.0, drawdown=2.0))

    summary = repository.summarize()

    assert summary["cycle_count"] == 2
    assert summary["trade_statistics"]["trade_count"] == 4.0
    assert summary["capital_curve"] == [100000.0, 100050.0]


def test_warning_evidence(tmp_path: Path) -> None:
    repository = MarathonEvidenceRepository(tmp_path / "marathon_evidence.json")
    repository.record_event({"event_type": "alert", "payload": {"severity": "warning"}})
    repository.record_snapshot(_snapshot(1, drawdown=5.0))

    summary = repository.summarize()

    assert summary["counts"]["alert"] == 1
    assert summary["drawdown_history"] == [5.0]


def test_corrupt_evidence_fail_closed(tmp_path: Path) -> None:
    storage = tmp_path / "marathon_evidence.json"
    storage.write_text("{not-json", encoding="utf-8")
    repository = MarathonEvidenceRepository(storage)

    with pytest.raises(MarathonEvidenceRepositoryError):
        repository.load_run()
