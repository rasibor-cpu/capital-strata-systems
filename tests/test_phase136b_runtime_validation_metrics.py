from pathlib import Path

from backend.validation.runtime_validation_metrics import RuntimeValidationMetrics


def test_runtime_validation_metrics_calculates_rates_and_persists(tmp_path: Path) -> None:
    result = RuntimeValidationMetrics(artifacts_dir=tmp_path).calculate(
        runtime_health={"runtime_health": "GREEN"},
        performance={"dashboard_latency_ms": 10, "cache_hit_rate": 80},
        session_validation={"session_duration": 120, "restart_count": 2, "recovery_count": 1},
        validation_events=[
            {"cycle_duration_seconds": 2, "artifact_write_failed": False, "validation_state": "GREEN"},
            {"cycle_duration_seconds": 4, "artifact_write_failed": True, "validation_state": "AMBER"},
        ],
        persist=True,
    )

    assert result["average_cycle_duration"] == 3
    assert result["maximum_cycle_duration"] == 4
    assert result["artifact_write_success_rate"] == 50
    assert result["validation_degradation_events"] == 1
    assert (tmp_path / "runtime_validation_metrics.json").exists()
