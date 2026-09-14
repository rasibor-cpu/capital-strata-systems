from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .caie_learning_log import CAIEMatchedOutcome


@dataclass(frozen=True)
class CAIECalibrationSummary:
    matched_count: int
    mean_expected_value_pct: Decimal
    mean_actual_return_pct: Decimal
    expected_minus_actual_pct: Decimal
    mean_confidence: Decimal
    realized_win_rate: Decimal
    confidence_minus_win_rate: Decimal
    mode: str = "SHADOW_ONLY"


def summarize_calibration(matches: tuple[CAIEMatchedOutcome, ...]) -> CAIECalibrationSummary:
    if not matches:
        zero = Decimal("0")
        return CAIECalibrationSummary(
            matched_count=0,
            mean_expected_value_pct=zero,
            mean_actual_return_pct=zero,
            expected_minus_actual_pct=zero,
            mean_confidence=zero,
            realized_win_rate=zero,
            confidence_minus_win_rate=zero,
        )

    n = Decimal(len(matches))
    mean_expected = sum(
        (item.recommendation.expected_value_pct for item in matches),
        Decimal("0"),
    ) / n
    mean_actual = sum(
        (item.outcome.realized_return_pct for item in matches),
        Decimal("0"),
    ) / n
    mean_confidence = sum(
        (item.recommendation.confidence for item in matches),
        Decimal("0"),
    ) / n
    wins = sum(
        (Decimal("1") if item.outcome.realized_return_pct > 0 else Decimal("0") for item in matches),
        Decimal("0"),
    )
    win_rate = wins / n
    q = Decimal("0.000001")

    return CAIECalibrationSummary(
        matched_count=len(matches),
        mean_expected_value_pct=mean_expected.quantize(q),
        mean_actual_return_pct=mean_actual.quantize(q),
        expected_minus_actual_pct=(mean_expected - mean_actual).quantize(q),
        mean_confidence=mean_confidence.quantize(q),
        realized_win_rate=win_rate.quantize(q),
        confidence_minus_win_rate=(mean_confidence - win_rate).quantize(q),
    )
