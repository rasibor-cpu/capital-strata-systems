from __future__ import annotations

from typing import Any, Mapping


class OptimizationSummaryReportError(RuntimeError):
    """Fail-closed exception for optimization summary reporting."""


class OptimizationSummaryReport:
    """Build deterministic optimization summary reports for review and certification."""

    def build(
        self,
        *,
        optimization_package: Mapping[str, Any],
        backtesting_results: Mapping[str, Any],
        validation_results: Mapping[str, Any],
        readiness_assessment: Mapping[str, Any],
    ) -> dict[str, Any]:
        for name, payload in (
            ("optimization_package", optimization_package),
            ("backtesting_results", backtesting_results),
            ("validation_results", validation_results),
            ("readiness_assessment", readiness_assessment),
        ):
            if not isinstance(payload, Mapping):
                raise OptimizationSummaryReportError(f"{name} must be a mapping")

        package = dict(optimization_package)
        backtest = dict(backtesting_results)
        validation = dict(validation_results)
        readiness = dict(readiness_assessment)

        certification = self._certification_recommendation(backtest, validation, readiness)

        return {
            "optimization_summary": {
                "estimated_improvement": package.get("estimated_improvement", 0.0),
                "confidence_score": package.get("confidence_score", 0.0),
                "metadata": dict(package.get("metadata", {})),
            },
            "threshold_recommendations": package.get("recommended_threshold_changes", {}),
            "position_recommendations": package.get("recommended_sizing_changes", []),
            "strategy_recommendations": package.get("recommended_strategy_changes", []),
            "regime_recommendations": package.get("recommended_regime_changes", {}),
            "backtesting_results": backtest,
            "validation_results": validation,
            "readiness_assessment": readiness,
            "expected_performance_improvement": package.get("estimated_improvement", 0.0),
            "certification_recommendation": certification,
        }

    @staticmethod
    def _certification_recommendation(
        backtest: Mapping[str, Any],
        validation: Mapping[str, Any],
        readiness: Mapping[str, Any],
    ) -> str:
        if str(backtest.get("backtest_decision", "REJECT")).upper() == "REJECT":
            return "NO_GO"
        if int(validation.get("summary", {}).get("REJECT", 0) or 0) > 0:
            return "NO_GO"
        if str(readiness.get("readiness", "NOT_READY")).upper() == "READY":
            return "GO"
        return "CONDITIONAL_GO"
