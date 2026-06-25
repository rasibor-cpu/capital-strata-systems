from __future__ import annotations

from typing import Any, Mapping


class MarathonRuntimeStatisticsError(RuntimeError):
    """Fail-closed exception for runtime statistics computation."""


class MarathonRuntimeStatistics:
    def compute(self, evidence_summary: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(evidence_summary, Mapping):
            raise MarathonRuntimeStatisticsError("evidence_summary must be a mapping")

        cycle_count = int(evidence_summary.get("cycle_count", 0) or 0)
        runtime_duration_seconds = self._float(evidence_summary.get("runtime_duration_seconds", 0.0))
        active_runtime_seconds = self._float(evidence_summary.get("active_runtime_seconds", runtime_duration_seconds))
        average_cycle_duration = self._float(
            evidence_summary.get(
                "average_cycle_duration_seconds",
                (runtime_duration_seconds / cycle_count) if cycle_count else 0.0,
            )
        )
        recovery_count = int(evidence_summary.get("recovery_count", len(list(evidence_summary.get("recovery_events", [])))) or 0)
        alert_count = int(evidence_summary.get("alert_count", len(list(evidence_summary.get("alerts", [])))) or 0)
        restart_count = int(evidence_summary.get("restart_count", len(list(evidence_summary.get("restart_events", [])))) or 0)
        trade_count = int(evidence_summary.get("trade_count", evidence_summary.get("trade_statistics", {}).get("trade_count", 0)) or 0)
        runtime_latency_seconds = self._average(evidence_summary.get("runtime_latency_history", []), evidence_summary.get("runtime_latency_seconds", 0.0))
        decision_latency_seconds = self._average(evidence_summary.get("decision_latency_history", []), evidence_summary.get("decision_latency_seconds", 0.0))

        uptime_pct = active_runtime_seconds / runtime_duration_seconds if runtime_duration_seconds > 0.0 else 0.0
        recovery_rate = recovery_count / cycle_count if cycle_count else 0.0
        alert_rate = alert_count / cycle_count if cycle_count else 0.0
        trade_frequency = trade_count / runtime_duration_seconds if runtime_duration_seconds > 0.0 else 0.0

        return {
            "cycle_count": cycle_count,
            "runtime_duration_seconds": round(runtime_duration_seconds, 8),
            "uptime_pct": round(uptime_pct, 8),
            "average_cycle_duration_seconds": round(average_cycle_duration, 8),
            "recovery_rate": round(recovery_rate, 8),
            "alert_rate": round(alert_rate, 8),
            "restart_count": restart_count,
            "trade_frequency": round(trade_frequency, 8),
            "average_runtime_latency_seconds": round(runtime_latency_seconds, 8),
            "average_decision_latency_seconds": round(decision_latency_seconds, 8),
            "trade_count": trade_count,
            "recovery_count": recovery_count,
            "alert_count": alert_count,
        }

    @staticmethod
    def _average(values: Any, fallback: Any) -> float:
        if isinstance(values, list) and values:
            try:
                return sum(float(value) for value in values) / len(values)
            except (TypeError, ValueError):
                return 0.0
        return MarathonRuntimeStatistics._float(fallback)

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
