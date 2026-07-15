from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.mission_control.health import build_health_summary
from dashboard.mission_control.serializers import state_hash


def build_live_mission_control_state(
    dashboard_state: Mapping[str, Any] | None = None,
    *,
    allow_mock: bool = False,
) -> dict[str, Any]:
    from dashboard.mission_control.contracts import build_mission_control_state

    state = build_mission_control_state(dashboard_state, allow_mock=allow_mock)
    freshness = state.get("freshness") if isinstance(state.get("freshness"), Mapping) else {}
    state["health"] = build_health_summary(state, freshness_summary=freshness)
    state["state_hash"] = state_hash(
        {
            key: value
            for key, value in state.items()
            if key not in {"generated_at", "state_hash"}
        }
    )
    return state


def normalize_canonical_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"status": "UNAVAILABLE", "source": "UNAVAILABLE"}
    return dict(payload)


__all__ = [
    "build_live_mission_control_state",
    "normalize_canonical_payload",
]
