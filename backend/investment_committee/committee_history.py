from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class CommitteeHistoryStore:
    """In-memory advisory history store for committee decision explainability."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        *,
        opportunity_id: str,
        votes: Sequence[Mapping[str, Any]],
        recommendation: str,
        confidence: float,
        consensus: Mapping[str, Any],
        explanations: Sequence[str],
    ) -> dict[str, Any]:
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "opportunity_id": str(opportunity_id),
            "votes": _json_safe(list(votes)),
            "recommendation": str(recommendation),
            "confidence": round(float(confidence), 6),
            "consensus": _json_safe(dict(consensus)),
            "committee_explanations": [str(item) for item in explanations],
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        }
        self._records.append(item)
        return dict(item)

    def records(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._records]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


__all__ = ["CommitteeHistoryStore"]
