from __future__ import annotations

from typing import Any, Mapping


class MarathonSummaryReportError(RuntimeError):
    """Fail-closed exception for marathon summary reporting."""


class MarathonSummaryReport:
    def build_report(
        self,
        *,
        marathon_evidence: Mapping[str, Any],
        health_summary: Mapping[str, Any],
        runtime_statistics: Mapping[str, Any],
        certification_summary: Mapping[str, Any],
        trade_forensics: list[Mapping[str, Any]] | None = None,
        attribution: Mapping[str, Any] | None = None,
        strategy_league_table: list[Mapping[str, Any]] | None = None,
        opportunity_cost: Mapping[str, Any] | None = None,
        improvement_recommendations: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(marathon_evidence, Mapping):
            raise MarathonSummaryReportError("marathon_evidence must be a mapping")
        if not isinstance(health_summary, Mapping):
            raise MarathonSummaryReportError("health_summary must be a mapping")
        if not isinstance(runtime_statistics, Mapping):
            raise MarathonSummaryReportError("runtime_statistics must be a mapping")
        if not isinstance(certification_summary, Mapping):
            raise MarathonSummaryReportError("certification_summary must be a mapping")

        trade_forensics = list(trade_forensics or [])
        strategy_league_table = list(strategy_league_table or [])
        improvement_recommendations = list(improvement_recommendations or [])
        attribution = dict(attribution or {})
        opportunity_cost = dict(opportunity_cost or {})

        runtime_summary = {
            "cycle_count": int(runtime_statistics.get("cycle_count", marathon_evidence.get("cycle_count", 0)) or 0),
            "runtime_duration_seconds": float(runtime_statistics.get("runtime_duration_seconds", marathon_evidence.get("runtime_duration_seconds", 0.0))),
            "uptime_pct": float(runtime_statistics.get("uptime_pct", 0.0)),
            "average_cycle_duration_seconds": float(runtime_statistics.get("average_cycle_duration_seconds", 0.0)),
            "restart_count": int(runtime_statistics.get("restart_count", 0) or 0),
            "trade_frequency": float(runtime_statistics.get("trade_frequency", 0.0)),
            "average_runtime_latency_seconds": float(runtime_statistics.get("average_runtime_latency_seconds", 0.0)),
            "average_decision_latency_seconds": float(runtime_statistics.get("average_decision_latency_seconds", 0.0)),
        }
        trading_summary = {
            "trade_statistics": dict(marathon_evidence.get("trade_statistics", {})),
            "capital_curve": list(marathon_evidence.get("capital_curve", [])),
            "drawdown_history": list(marathon_evidence.get("drawdown_history", [])),
            "strategy_selections": list(marathon_evidence.get("strategy_selections", [])),
            "regime_transitions": list(marathon_evidence.get("regime_transitions", [])),
        }
        performance_summary = {
            "trade_count": int(marathon_evidence.get("cycle_count", 0) or 0),
            "decision_latency_seconds": float(marathon_evidence.get("decision_latency_seconds", 0.0)),
            "runtime_latency_seconds": float(marathon_evidence.get("runtime_latency_seconds", 0.0)),
            "capital_curve": list(marathon_evidence.get("capital_curve", [])),
        }
        recovery_summary = {
            "recovery_events": list(marathon_evidence.get("recovery_events", [])),
            "recovery_rate": float(runtime_statistics.get("recovery_rate", 0.0)),
        }
        alert_summary = {
            "alerts": list(marathon_evidence.get("alerts", [])),
            "alert_rate": float(runtime_statistics.get("alert_rate", 0.0)),
        }

        return {
            "runtime_summary": runtime_summary,
            "health_summary": dict(health_summary),
            "trading_summary": trading_summary,
            "performance_summary": performance_summary,
            "recovery_summary": recovery_summary,
            "alert_summary": alert_summary,
            "certification_summary": dict(certification_summary),
            "recommendations": improvement_recommendations,
            "marathon_evidence": dict(marathon_evidence),
            "trade_forensics": trade_forensics,
            "attribution": attribution,
            "strategy_league_table": strategy_league_table,
            "opportunity_cost": opportunity_cost,
            "unified_operational_report": {
                "runtime_summary": runtime_summary,
                "health_summary": dict(health_summary),
                "trading_summary": trading_summary,
                "performance_summary": performance_summary,
                "recovery_summary": recovery_summary,
                "alert_summary": alert_summary,
                "certification_summary": dict(certification_summary),
                "recommendations": improvement_recommendations,
                "marathon_evidence": dict(marathon_evidence),
                "trade_forensics": trade_forensics,
                "attribution": attribution,
                "strategy_league_table": strategy_league_table,
                "opportunity_cost": opportunity_cost,
            },
        }
