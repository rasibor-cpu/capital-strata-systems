from __future__ import annotations

from backend.validation.marathon_health_monitor import MarathonHealthMonitor


def test_health_healthy_warning_critical() -> None:
    monitor = MarathonHealthMonitor()

    healthy = monitor.evaluate({"heartbeat_history": [{"age_seconds": 5}], "cycle_count": 10, "recovery_events": [], "alerts": [], "runtime_stability_metric": 0.95, "memory_growth_metric": 0.05, "consecutive_failures": 0})
    warning = monitor.evaluate({"heartbeat_history": [{"age_seconds": 150}], "cycle_count": 10, "recovery_events": [{}, {}], "alerts": [{}], "runtime_stability_metric": 0.8, "memory_growth_metric": 0.22, "consecutive_failures": 1})
    critical = monitor.evaluate({"heartbeat_history": [{"age_seconds": 400}], "cycle_count": 10, "recovery_events": [{}, {}, {}, {}], "alerts": [{}, {}, {}, {}], "runtime_stability_metric": 0.4, "memory_growth_metric": 0.5, "consecutive_failures": 4})

    assert healthy["status"] == "HEALTHY"
    assert warning["status"] == "WARNING"
    assert critical["status"] == "CRITICAL"
