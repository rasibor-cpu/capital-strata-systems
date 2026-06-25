from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping


class SessionAwarenessEngine:
    """Session-aware confidence adjustment for intelligence scoring."""

    def analyze(self, *, now: datetime | None = None, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        ts = now or datetime.now(UTC)
        weekday = ts.weekday()
        hour = ts.hour

        if weekday >= 5:
            return {
                "session": "WEEKEND",
                "overlap": False,
                "holiday_or_weekend": True,
                "confidence_adjustment": 0.75,
                "characteristics": "weekend_liquidity",
            }

        if 21 <= hour or hour < 6:
            session = "SYDNEY"
        elif hour < 9:
            session = "TOKYO"
        elif hour < 16:
            session = "LONDON"
        else:
            session = "NEW_YORK"

        overlap = (7 <= hour < 9) or (12 <= hour < 16)
        confidence_adjustment = 1.08 if overlap else (0.96 if session in {"SYDNEY", "TOKYO"} else 1.0)

        if metadata and bool(metadata.get("holiday", False)):
            confidence_adjustment *= 0.92

        return {
            "session": session,
            "overlap": overlap,
            "holiday_or_weekend": bool(metadata.get("holiday", False)) if metadata else False,
            "confidence_adjustment": round(max(0.7, min(1.2, confidence_adjustment)), 8),
            "characteristics": "overlap_high_activity" if overlap else "standard",
        }
