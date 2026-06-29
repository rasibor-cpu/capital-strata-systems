from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class RuntimeHealthAggregatorError(RuntimeError):
    """Fail-closed exception for runtime health aggregation."""


class RuntimeHealthAggregator:
    """Combine operational telemetry into one canonical runtime health package."""

    ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}

    def aggregate(
        self,
        performance: Mapping[str, Any] | None,
        session_validation: Mapping[str, Any] | None,
        supervisor_status: Mapping[str, Any] | None = None,
        portfolio_decision: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(performance, Mapping):
            return self._unavailable("performance_unavailable")
        if not isinstance(session_validation, Mapping):
            return self._unavailable("session_validation_unavailable")

        supervisor = supervisor_status if isinstance(supervisor_status, Mapping) else {}
        decision = portfolio_decision if isinstance(portfolio_decision, Mapping) else {}
        statuses = [
            str(performance.get("overall_status", "RED")).upper(),
            str(session_validation.get("session_status", "RED")).upper(),
            self._supervisor_health(supervisor),
            str(decision.get("overall_status", "RED" if not decision else "GREEN")).upper(),
        ]
        overall = max(statuses, key=lambda item: self.ORDER.get(item, 2))

        recommendation = "Runtime health is acceptable for advisory monitoring."
        if overall == "RED":
            recommendation = "Operational health is red; investigate telemetry before relying on runtime dashboards."
        elif overall == "AMBER":
            recommendation = "Operational health is degraded; continue advisory-only monitoring."

        return {
            "status": "OK",
            "runtime_health": overall,
            "overall_operational_health": overall,
            "performance_status": performance.get("overall_status"),
            "session_status": session_validation.get("session_status"),
            "supervisor_status": supervisor.get("status", "UNKNOWN"),
            "portfolio_decision_status": decision.get("overall_status", "UNKNOWN"),
            "pipeline_latency_ms": performance.get("pipeline_latency_ms"),
            "dashboard_latency_ms": performance.get("dashboard_latency_ms"),
            "cache_hit_rate": performance.get("cache_hit_rate"),
            "heartbeat_age": session_validation.get("heartbeat_age"),
            "restart_count": session_validation.get("restart_count"),
            "recovery_count": session_validation.get("recovery_count"),
            "memory_usage": performance.get("memory_usage"),
            "cpu_usage": performance.get("cpu_usage"),
            "recommendation": recommendation,
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _supervisor_health(supervisor: Mapping[str, Any]) -> str:
        status = str(supervisor.get("status", "UNKNOWN")).upper()
        if status in {"RUNNING", "ONLINE", "HEALTHY", "GREEN"}:
            return "GREEN"
        if status in {"STARTING", "RECOVERING", "DEGRADED", "AMBER"}:
            return "AMBER"
        return "RED"

    @staticmethod
    def _unavailable(reason: str) -> dict[str, Any]:
        return {
            "status": "DATA UNAVAILABLE",
            "runtime_health": "RED",
            "overall_operational_health": "RED",
            "performance_status": "RED",
            "session_status": "RED",
            "supervisor_status": "UNKNOWN",
            "portfolio_decision_status": "UNKNOWN",
            "pipeline_latency_ms": None,
            "dashboard_latency_ms": None,
            "cache_hit_rate": 0.0,
            "heartbeat_age": None,
            "restart_count": 0,
            "recovery_count": 0,
            "memory_usage": None,
            "cpu_usage": None,
            "recommendation": f"Runtime health unavailable: {reason}.",
            "advisory_only": True,
            "execution_allowed": False,
        }
