from __future__ import annotations

from typing import Any, Mapping


class PerformanceReportingEngineError(RuntimeError):
    """Fail-closed exception for performance reporting."""


class PerformanceReportingEngine:
    """Builds deterministic reporting dictionaries for production readiness."""

    def build_reports(
        self,
        *,
        performance_metrics: Mapping[str, Any],
        calibration_report: Mapping[str, Any],
        trade_quality_report: Mapping[str, Any],
        runtime_health_report: Mapping[str, Any],
        recovery_report: Mapping[str, Any],
        profitability_report: Mapping[str, Any],
        learning_report: Mapping[str, Any] | None = None,
        strategy_ranking_report: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_mapping(performance_metrics, "performance_metrics")
        self._validate_mapping(calibration_report, "calibration_report")
        self._validate_mapping(trade_quality_report, "trade_quality_report")
        self._validate_mapping(runtime_health_report, "runtime_health_report")
        self._validate_mapping(recovery_report, "recovery_report")
        self._validate_mapping(profitability_report, "profitability_report")
        self._validate_mapping(learning_report or {}, "learning_report")
        self._validate_mapping(strategy_ranking_report or {}, "strategy_ranking_report")

        certification_report = {
            "status": self._derive_status(performance_metrics, runtime_health_report, recovery_report),
            "metrics_summary": self._metric_summary(performance_metrics),
            "evidence": {
                "calibration_ready": bool(calibration_report.get("audit_trail")),
                "runtime_healthy": bool(runtime_health_report.get("runtime_healthy", False)),
                "recovery_operational": bool(recovery_report.get("operational", False)),
            },
        }

        learning_payload = dict(learning_report or {})
        strategy_ranking_payload = dict(strategy_ranking_report or {})
        learning_report = {
            "learning_status": learning_payload.get("learning_status", "UNKNOWN"),
            "strategy_memory": dict(learning_payload.get("strategy_memory", {})),
            "feedback": dict(learning_payload.get("feedback", {})),
        }
        calibration_report = {
            "calibration_status": calibration_report.get("calibration_status", "UNKNOWN"),
            "updates": dict(calibration_report.get("updates", {})),
            "audit_trail": list(calibration_report.get("audit_trail", [])),
        }
        strategy_ranking_report = {
            "strategy_rankings": list(strategy_ranking_payload.get("strategy_rankings", [])),
            "selected_strategies": list(strategy_ranking_payload.get("selected_strategies", [])),
        }
        trade_quality_report = {
            "trade_quality_summary": dict(trade_quality_report.get("trade_quality_summary", trade_quality_report)),
        }
        runtime_health_report = {
            "runtime_health": dict(runtime_health_report),
        }
        recovery_report = {
            "recovery_summary": dict(recovery_report),
        }
        profitability_report = {
            "profitability_summary": dict(profitability_report),
        }

        return {
            "certification_report": certification_report,
            "learning_report": learning_report,
            "calibration_report": calibration_report,
            "strategy_ranking_report": strategy_ranking_report,
            "trade_quality_report": trade_quality_report,
            "runtime_health_report": runtime_health_report,
            "recovery_report": recovery_report,
            "profitability_report": profitability_report,
        }

    @staticmethod
    def _validate_mapping(payload: Mapping[str, Any], name: str) -> None:
        if not isinstance(payload, Mapping):
            raise PerformanceReportingEngineError(f"{name} must be a mapping")

    @staticmethod
    def _metric_summary(metrics: Mapping[str, Any]) -> dict[str, Any]:
        keys = (
            "win_rate",
            "profit_factor",
            "expectancy",
            "average_r",
            "average_hold_time",
            "max_drawdown",
            "recovery_factor",
        )
        return {key: metrics.get(key, 0.0) for key in keys}

    @staticmethod
    def _derive_status(
        performance_metrics: Mapping[str, Any],
        runtime_health_report: Mapping[str, Any],
        recovery_report: Mapping[str, Any],
    ) -> str:
        if not runtime_health_report.get("runtime_healthy", False):
            return "NO_GO"
        if not recovery_report.get("operational", False):
            return "CONDITIONAL_GO"
        if float(performance_metrics.get("win_rate", 0.0)) >= 0.55 and float(performance_metrics.get("profit_factor", 0.0)) >= 1.2:
            return "GO"
        return "CONDITIONAL_GO"
