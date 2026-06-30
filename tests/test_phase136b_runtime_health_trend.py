from datetime import datetime, timedelta, timezone

from backend.monitoring.runtime_health_trend import RuntimeHealthTrend


def test_runtime_health_trend_builds_windows() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    history = [
        {"timestamp": (now - timedelta(minutes=30)).isoformat(), "runtime_health": "AMBER"},
        {"timestamp": (now - timedelta(hours=2)).isoformat(), "runtime_health": "GREEN"},
    ]

    result = RuntimeHealthTrend().evaluate(
        runtime_health={"runtime_health": "GREEN"},
        validation_readiness={"readiness_status": "READY"},
        artifact_freshness={"freshness_status": "GREEN"},
        session_continuity={"session_continuity_status": "ACTIVE"},
        portfolio_decision={"overall_status": "GREEN"},
        portfolio_lifecycle={"portfolio_state": "NO_PORTFOLIO"},
        history=history,
        timestamp=now.isoformat(),
    )

    assert result["trends"]["1h"]["sample_count"] == 2
    assert result["trends"]["6h"]["sample_count"] == 3
    assert result["trends"]["1h"]["statuses"]["runtime_health"] == "AMBER"
