"""
REA Capital Trading Engine
Phase 12 — Screen & UI Orchestration (Backend Entry Point)

This module is the single orchestration gateway between:
- UI / Screens (frontend, CLI, dashboards, admin panels)
- Backend intents, diagnostics, and prompt-only engine modules

HARD CONSTRAINTS (ENFORCED):
- NO trade execution
- NO order placement
- NO auto-risk escalation
- Prompt / diagnostics / routing ONLY

All screens must register here.
All UI requests must pass through the ScreenRegistry.
"""

from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass
import datetime


# ---------------------------------------------------------------------
# Screen Request / Response Contracts
# ---------------------------------------------------------------------

@dataclass
class ScreenRequest:
    screen_id: str
    action: str
    payload: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: datetime.datetime = datetime.datetime.utcnow()


@dataclass
class ScreenResponse:
    screen_id: str
    status: str
    message: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------
# Screen Registry
# ---------------------------------------------------------------------

class ScreenRegistry:
    """
    Central registry for all UI screens.

    Each screen registers:
    - screen_id (unique)
    - handler function

    The handler receives a ScreenRequest and returns ScreenResponse.
    """

    def __init__(self) -> None:
        self._registry: Dict[str, Callable[[ScreenRequest], ScreenResponse]] = {}

    def register(self, screen_id: str, handler: Callable[[ScreenRequest], ScreenResponse]) -> None:
        if screen_id in self._registry:
            raise ValueError(f"Screen already registered: {screen_id}")
        self._registry[screen_id] = handler

    def dispatch(self, request: ScreenRequest) -> ScreenResponse:
        if request.screen_id not in self._registry:
            return ScreenResponse(
                screen_id=request.screen_id,
                status="error",
                message="Unknown screen",
                data={}
            )
        handler = self._registry[request.screen_id]
        return handler(request)


# ---------------------------------------------------------------------
# Global Screen Registry Instance
# ---------------------------------------------------------------------

SCREEN_REGISTRY = ScreenRegistry()


# ---------------------------------------------------------------------
# Example / Placeholder Screen Handlers
# (These will be replaced incrementally in Phase 12.x)
# ---------------------------------------------------------------------

def health_check_screen(request: ScreenRequest) -> ScreenResponse:
    return ScreenResponse(
        screen_id=request.screen_id,
        status="ok",
        message="Backend orchestration online",
        data={
            "server_time": datetime.datetime.utcnow().isoformat(),
            "engine_mode": "prompt-only",
            "execution_enabled": False
        }
    )


def diagnostics_screen(request: ScreenRequest) -> ScreenResponse:
    return ScreenResponse(
        screen_id=request.screen_id,
        status="ok",
        message="Diagnostics endpoint",
        data={
            "requested_action": request.action,
            "payload_keys": list(request.payload.keys())
        }
    )


# ---------------------------------------------------------------------
# Screen Registration
# ---------------------------------------------------------------------

SCREEN_REGISTRY.register("health_check", health_check_screen)
SCREEN_REGISTRY.register("diagnostics", diagnostics_screen)


# ---------------------------------------------------------------------
# Orchestration Entry Function
# ---------------------------------------------------------------------

def handle_screen_request(
    screen_id: str,
    action: str,
    payload: Dict[str, Any],
    user_id: Optional[str] = None
) -> ScreenResponse:
    """
    Single entry point for ALL UI → backend interactions.
    """

    request = ScreenRequest(
        screen_id=screen_id,
        action=action,
        payload=payload,
        user_id=user_id
    )

    return SCREEN_REGISTRY.dispatch(request)


# ---------------------------------------------------------------------
# Manual Test Hook (safe, non-executing)
# ---------------------------------------------------------------------

if __name__ == "__main__":
    # Simple sanity check
    resp = handle_screen_request(
        screen_id="health_check",
        action="ping",
        payload={}
    )
    print(resp)
