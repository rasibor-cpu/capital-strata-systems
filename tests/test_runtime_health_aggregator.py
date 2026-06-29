from __future__ import annotations

from backend.monitoring.runtime_health_aggregator import RuntimeHealthAggregator


def test_runtime_health_aggregator_healthy_runtime() -> None:
    result = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN", "pipeline_latency_ms": 25, "dashboard_latency_ms": 50, "cache_hit_rate": 90},
        session_validation={"session_status": "GREEN", "heartbeat_age": 20, "restart_count": 0, "recovery_count": 0},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
    )

    assert result["status"] == "OK"
    assert result["runtime_health"] == "GREEN"
    assert result["session_status"] == "GREEN"
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_runtime_health_aggregator_degraded_and_red_paths() -> None:
    amber = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "AMBER"},
        session_validation={"session_status": "GREEN"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
    )
    red = RuntimeHealthAggregator().aggregate(
        performance={"overall_status": "GREEN"},
        session_validation={"session_status": "RED"},
        supervisor_status={"status": "RUNNING"},
        portfolio_decision={"overall_status": "GREEN"},
    )

    assert amber["runtime_health"] == "AMBER"
    assert red["runtime_health"] == "RED"


def test_runtime_health_aggregator_fail_closed() -> None:
    result = RuntimeHealthAggregator().aggregate(None, None)

    assert result["status"] == "DATA UNAVAILABLE"
    assert result["runtime_health"] == "RED"
