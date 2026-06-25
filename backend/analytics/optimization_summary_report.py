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
        summary_payload = self._build_unified_summary(
            package=package,
            backtest=backtest,
            validation=validation,
        )

        return {
            "optimization_summary": {
                "estimated_improvement": package.get("estimated_improvement", 0.0),
                "confidence_score": package.get("confidence_score", 0.0),
                "metadata": dict(package.get("metadata", {})),
                "best_strategy": summary_payload["best_strategy"],
                "optimization_score": summary_payload["optimization_score"],
                "expected_return": summary_payload["expected_return"],
                "expectancy": summary_payload["expectancy"],
                "confidence": summary_payload["confidence"],
                "profit_factor": summary_payload["profit_factor"],
                "sharpe_ratio": summary_payload["sharpe_ratio"],
                "sortino_ratio": summary_payload["sortino_ratio"],
                "max_drawdown": summary_payload["max_drawdown"],
                "portfolio_health": summary_payload["portfolio_health"],
                "learning_confidence": summary_payload["learning_confidence"],
                "capital_efficiency": summary_payload["capital_efficiency"],
                "market_regime": summary_payload["market_regime"],
                "recommended_improvements": summary_payload["recommended_improvements"],
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

    def _build_unified_summary(
        self,
        *,
        package: Mapping[str, Any],
        backtest: Mapping[str, Any],
        validation: Mapping[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(package.get("metadata", {}))
        strategy_recommendations = list(package.get("recommended_strategy_changes", []))
        portfolio_summary = dict(package.get("portfolio_summary", {}))
        performance_summary = dict(backtest.get("performance_summary", {}))
        validation_summary = dict(validation.get("summary", {}))

        best_strategy = str(metadata.get("best_strategy") or self._preferred_strategy(strategy_recommendations) or "UNKNOWN")
        confidence = self._float(package.get("confidence_score", 0.0))
        expectancy = self._float(metadata.get("expectancy", performance_summary.get("expectancy", 0.0)))
        expected_return = self._float(metadata.get("expected_return", package.get("estimated_improvement", 0.0)))
        profit_factor = self._float(metadata.get("profit_factor", performance_summary.get("profit_factor", 0.0)))
        sharpe_ratio = self._float(metadata.get("sharpe_ratio", performance_summary.get("sharpe_ratio", 0.0)))
        sortino_ratio = self._float(metadata.get("sortino_ratio", performance_summary.get("sortino_ratio", 0.0)))
        max_drawdown = abs(self._float(metadata.get("max_drawdown", performance_summary.get("max_drawdown", 0.0))))
        capital_efficiency = self._float(metadata.get("capital_efficiency", portfolio_summary.get("capital_efficiency", 0.0)))
        learning_confidence = self._float(metadata.get("learning_confidence", confidence))
        market_regime = str(metadata.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN"
        portfolio_health = str(portfolio_summary.get("portfolio_health") or "STABLE").strip().upper() or "STABLE"
        optimization_score = self._float(
            metadata.get(
                "optimization_score",
                (confidence * 0.4) + (learning_confidence * 0.2) + (profit_factor * 0.2) + (capital_efficiency * 0.2),
            )
        )
        recommended_improvements = list(package.get("recommended_improvements", []))
        if not recommended_improvements:
            recommended_improvements = [
                row
                for row in strategy_recommendations
                if isinstance(row, Mapping) and str(row.get("recommendation") or "").upper() in {"PROMOTE", "DEMOTE", "DISABLE"}
            ]

        if int(validation_summary.get("REJECT", 0) or 0) > 0:
            portfolio_health = "UNSTABLE"

        return {
            "best_strategy": best_strategy,
            "optimization_score": round(optimization_score, 8),
            "expected_return": round(expected_return, 8),
            "expectancy": round(expectancy, 8),
            "confidence": round(confidence, 8),
            "profit_factor": round(profit_factor, 8),
            "sharpe_ratio": round(sharpe_ratio, 8),
            "sortino_ratio": round(sortino_ratio, 8),
            "max_drawdown": round(max_drawdown, 8),
            "portfolio_health": portfolio_health,
            "learning_confidence": round(learning_confidence, 8),
            "capital_efficiency": round(capital_efficiency, 8),
            "market_regime": market_regime,
            "recommended_improvements": recommended_improvements,
        }

    @staticmethod
    def _preferred_strategy(strategy_recommendations: list[Any]) -> str:
        for row in strategy_recommendations:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("recommendation") or "").upper() in {"PROMOTE", "EXECUTE", "PREFERRED"}:
                strategy_id = str(row.get("strategy_id") or row.get("symbol") or "").strip()
                if strategy_id:
                    return strategy_id
        return ""

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

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
