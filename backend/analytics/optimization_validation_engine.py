from __future__ import annotations

from typing import Any, Mapping


class OptimizationValidationEngineError(RuntimeError):
    """Fail-closed exception for optimization validation."""


class OptimizationValidationEngine:
    """Validate recommendation safety as SAFE/REVIEW/REJECT without auto-approval."""

    def validate(
        self,
        optimization_package: Mapping[str, Any] | None,
        backtesting_result: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if optimization_package is not None and not isinstance(optimization_package, Mapping):
            raise OptimizationValidationEngineError("optimization_package must be a mapping when provided")
        if backtesting_result is not None and not isinstance(backtesting_result, Mapping):
            raise OptimizationValidationEngineError("backtesting_result must be a mapping when provided")

        package = dict(optimization_package or {})
        backtest = dict(backtesting_result or {})

        base_conf = self._float(package.get("confidence_score", 0.0))
        expect_delta = self._float(backtest.get("optimized_expectancy", 0.0)) - self._float(backtest.get("baseline_expectancy", 0.0))
        drawdown_delta = self._float(backtest.get("optimized_drawdown", 0.0)) - self._float(backtest.get("baseline_drawdown", 0.0))
        backtest_decision = str(backtest.get("backtest_decision", "REJECT")).upper()

        rows: list[dict[str, Any]] = []
        rows.extend(self._validate_rows("threshold", package.get("recommended_threshold_changes", {}), base_conf, expect_delta, drawdown_delta, backtest_decision))
        rows.extend(self._validate_rows("position", package.get("recommended_sizing_changes", []), base_conf, expect_delta, drawdown_delta, backtest_decision))
        rows.extend(self._validate_rows("strategy", package.get("recommended_strategy_changes", []), base_conf, expect_delta, drawdown_delta, backtest_decision))
        rows.extend(self._validate_rows("regime", package.get("recommended_regime_changes", {}), base_conf, expect_delta, drawdown_delta, backtest_decision))

        summary = {
            "SAFE": sum(1 for row in rows if row["status"] == "SAFE"),
            "REVIEW": sum(1 for row in rows if row["status"] == "REVIEW"),
            "REJECT": sum(1 for row in rows if row["status"] == "REJECT"),
        }

        return {
            "validations": rows,
            "summary": summary,
            "overall": "REVIEW" if summary["REVIEW"] or summary["REJECT"] else "SAFE",
        }

    def _validate_rows(
        self,
        category: str,
        payload: Any,
        base_conf: float,
        expect_delta: float,
        drawdown_delta: float,
        backtest_decision: str,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            iterable = payload
        elif isinstance(payload, Mapping):
            iterable = [{"key": key, "value": value} for key, value in sorted(payload.items())]
        else:
            iterable = []

        for item in iterable:
            if backtest_decision == "REJECT":
                status = "REJECT"
                reason = "backtesting_rejected"
            elif drawdown_delta > 0.0:
                status = "REVIEW"
                reason = "drawdown_increase"
            elif expect_delta < 0.0:
                status = "REJECT"
                reason = "expectancy_decrease"
            elif base_conf >= 0.70:
                status = "SAFE"
                reason = "confidence_and_backtest_support"
            else:
                status = "REVIEW"
                reason = "manual_review_required"

            rows.append({
                "category": category,
                "status": status,
                "reason": reason,
                "recommendation": item,
            })
        return rows

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
