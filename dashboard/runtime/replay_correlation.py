from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any


REPLAY_CORRELATION_VERSION = "css.replay_correlation.v1"


def create_correlation_id(
    *,
    session_id: Any = "",
    lifecycle_id: Any = "",
    position_id: Any = "",
    symbol: Any = "",
    asset_class: Any = "",
    cycle: Any = "",
    namespace: str = "css-replay",
) -> str:
    """
    Build a stable, replay-safe correlation id from lifecycle identity fields.

    Event type is intentionally excluded so related lifecycle events can group
    into the same timeline.
    """

    seed = "|".join(
        [
            str(namespace or "css-replay"),
            _clean(session_id),
            _clean(lifecycle_id or position_id),
            _clean(symbol).upper(),
            _clean(asset_class).upper(),
            _clean(cycle),
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24].upper()
    return f"COR-{digest}"


def create_lifecycle_id(payload: Mapping[str, Any]) -> str:
    existing = _clean(payload.get("lifecycle_id"))
    if existing:
        return existing

    position_id = _clean(payload.get("position_id"))
    if position_id:
        return f"LFC-{position_id}"

    digest = hashlib.sha256(
        "|".join(
            [
                _clean(payload.get("session_id")),
                _clean(payload.get("symbol")).upper(),
                _clean(payload.get("asset_class")).upper(),
                _clean(payload.get("cycle")),
            ]
        ).encode("utf-8")
    ).hexdigest()[:20].upper()
    return f"LFC-{digest}"


def enrich_with_correlation(payload: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    lifecycle_id = create_lifecycle_id(enriched)
    correlation_id = _clean(enriched.get("correlation_id")) or create_correlation_id(
        session_id=enriched.get("session_id"),
        lifecycle_id=lifecycle_id,
        position_id=enriched.get("position_id"),
        symbol=enriched.get("symbol"),
        asset_class=enriched.get("asset_class"),
        cycle=enriched.get("cycle"),
    )
    enriched["correlation_id"] = correlation_id
    enriched["lifecycle_id"] = lifecycle_id
    return enriched


def correlation_key(payload: Mapping[str, Any]) -> str:
    return _clean(payload.get("correlation_id")) or create_correlation_id(
        session_id=payload.get("session_id"),
        lifecycle_id=payload.get("lifecycle_id"),
        position_id=payload.get("position_id"),
        symbol=payload.get("symbol"),
        asset_class=payload.get("asset_class"),
        cycle=payload.get("cycle"),
    )


def short_correlation_id(value: Any, *, length: int = 12) -> str:
    text = _clean(value)
    if not text:
        return ""
    return text if len(text) <= length else text[:length]


def _clean(value: Any) -> str:
    return str(value or "").strip()


__all__ = [
    "REPLAY_CORRELATION_VERSION",
    "correlation_key",
    "create_correlation_id",
    "create_lifecycle_id",
    "enrich_with_correlation",
    "short_correlation_id",
]
