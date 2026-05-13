from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import (
    build_frontend_payload,
    build_websocket_delta,
)
from dashboard.runtime.runtime_event_bus import runtime_event_to_ws_message


DashboardStateProvider = Callable[[], DashboardState]
WS_DELTA_SECTIONS = (
    "pnl_summary",
    "positions",
    "governance",
    "execution",
    "risk",
    "broker",
)
WEBSOCKET_EVENT_TYPES = {
    "dashboard_snapshot",
    "dashboard_delta",
    "dashboard_heartbeat",
    "pnl_update",
    "position_update",
    "governance_alert",
    "execution_alert",
    "broker_status",
    "risk_update",
}


def default_dashboard_state_provider() -> DashboardState:
    return DashboardHydrationCoordinator().hydrate()


def build_initial_ws_message(
    state: DashboardState,
    *,
    sequence: int = 0,
) -> dict[str, Any]:
    payload = build_frontend_payload(state)
    payload["message_type"] = "dashboard_snapshot"
    payload["sequence"] = sequence
    payload["stale_after_ms"] = 15000
    return payload


def build_delta_ws_messages(
    previous_payload: dict[str, Any] | None,
    current_state: DashboardState,
    *,
    sequence: int,
) -> list[dict[str, Any]]:
    current_payload = build_frontend_payload(current_state)
    delta = build_websocket_delta(
        previous_payload,
        current_payload,
        sequence=sequence,
        sections=WS_DELTA_SECTIONS,
    )

    if not delta.get("changed_sections"):
        return []

    event_map = {
        "pnl_summary": "pnl_update",
        "positions": "position_update",
        "governance": "governance_alert",
        "execution": "execution_alert",
        "broker": "broker_status",
        "risk": "risk_update",
    }

    messages = []
    for section in delta["changed_sections"]:
        msg_type = event_map.get(section, "dashboard_delta")
        messages.append({
            "message_type": msg_type,
            "payload_version": delta["payload_version"],
            "generated_at": delta["generated_at"],
            "sequence": sequence,
            "stale_after_ms": delta.get("stale_after_ms", 15000),
            "changed_sections": [section],
            "section": section,
            "transport": "websocket_delta",
            "data": {section: delta["data"][section]},
        })

    return messages


def build_delta_ws_message(
    previous_payload: dict[str, Any] | None,
    current_state: DashboardState,
    *,
    sequence: int,
) -> dict[str, Any]:
    """
    Backward-compatible aggregate delta helper.

    The websocket router now emits one lightweight message per changed section,
    while existing smoke tests and callers still use the original aggregate
    shape. Keep this helper as a stable contract boundary.
    """

    current_payload = build_frontend_payload(current_state)
    return build_websocket_delta(
        previous_payload,
        current_payload,
        sequence=sequence,
        sections=WS_DELTA_SECTIONS,
    )


def build_heartbeat_ws_message(
    *,
    sequence: int,
) -> dict[str, Any]:
    return {
        "message_type": "dashboard_heartbeat",
        "payload_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sequence": sequence,
        "changed_sections": [],
        "data": {},
        "stale_after_ms": 15000,
    }


def build_ws_message_from_runtime_event(
    event: dict[str, Any],
    *,
    sequence: int,
    stale_after_ms: int = 15000,
) -> dict[str, Any]:
    """
    Compatibility adapter for future event-bus-backed websocket delivery.

    Existing websocket snapshot/delta routing remains unchanged; this helper
    lets typed runtime events be rendered into the current websocket message
    shape when a caller opts in.
    """

    return runtime_event_to_ws_message(
        event,
        sequence=sequence,
        stale_after_ms=stale_after_ms,
    )


def is_stale_ws_message(
    message: dict[str, Any],
    *,
    last_sequence: int,
    now_ms: int | None = None,
) -> bool:
    sequence = _safe_int(message.get("sequence"), -1)
    if sequence <= last_sequence:
        return True

    generated_at = message.get("generated_at")
    if not generated_at:
        return False

    generated_ms = _timestamp_ms(str(generated_at))
    if generated_ms is None:
        return False

    current_ms = now_ms if now_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
    stale_after_ms = _safe_int(message.get("stale_after_ms"), 15000)
    return current_ms - generated_ms > stale_after_ms


def create_ws_router(
    state_provider: DashboardStateProvider | None = None,
    *,
    interval_seconds: float = 5.0,
) -> APIRouter:
    provider = state_provider or default_dashboard_state_provider
    router = APIRouter()

    @router.websocket("/ws/v1/dashboard-state")
    async def dashboard_state_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        sequence = 0
        previous_payload: dict[str, Any] | None = None

        try:
            state = _state_from_provider(provider)
            initial_payload = build_initial_ws_message(
                state,
                sequence=sequence,
            )
            await websocket.send_json(initial_payload)
            previous_payload = initial_payload

            while True:
                await asyncio.sleep(interval_seconds)
                sequence += 1
                state = _state_from_provider(provider)
                messages = build_delta_ws_messages(
                    previous_payload,
                    state,
                    sequence=sequence,
                )

                if messages:
                    for msg in messages:
                        await websocket.send_json(msg)
                    previous_payload = build_frontend_payload(state)
                    continue

                await websocket.send_json(
                    build_heartbeat_ws_message(sequence=sequence)
                )
        except WebSocketDisconnect:
            return

    return router


def _state_from_provider(provider: DashboardStateProvider) -> DashboardState:
    state = provider()
    if not isinstance(state, DashboardState):
        raise TypeError("dashboard state provider must return DashboardState")
    return state


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _timestamp_ms(value: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    return int(parsed.timestamp() * 1000)


__all__ = [
    "DashboardStateProvider",
    "WS_DELTA_SECTIONS",
    "WEBSOCKET_EVENT_TYPES",
    "build_delta_ws_message",
    "build_delta_ws_messages",
    "build_heartbeat_ws_message",
    "build_initial_ws_message",
    "build_ws_message_from_runtime_event",
    "create_ws_router",
    "default_dashboard_state_provider",
    "is_stale_ws_message",
]
