import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.validation.long_duration_validation import LongDurationValidation


def test_phase137a_long_duration_validation_accumulates_history(tmp_path: Path) -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    engine = LongDurationValidation(artifacts_dir=tmp_path)

    first = engine.summarize(
        current_sample={
            "timestamp": (now - timedelta(minutes=5)).isoformat(),
            "runtime_health": "GREEN",
            "validation_confidence": 92,
            "artifact_freshness": "GREEN",
            "recommendation_stability": "STABLE",
            "restart_count": 0,
            "recovery_count": 0,
            "runtime_uptime": 60,
        },
        timestamp=(now - timedelta(minutes=5)).isoformat(),
        persist=True,
    )
    second = engine.summarize(
        current_sample={
            "timestamp": now.isoformat(),
            "runtime_health": "AMBER",
            "validation_confidence": 74,
            "artifact_freshness": "AGING",
            "recommendation_stability": "STABLE",
            "restart_count": 1,
            "recovery_count": 1,
            "runtime_uptime": 120,
            "validation_state": "AMBER",
        },
        timestamp=now.isoformat(),
        persist=True,
    )

    assert first["history_count"] == 1
    assert second["history_count"] == 2
    assert second["windows"]["6h"]["sample_count"] == 2
    assert second["windows"]["6h"]["validation_confidence_history"] == [92, 74]
    history = json.loads((tmp_path / "long_duration_validation_history.json").read_text(encoding="utf-8"))
    assert len(history["history"]) == 2


def test_phase137a_long_duration_validation_prunes_after_seven_days(tmp_path: Path) -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=8)

    result = LongDurationValidation(artifacts_dir=tmp_path).summarize(
        events=[
            {"timestamp": old.isoformat(), "runtime_health": "RED", "runtime_uptime": 1},
            {"timestamp": now.isoformat(), "runtime_health": "GREEN", "runtime_uptime": 1},
        ],
        timestamp=now.isoformat(),
        persist=True,
    )

    assert result["history_count"] == 1
    assert result["windows"]["7d"]["sample_count"] == 1
