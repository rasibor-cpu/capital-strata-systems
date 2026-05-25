from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


class SignalQualityEngine:
    """Read-only signal quality analytics with no trade filtering."""

    def build(self, signals: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        normalized = [self._normalize_signal(s) for s in (signals or [])]
        total = len(normalized)
        false_positives = sum(1 for s in normalized if s["is_false_positive"])
        true_positives = total - false_positives

        avg_score = (sum(s["score"] for s in normalized) / total) if total else 0.0
        avg_confidence = (sum(s["confidence"] for s in normalized) / total) if total else 0.0
        avg_regime_alignment = (
            sum(s["regime_alignment"] for s in normalized) / total
        ) if total else 0.0
        avg_persistence = (sum(s["persistence"] for s in normalized) / total) if total else 0.0

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "deterministic": True,
            "signal_count": total,
            "signal_score": avg_score,
            "false_positive_count": false_positives,
            "false_positive_rate": (false_positives / total) if total else 0.0,
            "true_positive_rate": (true_positives / total) if total else 0.0,
            "regime_alignment_score": avg_regime_alignment,
            "signal_persistence_score": avg_persistence,
            "confidence_analytics": {
                "average_confidence": avg_confidence,
                "min_confidence": min((s["confidence"] for s in normalized), default=0.0),
                "max_confidence": max((s["confidence"] for s in normalized), default=0.0),
            },
        }

    @staticmethod
    def _normalize_signal(signal: Mapping[str, Any]) -> dict[str, float | bool]:
        return {
            "score": float(signal.get("score", 0.0)),
            "confidence": float(signal.get("confidence", 0.0)),
            "regime_alignment": float(signal.get("regime_alignment", 0.0)),
            "persistence": float(signal.get("persistence", 0.0)),
            "is_false_positive": bool(signal.get("is_false_positive", False)),
        }
