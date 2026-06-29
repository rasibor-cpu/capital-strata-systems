from __future__ import annotations

from backend.monitoring.runtime_performance_monitor import RuntimePerformanceMonitor


def test_runtime_performance_monitor_healthy_runtime() -> None:
    result = RuntimePerformanceMonitor().evaluate(
        {
            "pipeline_latency_ms": 50,
            "dashboard_latency_ms": 75,
            "api_endpoint_latency_ms": [20, 30],
            "json_persistence_latency_ms": [5],
            "artifact_reads": 4,
            "artifact_writes": 0,
            "cache_hits": 9,
            "cache_misses": 1,
            "execution_times_ms": [50, 75, 20],
            "memory_usage": {"rss_kb": 1000},
            "cpu_usage": {"process_time_seconds": 1.0},
        }
    )

    assert result["status"] == "OK"
    assert result["overall_status"] == "GREEN"
    assert result["cache_hit_rate"] == 90.0
    assert result["artifact_reads"] == 4
    assert result["artifact_writes"] == 0
    assert result["average_execution_time_ms"] > 0
    assert result["peak_execution_time_ms"] == 75
    assert result["advisory_only"] is True
    assert result["execution_allowed"] is False


def test_runtime_performance_monitor_degraded_latency_and_cache() -> None:
    result = RuntimePerformanceMonitor().evaluate(
        {
            "pipeline_latency_ms": 1600,
            "dashboard_latency_ms": 800,
            "cache_hits": 1,
            "cache_misses": 4,
            "execution_times_ms": [1600, 800],
        }
    )

    assert result["overall_status"] == "AMBER"
    assert result["cache_hit_rate"] == 20.0
    assert "Monitor runtime performance" in result["recommendation"]


def test_runtime_performance_monitor_red_and_fail_closed() -> None:
    red = RuntimePerformanceMonitor().evaluate({"pipeline_latency_ms": 6000})
    unavailable = RuntimePerformanceMonitor().evaluate(None)

    assert red["overall_status"] == "RED"
    assert unavailable["status"] == "DATA UNAVAILABLE"
    assert unavailable["overall_status"] == "RED"
