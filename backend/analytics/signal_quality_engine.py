from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


class SignalQualityEngine:
    """
    Safe-mode signal quality analytics engine.

    Read-only scoring/analytics layer.
    No trade filtering or execution decisions occur here.
    """

    def evaluate(
        self,
        signal_strength: float = 0.0,
        regime_alignment: float = 0.0,
        persistence_score: float = 0.0,
        false_positive_rate: float = 0.0,
    ) -> Dict[str, Any]:

        signal_strength = self._clamp(signal_strength)
        regime_alignment = self._clamp(regime_alignment)
        persistence_score = self._clamp(persistence_score)
        false_positive_rate = self._clamp(false_positive_rate)

        confidence = (
            (signal_strength * 0.40)
            + (regime_alignment * 0.30)
            + (persistence_score * 0.20)
            + ((1.0 - false_positive_rate) * 0.10)
        )

        quality_label = self._quality_label(confidence)

        return {
            "timestamp": self._now(),
            "signal_strength": round(signal_strength, 6),
            "regime_alignment": round(regime_alignment, 6),
            "persistence_score": round(persistence_score, 6),
            "false_positive_rate": round(false_positive_rate, 6),
            "confidence_score": round(confidence, 6),
            "quality_label": quality_label,
            "mode": "safe_read_only",
        }

    def _quality_label(self, confidence: float) -> str:
        if confidence >= 0.80:
            return "institutional_grade"
        if confidence >= 0.65:
            return "high_quality"
        if confidence >= 0.50:
            return "moderate_quality"
        if confidence >= 0.35:
            return "weak_quality"
        return "poor_quality"

    def _clamp(self, value: Any) -> float:
        try:
            numeric = float(value)
        except Exception:
            numeric = 0.0
        return max(0.0, min(1.0, numeric))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()