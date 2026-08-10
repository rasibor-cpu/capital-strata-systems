from __future__ import annotations

from typing import Any, Mapping


class AutonomousSupervisorError(ValueError):
    """Raised when the autonomous supervisor receives invalid input."""


class AutonomousSupervisor:
    """Fail-closed supervisor for autonomous runtime decisions."""

    def evaluate(self, state: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            raise AutonomousSupervisorError("state must be a mapping")

        metrics = state.get("performance_metrics", {})
        if not isinstance(metrics, Mapping):
            raise AutonomousSupervisorError("performance_metrics must be a mapping")

        win_rate = float(metrics.get("win_rate", 0.0))
        max_drawdown = float(metrics.get("max_drawdown", 0.0))
        critical_alerts = int(state.get("critical_alerts", 0))
        recovery_exhausted = bool(state.get("recovery_exhausted", False))
        heartbeat_age_seconds = float(state.get("heartbeat_age_seconds", 0.0))
        weak_strategy = bool(state.get("weak_strategy", False))

        if critical_alerts > 0 or recovery_exhausted or heartbeat_age_seconds > 300:
            return {"action": "STOP_AUTONOMY", "reason": "safety_stop"}

        if max_drawdown >= 0.25:
            return {"action": "STOP_AUTONOMY", "reason": "drawdown_limit"}

        if weak_strategy:
            return {"action": "PAUSE_STRATEGY", "reason": "weak_strategy"}

        if win_rate < 0.5:
            return {"action": "REDUCE_EXPOSURE", "reason": "low_win_rate"}

        return {"action": "CONTINUE", "reason": "nominal"}