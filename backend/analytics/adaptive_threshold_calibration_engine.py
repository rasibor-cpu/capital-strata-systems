from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping


class AdaptiveThresholdCalibrationEngineError(RuntimeError):
    """Fail-closed exception for threshold calibration recommendations."""


class AdaptiveThresholdCalibrationEngine:
    """Recommend confidence/entry/rejection/exit thresholds without mutating production settings."""

    def recommend(
        self,
        evidence: list[Mapping[str, Any]] | None,
        *,
        current_thresholds: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if evidence is not None and not isinstance(evidence, list):
            raise AdaptiveThresholdCalibrationEngineError("evidence must be a list when provided")
        if current_thresholds is not None and not isinstance(current_thresholds, Mapping):
            raise AdaptiveThresholdCalibrationEngineError("current_thresholds must be a mapping when provided")

        rows = [self._normalize_trade(row) for row in (evidence or [])]
        if not rows:
            return {
                "strategy_thresholds": [],
                "asset_class_thresholds": [],
                "market_regime_thresholds": [],
                "metadata": {"trade_count": 0, "deterministic": True},
            }

        current = dict(current_thresholds or {})
        strategy_thresholds = self._group_recommendations(rows, "strategy_id", current)
        asset_thresholds = self._group_recommendations(rows, "asset_class", current)
        regime_thresholds = self._group_recommendations(rows, "market_regime", current)

        return {
            "strategy_thresholds": strategy_thresholds,
            "asset_class_thresholds": asset_thresholds,
            "market_regime_thresholds": regime_thresholds,
            "metadata": {"trade_count": len(rows), "deterministic": True},
        }

    def _group_recommendations(
        self,
        rows: list[dict[str, Any]],
        field_name: str,
        current_thresholds: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row[field_name])].append(row)

        output: list[dict[str, Any]] = []
        for key in sorted(grouped.keys()):
            bucket = grouped[key]
            trade_count = len(bucket)
            wins = sum(1 for row in bucket if row["pnl"] > 0.0)
            win_rate = wins / trade_count if trade_count else 0.0
            confidence_avg = sum(row["confidence"] for row in bucket) / trade_count if trade_count else 0.0
            quality_avg = sum(row["quality_score"] for row in bucket) / trade_count if trade_count else 0.0
            drawdown_proxy = abs(min(0.0, min(row["pnl"] for row in bucket)))

            confidence_threshold = self._clamp01(0.45 + (0.30 * win_rate) + (0.20 * confidence_avg) - (0.10 * self._clamp01(drawdown_proxy / 10.0)))
            entry_threshold = self._clamp01(0.40 + (0.35 * win_rate) + (0.25 * self._clamp01(quality_avg / 100.0)))
            rejection_threshold = self._clamp01(1.0 - entry_threshold)
            exit_threshold = self._clamp01(0.50 + (0.20 * confidence_avg) + (0.20 * self._clamp01(quality_avg / 100.0)) - (0.10 * self._clamp01(drawdown_proxy / 10.0)))

            current_bucket = current_thresholds.get(field_name, {}) if isinstance(current_thresholds.get(field_name, {}), Mapping) else {}
            if isinstance(current_bucket, Mapping) and key in current_bucket and isinstance(current_bucket[key], Mapping):
                existing = current_bucket[key]
                confidence_threshold = self._blend(confidence_threshold, existing.get("confidence_threshold"))
                entry_threshold = self._blend(entry_threshold, existing.get("entry_threshold"))
                rejection_threshold = self._blend(rejection_threshold, existing.get("rejection_threshold"))
                exit_threshold = self._blend(exit_threshold, existing.get("exit_threshold"))

            output.append(
                {
                    field_name: key,
                    "trade_count": trade_count,
                    "confidence_threshold": round(confidence_threshold, 8),
                    "entry_threshold": round(entry_threshold, 8),
                    "rejection_threshold": round(rejection_threshold, 8),
                    "exit_threshold": round(exit_threshold, 8),
                }
            )
        return output

    @staticmethod
    def _normalize_trade(payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise AdaptiveThresholdCalibrationEngineError("each evidence trade must be a mapping")
        return {
            "strategy_id": str(payload.get("strategy_id") or payload.get("strategy") or "UNKNOWN").strip() or "UNKNOWN",
            "asset_class": str(payload.get("asset_class") or "UNKNOWN").strip().upper() or "UNKNOWN",
            "market_regime": str(payload.get("market_regime") or "UNKNOWN").strip().upper() or "UNKNOWN",
            "confidence": AdaptiveThresholdCalibrationEngine._to_float(payload.get("confidence", payload.get("decision_confidence", 0.0))),
            "quality_score": AdaptiveThresholdCalibrationEngine._to_float(payload.get("quality_score", 0.0)),
            "pnl": AdaptiveThresholdCalibrationEngine._to_float(payload.get("realized_pnl", payload.get("pnl", 0.0))),
        }

    @staticmethod
    def _blend(recommended: float, existing: Any) -> float:
        try:
            existing_value = float(existing)
        except (TypeError, ValueError):
            return recommended
        return AdaptiveThresholdCalibrationEngine._clamp01((recommended * 0.7) + (existing_value * 0.3))

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
