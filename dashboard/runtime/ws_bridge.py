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


DashboardStateProvider = Callable[[], DashboardState]
WS_DELTA_SECTIONS = (
    "pnl_summary",
    "positions",
    "governance",
    "execution",
    "risk",
)


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


def build_delta_ws_message(
    previous_payload: dict[str, Any] | None,
    current_state: DashboardState,
    *,
    sequence: int,
) -> dict[str, Any]:
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
                delta = build_delta_ws_message(
                    previous_payload,
                    state,
                    sequence=sequence,
                )

                if delta["changed_sections"]:
                    await websocket.send_json(delta)
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


__all__ = [
    "DashboardStateProvider",
    "WS_DELTA_SECTIONS",
    "build_delta_ws_message",
    "build_heartbeat_ws_message",
    "build_initial_ws_message",
    "create_ws_router",
    "default_dashboard_state_provider",
]
