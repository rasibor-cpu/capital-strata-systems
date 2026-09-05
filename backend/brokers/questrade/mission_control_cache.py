"""Fail-closed in-memory cache for Questrade Mission Control read-only evidence."""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any, Mapping

from backend.runtime.coinbase_live_read_only_balance_promotion import (
    evaluate_canonical_broker_snapshot_freshness,
)


def _snapshot_timestamp(snapshot: Mapping[str, Any]) -> Any:
    """Return the first supported broker acquisition timestamp, if present."""
    for key in ("provider_timestamp", "timestamp", "acquisition_timestamp"):
        value = snapshot.get(key)
        if value not in (None, ""):
            return value
    for key in ("balances", "positions"):
        nested = snapshot.get(key)
        if isinstance(nested, Mapping):
            value = nested.get("acquisition_timestamp")
            if value not in (None, ""):
                return value
    return None


def _evaluate_freshness(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return evaluate_canonical_broker_snapshot_freshness(
        {"timestamp": _snapshot_timestamp(snapshot)}
)


class QuestradeMissionControlCache:
    """Cache read-only broker evidence without creating auth or network capability."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot: dict[str, Any] | None = None

    def publish(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        candidate = deepcopy(dict(snapshot))
        freshness = _evaluate_freshness(candidate)
        if not freshness.get("ok"):
            raise ValueError(f"questrade_snapshot_rejected:{freshness.get('reason')}")
        candidate["execution_allowed"] = False
        candidate["live_trading_blocked"] = True
        candidate["broker_execution_armed"] = False
        candidate["advisory_only"] = True
        with self._lock:
            self._snapshot = candidate
        return deepcopy(candidate)

    def read(self) -> dict[str, Any] | None:
        with self._lock:
            candidate = deepcopy(self._snapshot)
        if not candidate:
            return None
        freshness = _evaluate_freshness(candidate)
        if not freshness.get("ok"):
            return None
        candidate["execution_allowed"] = False
        candidate["live_trading_blocked"] = True
        candidate["broker_execution_armed"] = False
        candidate["advisory_only"] = True
        return candidate

    def clear(self) -> None:
        with self._lock:
            self._snapshot = None
