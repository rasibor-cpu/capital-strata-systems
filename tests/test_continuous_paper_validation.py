from __future__ import annotations

from pathlib import Path

from backend.validation.continuous_paper_validation import ContinuousPaperValidation


def test_continuous_paper_validation_green_output() -> None:
    checkpoints = [
        {
            "session_id": "paper-1",
            "timestamp": "2026-06-29T10:00:00Z",
            "cycle_count": 1,
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "recommendation_stability": 92.0,
            "pipeline_latency_ms": 120.0,
            "dashboard_latency_ms": 80.0,
            "memory_usage": 40.0,
            "cpu_usage": 20.0,
        },
        {
            "session_id": "paper-1",
            "timestamp": "2026-06-29T10:10:00Z",
            "cycle_count": 2,
            "runtime_health_status": "GREEN",
            "portfolio_decision_status": "GREEN",
            "recommendation_stability": 88.0,
            "pipeline_latency_ms": 140.0,
            "dashboard_latency_ms": 90.0,
            "memory_usage": 42.0,
            "cpu_usage": 24.0,
        },
    ]

    result = ContinuousPaperValidation().summarize(checkpoints)

    assert result["status"] == "OK"
    assert result["final_validation_status"] == "GREEN"
    assert result["duration"] == 600.0
    assert result["cycle_count"] == 2
    assert result["average_pipeline_latency"] == 130.0
    assert result["peak_pipeline_latency"] == 140.0
    assert result["average_dashboard_latency"] == 85.0
    assert result["memory_usage_summary"] == {"average": 41.0, "peak": 42.0}
    assert result["cpu_usage_summary"] == {"average": 22.0, "peak": 24.0}
    assert result["paper_validation_only"] is True
    assert result["execution_allowed"] is False


def test_continuous_paper_validation_amber_output() -> None:
    result = ContinuousPaperValidation().summarize(
        [
            {
                "session_id": "paper-2",
                "timestamp": "2026-06-29T10:00:00Z",
                "runtime_health_status": "AMBER",
                "portfolio_decision_status": "GREEN",
                "restart_count": 1,
                "alert_count": 1,
                "recommendation_stability": 70.0,
                "pipeline_latency_ms": 1600.0,
            }
        ]
    )

    assert result["final_validation_status"] == "AMBER"
    assert "runtime_health_degraded" in result["reasons"]
    assert "pipeline_latency_degraded" in result["reasons"]


def test_continuous_paper_validation_red_output_and_missing_history() -> None:
    red = ContinuousPaperValidation().summarize(
        [
            {
                "session_id": "paper-3",
                "timestamp": "2026-06-29T10:00:00Z",
                "runtime_health_status": "RED",
                "portfolio_decision_status": "FAIL",
                "error_count": 3,
                "stale_artifact_count": 3,
                "recommendation_stability": 40.0,
                "pipeline_latency_ms": 5200.0,
            }
        ]
    )
    missing = ContinuousPaperValidation().summarize([])

    assert red["status"] == "OK"
    assert red["final_validation_status"] == "RED"
    assert "runtime_health_not_green" in red["reasons"]
    assert "error_count_exceeds_limit" in red["reasons"]
    assert missing["status"] == "DATA UNAVAILABLE"
    assert missing["final_validation_status"] == "RED"
    assert missing["reasons"] == ["no_validation_checkpoints"]


def test_phase135a_validation_code_has_no_execution_hooks() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [
        root / "backend" / "validation" / "continuous_paper_validation.py",
        root / "backend" / "validation" / "session_checkpoint_store.py",
        root / "backend" / "validation" / "validation_readiness_engine.py",
    ]
    forbidden = (
        "submit_" + "order",
        "execute_" + "trade",
        "enable_" + "live_" + "trading",
        "live_" + "order",
    )

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not any(term in text for term in forbidden)
