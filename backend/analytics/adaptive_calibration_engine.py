from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class AdaptiveCalibrationEngineError(RuntimeError):
    """Fail-closed exception for calibration recommendations."""


@dataclass(frozen=True)
class CalibrationRecommendation:
    trade_quality_weights: dict[str, float]
    acceptance_threshold: float
    position_sizing_multiplier: float
    exit_confidence: float
    strategy_weighting: dict[str, float]
    regime_sensitivity: dict[str, float]
    audit_trail: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdaptiveCalibrationEngine:
    """Produces bounded calibration updates without changing execution behavior."""

    _BOUNDS = {
        "trade_quality_weights": (0.0, 1.0),
        "acceptance_threshold": (0.0, 100.0),
        "position_sizing_multiplier": (0.25, 1.5),
        "exit_confidence": (0.0, 1.0),
        "strategy_weighting": (0.0, 1.0),
        "regime_sensitivity": (0.5, 2.0),
    }

    def recommend(
        self,
        performance_metrics: Mapping[str, Any],
        calibration_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(performance_metrics, Mapping):
            raise AdaptiveCalibrationEngineError("performance_metrics must be a mapping")
        if calibration_state is not None and not isinstance(calibration_state, Mapping):
            raise AdaptiveCalibrationEngineError("calibration_state must be a mapping when provided")

        metrics = dict(performance_metrics)
        state = dict(calibration_state or {})
        win_rate = self._fraction(metrics.get("win_rate", 0.0), "win_rate")
        profit_factor = self._non_negative(metrics.get("profit_factor", 0.0), "profit_factor")
        max_drawdown = self._fraction(abs(metrics.get("max_drawdown", 0.0)), "max_drawdown")
        recovery_factor = self._non_negative(metrics.get("recovery_factor", 0.0), "recovery_factor")
        consecutive_losses = int(metrics.get("consecutive_losses", 0) or 0)
        concentration_score = self._fraction(metrics.get("concentration_score", 0.0), "concentration_score")
        strategy_strength = self._fraction(metrics.get("strategy_strength", 0.5), "strategy_strength")
        regime_strength = self._fraction(metrics.get("regime_strength", 0.5), "regime_strength")

        trade_quality_weights = self._bounded_weights(
            base=state.get("trade_quality_weights") or {},
            adjustments={
                "market_regime": 0.12 + (regime_strength * 0.08),
                "strategy_intelligence": 0.14 + (strategy_strength * 0.08),
                "replay_confidence": 0.12 + (win_rate * 0.05),
                "portfolio_concentration": 0.12 - (concentration_score * 0.04),
                "capital_allocation": 0.12,
                "position_sizing": 0.10,
                "adaptive_exit_quality": 0.10 + (recovery_factor * 0.02),
                "risk_reward": 0.18 + (profit_factor * 0.03),
            },
        )

        acceptance_threshold = self._clamp(
            float(state.get("acceptance_threshold", 65.0))
            + (max_drawdown * 20.0)
            + (concentration_score * 10.0)
            - (win_rate * 10.0)
            - (profit_factor * 2.0),
            *self._BOUNDS["acceptance_threshold"],
        )
        position_sizing_multiplier = self._clamp(
            float(state.get("position_sizing_multiplier", 1.0))
            * (1.0 - min(0.35, max_drawdown * 0.5))
            * (1.0 - min(0.20, concentration_score * 0.2))
            * (1.0 + min(0.15, recovery_factor * 0.05)),
            *self._BOUNDS["position_sizing_multiplier"],
        )
        exit_confidence = self._clamp(
            float(state.get("exit_confidence", 0.75))
            + (win_rate * 0.05)
            - (max_drawdown * 0.08)
            + (recovery_factor * 0.03),
            *self._BOUNDS["exit_confidence"],
        )
        strategy_weighting = self._bounded_weights(
            base=state.get("strategy_weighting") or {},
            adjustments={
                "strong_strategy": 0.50 + (win_rate * 0.20) + (profit_factor * 0.10),
                "weak_strategy": 0.50 - (consecutive_losses * 0.05) - (max_drawdown * 0.10),
            },
        )
        regime_sensitivity = self._bounded_weights(
            base=state.get("regime_sensitivity") or {},
            adjustments={
                "TRENDING": 1.0 - (max_drawdown * 0.10),
                "RANGING": 1.0 + (concentration_score * 0.10),
                "BREAKOUT": 1.0 + (strategy_strength * 0.10),
                "REVERSAL": 1.0 + (consecutive_losses * 0.03),
                "HIGH_VOLATILITY": 1.0 + (max_drawdown * 0.15),
                "LOW_VOLATILITY": 1.0 - (win_rate * 0.05),
                "UNKNOWN": 1.0,
            },
        )

        audit_trail = [
            {"field": "win_rate", "value": win_rate, "effect": "decrease_threshold_if_strong"},
            {"field": "profit_factor", "value": profit_factor, "effect": "decrease_threshold_if_strong"},
            {"field": "max_drawdown", "value": max_drawdown, "effect": "increase_threshold_if_weak"},
            {"field": "concentration_score", "value": concentration_score, "effect": "increase_threshold_if_risky"},
            {"field": "recovery_factor", "value": recovery_factor, "effect": "decrease_threshold_if_recovering"},
        ]

        recommendation = CalibrationRecommendation(
            trade_quality_weights=trade_quality_weights,
            acceptance_threshold=acceptance_threshold,
            position_sizing_multiplier=position_sizing_multiplier,
            exit_confidence=exit_confidence,
            strategy_weighting=strategy_weighting,
            regime_sensitivity=regime_sensitivity,
            audit_trail=audit_trail,
        )
        return recommendation.to_dict()

    def _bounded_weights(self, *, base: Mapping[str, Any], adjustments: Mapping[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for key, target in adjustments.items():
            base_value = float(base.get(key, target)) if isinstance(base, Mapping) else float(target)
            normalized[key] = self._clamp(base_value + ((target - base_value) * 0.5), *self._BOUNDS.get(key, (0.0, 1.0)))
        total = sum(normalized.values())
        if total <= 0.0:
            return {key: 0.0 for key in sorted(normalized.keys())}
        return {key: round(value / total, 8) for key, value in sorted(normalized.items())}

    @staticmethod
    def _fraction(value: Any, field_name: str) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise AdaptiveCalibrationEngineError(f"{field_name} must be numeric") from exc
        if numeric < 0.0 or numeric > 1.0:
            raise AdaptiveCalibrationEngineError(f"{field_name} must be between 0 and 1")
        return numeric

    @staticmethod
    def _non_negative(value: Any, field_name: str) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise AdaptiveCalibrationEngineError(f"{field_name} must be numeric") from exc
        if numeric < 0.0:
            raise AdaptiveCalibrationEngineError(f"{field_name} must be non-negative")
        return numeric

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return round(max(minimum, min(maximum, float(value))), 8)
