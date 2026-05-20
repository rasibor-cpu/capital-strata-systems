from __future__ import annotations

from typing import Any


def calculate_event_confidence(
    source_reliability: Any,
    confirming_sources: int = 1,
    market_confirmation: bool = False,
    contradiction: bool = False,
    rumor: bool = False,
) -> float:
    try:
        confidence = float(source_reliability)
    except (TypeError, ValueError):
        confidence = 0.0

    try:
        confirmations = int(confirming_sources)
    except (TypeError, ValueError):
        confirmations = 1

    if confirmations > 1:
        confidence += min(20.0, (confirmations - 1) * 5.0)

    if market_confirmation:
        confidence += 10.0

    if contradiction:
        confidence -= 20.0

    if rumor:
        confidence -= 25.0

    if confidence < 0.0:
        confidence = 0.0
    elif confidence > 100.0:
        confidence = 100.0

    return confidence