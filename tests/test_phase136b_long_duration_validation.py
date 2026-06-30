from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.validation.long_duration_validation import LongDurationValidation


def test_long_duration_validation_summarizes_windows_and_persists(tmp_path: Path) -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    events = [
        {"timestamp": (now - timedelta(hours=1)).isoformat(), "uptime_seconds": 60, "validation_state": "GREEN", "runtime_health": "GREEN"},
        {"timestamp": (now - timedelta(hours=7)).isoformat(), "uptime_seconds": 120, "validation_state": "AMBER", "runtime_health": "AMBER"},
    ]

    result = LongDurationValidation(artifacts_dir=tmp_path).summarize(
        events=events,
        paper_performance={"closed_trades_count": 0},
        timestamp=now.isoformat(),
        persist=True,
    )

    assert result["windows"]["6h"]["sample_count"] == 1
    assert result["windows"]["12h"]["sample_count"] == 2
    assert result["windows"]["12h"]["validation_degradations"] == 1
    assert (tmp_path / "long_duration_validation.json").exists()
