from __future__ import annotations

from typing import Any, Mapping


class MarathonReadinessOptimizerError(RuntimeError):
    """Fail-closed exception for optimization readiness assessment."""


class MarathonReadinessOptimizer:
    """Assess whether optimization recommendations are suitable for a 48h paper marathon."""

    def assess(
        self,
        *,
        optimization_package: Mapping[str, Any] | None,
        backtesting_result: Mapping[str, Any] | None,
        validation_result: Mapping[str, Any] | None,
        health_summary: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        for name, payload in (
            ("optimization_package", optimization_package),
            ("backtesting_result", backtesting_result),
            ("validation_result", validation_result),
            ("health_summary", health_summary or {}),
        ):
            if payload is not None and not isinstance(payload, Mapping):
                raise MarathonReadinessOptimizerError(f"{name} must be a mapping when provided")

        package = dict(optimization_package or {})
        backtest = dict(backtesting_result or {})
        validation = dict(validation_result or {})
        health = dict(health_summary or {})

        estimated_improvement = self._float(package.get("estimated_improvement", 0.0))
        confidence = self._float(package.get("confidence_score", 0.0))
        drawdown_impact = self._float(backtest.get("optimized_drawdown", 0.0)) - self._float(backtest.get("baseline_drawdown", 0.0))
        validation_reject = int(validation.get("summary", {}).get("REJECT", 0) or 0)
        validation_review = int(validation.get("summary", {}).get("REVIEW", 0) or 0)
        health_status = str(health.get("status", "HEALTHY")).upper()

        risk_score = self._clamp01((0.40 * max(0.0, drawdown_impact)) + (0.35 * self._clamp01(validation_reject / 10.0)) + (0.25 * (1.0 if health_status == "CRITICAL" else 0.5 if health_status == "WARNING" else 0.0)))
        readiness_score = self._clamp01((0.45 * self._clamp01((estimated_improvement + 1.0) / 2.0)) + (0.35 * confidence) + (0.20 * (1.0 - risk_score)))

        readiness = "READY" if readiness_score >= 0.70 and validation_reject == 0 else "CONDITIONAL" if readiness_score >= 0.50 else "NOT_READY"

        return {
            "optimization_readiness_score": round(readiness_score, 8),
            "optimization_risk_score": round(risk_score, 8),
            "optimization_confidence": round(confidence, 8),
            "estimated_improvement": round(estimated_improvement, 8),
            "estimated_drawdown_impact": round(drawdown_impact, 8),
            "validation_review_count": validation_review,
            "validation_reject_count": validation_reject,
            "readiness": readiness,
        }

    @staticmethod
    def _float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
