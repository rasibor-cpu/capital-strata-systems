from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from dashboard.runtime.replay_correlation import correlation_key
from dashboard.runtime.trade_lifecycle_replay_viewer import (
    normalize_trade_lifecycle_replay_record,
)


REPLAY_TIMELINE_BUILDER_VERSION = "css.replay_timeline_builder.v1"


def build_replay_timelines(
    records: Iterable[Mapping[str, Any]],
    *,
    group_by: str = "correlation_id",
) -> dict[str, Any]:
    normalized_records = [
        normalize_trade_lifecycle_replay_record(record) for record in records
    ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for event in normalized_records:
        key = _group_key(event, group_by)
        groups[key].append(event)

    timelines = []
    for key, events in sorted(groups.items()):
        ordered = sorted(
            events,
            key=lambda item: (
                _timestamp_sort_key(str(item.get("timestamp_utc", ""))),
                str(item.get("event_id", "")),
            ),
        )
        timelines.append(
            {
                "timeline_key": key,
                "group_by": group_by,
                "event_count": len(ordered),
                "first_timestamp_utc": str(ordered[0].get("timestamp_utc", "")) if ordered else "",
                "last_timestamp_utc": str(ordered[-1].get("timestamp_utc", "")) if ordered else "",
                "symbols": sorted({str(event.get("symbol", "")) for event in ordered if event.get("symbol")}),
                "asset_classes": sorted(
                    {
                        str(event.get("asset_class", ""))
                        for event in ordered
                        if event.get("asset_class")
                    }
                ),
                "event_types": [str(event.get("event_type", "")) for event in ordered],
                "events": ordered,
            }
        )

    return {
        "payload_version": REPLAY_TIMELINE_BUILDER_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "group_by": group_by,
        "timeline_count": len(timelines),
        "event_count": len(normalized_records),
        "timelines": timelines,
    }


def _group_key(event: Mapping[str, Any], group_by: str) -> str:
    if group_by == "symbol":
        return str(event.get("symbol") or "UNKNOWN")
    if group_by == "cycle":
        return str(event.get("cycle") or "UNKNOWN")
    if group_by == "event_sequence":
        return "|".join(
            [
                str(event.get("correlation_id") or correlation_key(event)),
                str(event.get("event_type") or "UNKNOWN"),
            ]
        )
    return str(event.get("correlation_id") or correlation_key(event))


def _timestamp_sort_key(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except Exception:
        return value


__all__ = [
    "REPLAY_TIMELINE_BUILDER_VERSION",
    "build_replay_timelines",
]
