from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


STAGES = ("candidate", "approved", "blocked", "queued", "submitted", "filled", "partially_filled", "cancelled", "rejected", "expired")


def build_trade_lifecycle(state: Mapping[str, Any]) -> dict[str, Any]:
    trading = _mapping(state.get("trading"))
    orders = _list(trading.get("orders"))
    fills = _list(trading.get("fills"))
    rejections = _list(trading.get("rejections"))
    candidate_count = len(_list(trading.get("candidate_trades")))
    accepted = _number(trading.get("accepted_decisions"))
    rejected = _number(trading.get("rejected_decisions")) + len(rejections)
    stages = {
        "candidate": candidate_count,
        "approved": accepted,
        "blocked": rejected,
        "queued": _status_count(orders, "queued"),
        "submitted": _status_count(orders, "submitted"),
        "filled": len(fills) + _status_count(orders, "filled"),
        "partially_filled": _status_count(orders, "partially_filled"),
        "cancelled": _status_count(orders, "cancelled"),
        "rejected": rejected,
        "expired": _status_count(orders, "expired"),
    }
    return {
        "status": trading.get("execution_status", DATA_UNAVAILABLE),
        "stages": [{"stage": stage, "count": stages.get(stage, 0), **_metadata(state, f"trade_lifecycle.{stage}")} for stage in STAGES],
        "events": _events(state, orders, fills, rejections),
        "latency": trading.get("latency", DATA_UNAVAILABLE),
        "broker": _mapping(state.get("brokers")).get("active_broker", {}).get("selected_broker", DATA_UNAVAILABLE)
        if isinstance(_mapping(state.get("brokers")).get("active_broker"), Mapping)
        else DATA_UNAVAILABLE,
        "strategy": DATA_UNAVAILABLE,
        "asset": DATA_UNAVAILABLE,
        "reason": trading.get("last_execution_event", DATA_UNAVAILABLE),
        "execution_quality": trading.get("execution_quality", DATA_UNAVAILABLE),
        "read_only": True,
        "orders": [],
        "execution_controls": "DISABLED_READ_ONLY",
        **_metadata(state, "trade_lifecycle"),
    }


def _events(state: Mapping[str, Any], orders: list[Any], fills: list[Any], rejections: list[Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for collection, default_stage in ((orders, "submitted"), (fills, "filled"), (rejections, "rejected")):
        for item in collection:
            if not isinstance(item, Mapping):
                continue
            events.append(
                {
                    "stage": str(item.get("status", default_stage)).lower(),
                    "timestamp": item.get("timestamp", DATA_UNAVAILABLE),
                    "broker": item.get("broker", DATA_UNAVAILABLE),
                    "strategy": item.get("strategy", DATA_UNAVAILABLE),
                    "asset": item.get("asset_class", item.get("symbol", DATA_UNAVAILABLE)),
                    "reason": item.get("reason", DATA_UNAVAILABLE),
                    "execution_quality": item.get("execution_quality", DATA_UNAVAILABLE),
                    **_metadata(state, "trade_lifecycle.event"),
                }
            )
    return events


def _status_count(items: list[Any], status: str) -> int:
    return sum(1 for item in items if isinstance(item, Mapping) and str(item.get("status", "")).lower() == status)


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = ["STAGES", "build_trade_lifecycle"]
