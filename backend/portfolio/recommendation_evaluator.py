from __future__ import annotations

from typing import Any, Iterable, Mapping

from backend.portfolio.confidence_calibration_engine import ConfidenceCalibrationEngine
from backend.portfolio.utils import advisory_response, clamp, safe_float


class RecommendationEvaluatorError(RuntimeError):
    """Fail-closed exception for recommendation evaluation analytics."""


class RecommendationEvaluator:
    """Evaluate historical advisory recommendations against later outcomes."""

    DEFENSIVE = {"PAUSE_NEW_TRADES", "REDUCE_RISK", "DECREASE_RISK", "HEDGE", "AVOID"}
    AGGRESSIVE = {"INCREASE_RISK", "ALLOCATE", "ROTATE_IN", "BUY", "EXPAND"}
    NEUTRAL = {"MAINTAIN", "REBALANCE", "HOLD"}

    def evaluate(self, history: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        rows = self._evaluable_rows(history)
        if not rows:
            return advisory_response(
                "DATA UNAVAILABLE",
                overall_accuracy=None,
                recommendation_precision=None,
                recommendation_recall=None,
                confidence_calibration=None,
                avoided_loss=0.0,
                missed_opportunity=0.0,
                recommendation_effectiveness=None,
                accuracy_by_policy={},
                accuracy_by_regime={},
                accuracy_by_asset={},
                accuracy_by_strategy={},
                accuracy_by_recommendation_type={},
                recommendation="Insufficient evaluated recommendation history.",
            )

        hit_count = sum(1 for row in rows if row["hit"])
        accuracy = hit_count / len(rows)
        precision, recall = self._precision_recall(rows)
        avoided_loss = sum(row["avoided_loss"] for row in rows)
        missed_opportunity = sum(row["missed_opportunity"] for row in rows)
        calibration = ConfidenceCalibrationEngine().analyze(rows)
        calibration_score = calibration.get("calibration_score")
        effectiveness = self._effectiveness_score(accuracy, avoided_loss, missed_opportunity, calibration_score)

        return advisory_response(
            "OK",
            overall_accuracy=round(accuracy * 100.0, 6),
            recommendation_precision=precision,
            recommendation_recall=recall,
            confidence_calibration=calibration_score,
            avoided_loss=round(avoided_loss, 6),
            missed_opportunity=round(missed_opportunity, 6),
            recommendation_effectiveness=effectiveness,
            accuracy_by_policy=self._breakdown(rows, "policy_profile"),
            accuracy_by_regime=self._breakdown(rows, "market_regime"),
            accuracy_by_asset=self._breakdown(rows, "asset_class"),
            accuracy_by_strategy=self._breakdown(rows, "strategy"),
            accuracy_by_recommendation_type=self._breakdown(rows, "recommendation_type"),
            evaluated_recommendations=len(rows),
            recommendation=self._recommendation_text(accuracy, calibration_score, missed_opportunity),
        )

    @classmethod
    def _evaluable_rows(cls, history: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        if history is None or isinstance(history, (str, bytes)):
            return []
        try:
            iterator = iter(history)
        except TypeError:
            return []

        rows: list[dict[str, Any]] = []
        for item in iterator:
            if not isinstance(item, Mapping):
                continue
            recommendation = cls._recommendation(item)
            if not recommendation:
                continue
            if not cls._has_outcome(item):
                continue
            outcome_return = cls._outcome_return(item)
            drawdown = abs(cls._outcome_drawdown(item))
            hit = cls._hit(recommendation, outcome_return, drawdown)
            rows.append(
                {
                    "recommendation": recommendation,
                    "recommendation_type": cls._recommendation_type(item, recommendation),
                    "policy_profile": cls._dimension(item, "policy_profile", "POLICY_UNSPECIFIED"),
                    "market_regime": cls._dimension(item, "market_regime", "REGIME_UNSPECIFIED"),
                    "asset_class": cls._dimension(item, "asset_class", "ASSET_UNSPECIFIED"),
                    "strategy": cls._dimension(item, "strategy", "STRATEGY_UNSPECIFIED"),
                    "confidence": cls._confidence(item),
                    "actual_positive": outcome_return > 0.0,
                    "predicted_positive": recommendation in cls.AGGRESSIVE,
                    "hit": hit,
                    "performance": outcome_return,
                    "avoided_loss": max(0.0, -outcome_return) if recommendation in cls.DEFENSIVE else 0.0,
                    "missed_opportunity": max(0.0, outcome_return)
                    if recommendation in cls.DEFENSIVE and outcome_return > 0.0
                    else 0.0,
                }
            )
        return rows

    @staticmethod
    def _recommendation(row: Mapping[str, Any]) -> str:
        value = row.get(
            "recommendation",
            row.get("portfolio_recommendation", row.get("adaptive_recommendation", row.get("action", ""))),
        )
        return str(value or "").strip().upper()

    @staticmethod
    def _has_outcome(row: Mapping[str, Any]) -> bool:
        outcome = row.get("outcome")
        source = outcome if isinstance(outcome, Mapping) else row
        return any(
            key in source
            for key in (
                "realized_return",
                "forward_return",
                "portfolio_return",
                "return",
                "realized_pnl",
                "pnl",
                "max_drawdown",
                "drawdown",
            )
        )

    @staticmethod
    def _recommendation_type(row: Mapping[str, Any], recommendation: str) -> str:
        value = row.get("recommendation_type", row.get("type"))
        if value:
            return str(value).strip().upper()
        if recommendation in RecommendationEvaluator.DEFENSIVE:
            return "DEFENSIVE"
        if recommendation in RecommendationEvaluator.AGGRESSIVE:
            return "AGGRESSIVE"
        return "NEUTRAL"

    @staticmethod
    def _dimension(row: Mapping[str, Any], key: str, fallback: str) -> str:
        value = row.get(key)
        if value is None and isinstance(row.get("context"), Mapping):
            value = row["context"].get(key)
        return str(value or fallback).strip().upper()

    @staticmethod
    def _outcome_return(row: Mapping[str, Any]) -> float:
        outcome = row.get("outcome")
        source = outcome if isinstance(outcome, Mapping) else row
        value = source.get(
            "realized_return",
            source.get("forward_return", source.get("portfolio_return", source.get("return", None))),
        )
        if value is not None:
            return safe_float(value)
        pnl = safe_float(source.get("realized_pnl", source.get("pnl", 0.0)))
        capital = abs(safe_float(source.get("capital", source.get("notional", 10000.0)), 10000.0))
        return pnl / capital if capital > 0 else 0.0

    @staticmethod
    def _outcome_drawdown(row: Mapping[str, Any]) -> float:
        outcome = row.get("outcome")
        source = outcome if isinstance(outcome, Mapping) else row
        return safe_float(source.get("max_drawdown", source.get("drawdown", 0.0)))

    @staticmethod
    def _confidence(row: Mapping[str, Any]) -> float:
        value = row.get("confidence", row.get("decision_confidence", row.get("recommendation_confidence", 0.5)))
        numeric = safe_float(value, 0.5)
        if numeric > 1.0:
            numeric /= 100.0
        return clamp(numeric, 0.0, 1.0, default=0.5)

    @classmethod
    def _hit(cls, recommendation: str, outcome_return: float, drawdown: float) -> bool:
        if recommendation in cls.DEFENSIVE:
            return outcome_return <= 0.0 or drawdown >= 0.05
        if recommendation in cls.AGGRESSIVE:
            return outcome_return > 0.0 and drawdown < 0.1
        if recommendation in cls.NEUTRAL:
            return outcome_return >= -0.01 and drawdown < 0.1
        return False

    @staticmethod
    def _precision_recall(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
        true_positive = sum(1 for row in rows if row["predicted_positive"] and row["actual_positive"])
        false_positive = sum(1 for row in rows if row["predicted_positive"] and not row["actual_positive"])
        false_negative = sum(1 for row in rows if not row["predicted_positive"] and row["actual_positive"])
        precision = None if true_positive + false_positive == 0 else round(true_positive / (true_positive + false_positive) * 100.0, 6)
        recall = None if true_positive + false_negative == 0 else round(true_positive / (true_positive + false_negative) * 100.0, 6)
        return precision, recall

    @staticmethod
    def _breakdown(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(str(row[key]), []).append(row)
        return {
            name: {
                "accuracy": round(sum(1 for row in items if row["hit"]) / len(items) * 100.0, 6),
                "count": len(items),
            }
            for name, items in sorted(groups.items())
        }

    @staticmethod
    def _effectiveness_score(
        accuracy: float,
        avoided_loss: float,
        missed_opportunity: float,
        calibration_score: Any,
    ) -> float:
        calibration_component = safe_float(calibration_score, accuracy * 100.0) / 100.0
        raw = (accuracy * 70.0) + (calibration_component * 20.0)
        raw += min(10.0, avoided_loss * 100.0)
        raw -= min(25.0, missed_opportunity * 100.0)
        return round(max(0.0, min(100.0, raw)), 6)

    @staticmethod
    def _recommendation_text(accuracy: float, calibration_score: Any, missed_opportunity: float) -> str:
        calibration = safe_float(calibration_score, 0.0)
        if accuracy < 0.5:
            return "Review recommendation thresholds before relying on advisory conclusions."
        if calibration < 70.0:
            return "Recommendation direction is usable, but confidence calibration needs review."
        if missed_opportunity > 0.05:
            return "Evaluate overly defensive recommendations that missed positive outcomes."
        return "Recommendation evidence is acceptable for advisory monitoring."
