from __future__ import annotations

from typing import Any, Mapping

from .portfolio_correlation_engine import PortfolioCorrelationEngine, PortfolioCorrelationEngineError


class ConcentrationGuardError(RuntimeError):
    """Fail-closed exception for concentration guard evaluation."""


class ConcentrationGuard:
    """Recommendation-only concentration guard."""

    def __init__(
        self,
        *,
        concentration_reduce_threshold: float = 0.45,
        concentration_block_threshold: float = 0.65,
        correlation_reduce_threshold: float = 0.40,
        correlation_block_threshold: float = 0.60,
        risk_scale: float = 1.0,
        correlation_groups: Mapping[str, Any] | None = None,
    ) -> None:
        self.concentration_reduce_threshold = self._validate_threshold(concentration_reduce_threshold, "concentration_reduce_threshold")
        self.concentration_block_threshold = self._validate_threshold(concentration_block_threshold, "concentration_block_threshold")
        self.correlation_reduce_threshold = self._validate_threshold(correlation_reduce_threshold, "correlation_reduce_threshold")
        self.correlation_block_threshold = self._validate_threshold(correlation_block_threshold, "correlation_block_threshold")
        self.risk_scale = self._validate_threshold(risk_scale, "risk_scale")
        if self.concentration_reduce_threshold > self.concentration_block_threshold:
            raise ConcentrationGuardError("concentration_reduce_threshold cannot exceed concentration_block_threshold")
        if self.correlation_reduce_threshold > self.correlation_block_threshold:
            raise ConcentrationGuardError("correlation_reduce_threshold cannot exceed correlation_block_threshold")

        self.engine = PortfolioCorrelationEngine(correlation_groups=correlation_groups)

    def evaluate(self, positions: list[dict[str, Any]] | None) -> dict[str, Any]:
        try:
            summary = self.engine.analyze_portfolio(positions)
        except PortfolioCorrelationEngineError as exc:
            raise ConcentrationGuardError(str(exc)) from exc

        concentration_score = float(summary["concentration_score"])
        correlation_score = float(summary["correlation_score"])
        directional_pressure = self._compute_directional_pressure(summary)
        risk_score = min(1.0, (concentration_score * 0.45) + (correlation_score * 0.35) + (directional_pressure * 0.20))
        risk_score = round(max(0.0, risk_score * self.risk_scale), 8)

        if concentration_score >= self.concentration_block_threshold or correlation_score >= self.correlation_block_threshold or risk_score >= 0.80:
            recommendation = "BLOCK"
        elif concentration_score >= self.concentration_reduce_threshold or correlation_score >= self.correlation_reduce_threshold or risk_score >= 0.50:
            recommendation = "REDUCE_SIZE"
        else:
            recommendation = "ALLOW"

        return {
            "risk_score": risk_score,
            "concentration_score": concentration_score,
            "correlation_score": correlation_score,
            "recommendation": recommendation,
            "portfolio_summary": summary,
        }

    def _compute_directional_pressure(self, summary: Mapping[str, Any]) -> float:
        total_exposure = float(summary.get("total_exposure", 0.0) or 0.0)
        if total_exposure <= 0:
            return 0.0

        long_exposure = float(summary.get("long_exposure", 0.0) or 0.0)
        short_exposure = float(summary.get("short_exposure", 0.0) or 0.0)
        imbalance = abs(long_exposure - short_exposure) / total_exposure
        return max(0.0, min(1.0, round(imbalance, 8)))

    @staticmethod
    def _validate_threshold(value: float, field_name: str) -> float:
        try:
            threshold = float(value)
        except (TypeError, ValueError) as exc:
            raise ConcentrationGuardError(f"{field_name} must be numeric") from exc
        if threshold <= 0:
            raise ConcentrationGuardError(f"{field_name} must be positive")
        return threshold
