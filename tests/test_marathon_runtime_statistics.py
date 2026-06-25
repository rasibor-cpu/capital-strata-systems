from __future__ import annotations

from backend.validation.marathon_runtime_statistics import MarathonRuntimeStatistics


def test_runtime_statistics() -> None:
    statistics = MarathonRuntimeStatistics().compute({
        "cycle_count": 4,
        "runtime_duration_seconds": 400.0,
        "active_runtime_seconds": 380.0,
        "recovery_events": [{}, {}],
        "alerts": [{}],
        "restart_events": [{}],
        "trade_count": 8,
        "runtime_latency_history": [0.4, 0.6],
        "decision_latency_history": [0.1, 0.3],
    })

    assert statistics["uptime_pct"] == 0.95
    assert statistics["average_cycle_duration_seconds"] == 100.0
    assert statistics["recovery_rate"] == 0.5
    assert statistics["alert_rate"] == 0.25
    assert statistics["restart_count"] == 1
    assert statistics["trade_frequency"] == 0.02
