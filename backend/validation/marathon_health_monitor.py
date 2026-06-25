from __future__ import annotations

from typing import Any, Mapping


class MarathonHealthMonitorError(RuntimeError):
    """Fail-closed exception for marathon health monitoring."""


class MarathonHealthMonitor:
    def __init__(
        self,
        *,
        heartbeat_warning_seconds: float = 120.0,
        heartbeat_critical_seconds: float = 300.0,
        recovery_warning_rate: float = 0.20,
        recovery_critical_rate: float = 0.35,
        alert_warning_rate: float = 0.25,
        alert_critical_rate: float = 0.40,
        memory_warning_growth: float = 0.20,
        memory_critical_growth: float = 0.35,
        consecutive_failure_warning: int = 1,
        consecutive_failure_critical: int = 3,
        runtime_stability_warning: float = 0.75,
        runtime_stability_critical: float = 0.55,
    ) -> None:
        self.heartbeat_warning_seconds = float(heartbeat_warning_seconds)
        self.heartbeat_critical_seconds = float(heartbeat_critical_seconds)
        self.recovery_warning_rate = float(recovery_warning_rate)
        self.recovery_critical_rate = float(recovery_critical_rate)
        self.alert_warning_rate = float(alert_warning_rate)
        self.alert_critical_rate = float(alert_critical_rate)
        self.memory_warning_growth = float(memory_warning_growth)
        self.memory_critical_growth = float(memory_critical_growth)
        self.consecutive_failure_warning = int(consecutive_failure_warning)
        self.consecutive_failure_critical = int(consecutive_failure_critical)
        self.runtime_stability_warning = float(runtime_stability_warning)
        self.runtime_stability_critical = float(runtime_stability_critical)

    def evaluate(self, evidence_summary: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(evidence_summary, Mapping):
            raise MarathonHealthMonitorError("evidence_summary must be a mapping")

        cycle_count = int(evidence_summary.get("cycle_count", 0) or 0)
        heartbeat_history = list(evidence_summary.get("heartbeat_history", []))
        recovery_events = list(evidence_summary.get("recovery_events", []))
        alert_events = list(evidence_summary.get("alerts", []))
        restart_events = list(evidence_summary.get("restart_events", []))
        memory_growth = self._float(evidence_summary.get("memory_growth_metric", evidence_summary.get("memory_growth_rate", 0.0)))
        runtime_stability = self._float(evidence_summary.get("runtime_stability_metric", evidence_summary.get("runtime_stability_score", 1.0)))
        consecutive_failures = int(evidence_summary.get("consecutive_failures", 0) or 0)
        last_heartbeat_age = self._last_heartbeat_age(evidence_summary, heartbeat_history)

        recovery_rate = len(recovery_events) / cycle_count if cycle_count else float(len(recovery_events))
        alert_rate = len(alert_events) / cycle_count if cycle_count else float(len(alert_events))
        restart_rate = len(restart_events) / cycle_count if cycle_count else float(len(restart_events))

        reasons: list[str] = []
        status = "HEALTHY"

        if last_heartbeat_age >= self.heartbeat_critical_seconds:
            status = "CRITICAL"
            reasons.append("heartbeat_stale")
        elif last_heartbeat_age >= self.heartbeat_warning_seconds:
            status = "WARNING"
            reasons.append("heartbeat_age_warning")

        if recovery_rate >= self.recovery_critical_rate:
            status = "CRITICAL"
            reasons.append("recovery_frequency_critical")
        elif recovery_rate >= self.recovery_warning_rate and status == "HEALTHY":
            status = "WARNING"
            reasons.append("recovery_frequency_warning")

        if alert_rate >= self.alert_critical_rate:
            status = "CRITICAL"
            reasons.append("alert_frequency_critical")
        elif alert_rate >= self.alert_warning_rate and status == "HEALTHY":
            status = "WARNING"
            reasons.append("alert_frequency_warning")

        if runtime_stability <= self.runtime_stability_critical:
            status = "CRITICAL"
            reasons.append("runtime_stability_critical")
        elif runtime_stability <= self.runtime_stability_warning and status == "HEALTHY":
            status = "WARNING"
            reasons.append("runtime_stability_warning")

        if memory_growth >= self.memory_critical_growth:
            status = "CRITICAL"
            reasons.append("memory_growth_critical")
        elif memory_growth >= self.memory_warning_growth and status == "HEALTHY":
            status = "WARNING"
            reasons.append("memory_growth_warning")

        if consecutive_failures >= self.consecutive_failure_critical:
            status = "CRITICAL"
            reasons.append("consecutive_failures_critical")
        elif consecutive_failures >= self.consecutive_failure_warning and status == "HEALTHY":
            status = "WARNING"
            reasons.append("consecutive_failures_warning")

        return {
            "status": status,
            "reasons": tuple(sorted(set(reasons))),
            "metrics": {
                "heartbeat_age_seconds": round(last_heartbeat_age, 8),
                "recovery_rate": round(recovery_rate, 8),
                "alert_rate": round(alert_rate, 8),
                "restart_rate": round(restart_rate, 8),
                "memory_growth_metric": round(memory_growth, 8),
                "runtime_stability_metric": round(runtime_stability, 8),
                "consecutive_failures": consecutive_failures,
            },
        }

    @staticmethod
    def _last_heartbeat_age(evidence_summary: Mapping[str, Any], heartbeat_history: list[Any]) -> float:
        for key in ("last_heartbeat_age_seconds", "heartbeat_age_seconds"):
            if key in evidence_summary:
                return MarathonHealthMonitor._float(evidence_summary.get(key))
        if heartbeat_history:
            last_item = heartbeat_history[-1]
            if isinstance(last_item, Mapping):
                for key in ("age_seconds", "elapsed_seconds", "heartbeat_age_seconds"):
                    if key in last_item:
                        return MarathonHealthMonitor._float(last_item.get(key))
        return 0.0

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
