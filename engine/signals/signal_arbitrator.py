"""
Signal Arbitrator
-----------------
Detects conflicts across signals and produces an arbitrated, confidence-weighted view.

Responsibilities:
- Identify contradictory signals of the same type
- Down-weight conflicting inputs
- Hard-block downstream usage when conflict exceeds tolerance

NO strategy or execution logic lives here.
"""

from dataclasses import dataclass
from typing import Dict, Tuple
from math import fabs

from .signal_envelope import Signal, SignalEnvelope


@dataclass
class ArbitrationResult:
    allowed: bool
    aggregated_value: float
    aggregated_confidence: float
    conflict_score: float
    reason: str


class SignalArbitrator:
    """
    Deterministic, conservative arbitration logic.
    """

    # Thresholds are intentionally strict
    HARD_BLOCK_CONFLICT = 0.75     # above this → block
    SOFT_CONFLICT = 0.35           # above this → down-weight

    @staticmethod
    def _pairwise_conflict(a: Signal, b: Signal) -> float:
        """
        Returns conflict score between two signals [0,1]
        """
        direction_conflict = fabs(a.value - b.value) / 2.0  # values assumed [-1,1]
        confidence_factor = 1.0 - min(a.confidence, b.confidence)
        return min(1.0, direction_conflict + confidence_factor)

    @classmethod
    def arbitrate(cls, envelope: SignalEnvelope) -> ArbitrationResult:
        signals = list(envelope.signals.values())

        if not signals:
            return ArbitrationResult(
                allowed=False,
                aggregated_value=0.0,
                aggregated_confidence=0.0,
                conflict_score=1.0,
                reason="no_signals"
            )

        # Compute max pairwise conflict
        max_conflict = 0.0
        for i in range(len(signals)):
            for j in range(i + 1, len(signals)):
                c = cls._pairwise_conflict(signals[i], signals[j])
                max_conflict = max(max_conflict, c)

        # Aggregate using confidence-weighted mean
        total_weight = sum(s.confidence for s in signals)
        if total_weight == 0:
            return ArbitrationResult(
                allowed=False,
                aggregated_value=0.0,
                aggregated_confidence=0.0,
                conflict_score=max_conflict,
                reason="zero_confidence"
            )

        weighted_value = sum(s.value * s.confidence for s in signals) / total_weight
        avg_confidence = total_weight / len(signals)

        if max_conflict >= cls.HARD_BLOCK_CONFLICT:
            return ArbitrationResult(
                allowed=False,
                aggregated_value=weighted_value,
                aggregated_confidence=avg_confidence * 0.25,
                conflict_score=max_conflict,
                reason="hard_conflict"
            )

        if max_conflict >= cls.SOFT_CONFLICT:
            return ArbitrationResult(
                allowed=True,
                aggregated_value=weighted_value,
                aggregated_confidence=avg_confidence * 0.6,
                conflict_score=max_conflict,
                reason="soft_conflict"
            )

        return ArbitrationResult(
            allowed=True,
            aggregated_value=weighted_value,
            aggregated_confidence=avg_confidence,
            conflict_score=max_conflict,
            reason="clean"
        )


# Safety invariant
if __name__ == "__main__":
    raise RuntimeError(
        "signal_arbitrator.py is a library module only and must not be executed directly."
    )
