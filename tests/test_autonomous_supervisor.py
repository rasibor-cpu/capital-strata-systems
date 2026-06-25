from __future__ import annotations

import pytest

from backend.runtime.autonomous_supervisor import AutonomousSupervisor, AutonomousSupervisorError


def test_supervisor_continue() -> None:
    supervisor = AutonomousSupervisor()
    result = supervisor.evaluate({"performance_metrics": {"win_rate": 0.7, "max_drawdown": 0.05}, "critical_alerts": 0, "recovery_exhausted": False, "heartbeat_age_seconds": 20})

    assert result["action"] == "CONTINUE"


def test_supervisor_reduce_exposure() -> None:
    supervisor = AutonomousSupervisor()
    result = supervisor.evaluate({"performance_metrics": {"win_rate": 0.4, "max_drawdown": 0.05}, "critical_alerts": 0, "recovery_exhausted": False, "heartbeat_age_seconds": 20})

    assert result["action"] == "REDUCE_EXPOSURE"


def test_supervisor_pause_strategy() -> None:
    supervisor = AutonomousSupervisor()
    result = supervisor.evaluate({"performance_metrics": {"win_rate": 0.6, "max_drawdown": 0.05}, "weak_strategy": True, "critical_alerts": 0, "recovery_exhausted": False, "heartbeat_age_seconds": 20})

    assert result["action"] == "PAUSE_STRATEGY"


def test_supervisor_stop_autonomy() -> None:
    supervisor = AutonomousSupervisor()
    result = supervisor.evaluate({"performance_metrics": {"win_rate": 0.7, "max_drawdown": 0.3}, "critical_alerts": 0, "recovery_exhausted": False, "heartbeat_age_seconds": 20})

    assert result["action"] == "STOP_AUTONOMY"


def test_invalid_input_fail_closed() -> None:
    supervisor = AutonomousSupervisor()
    with pytest.raises(AutonomousSupervisorError):
        supervisor.evaluate(None)
