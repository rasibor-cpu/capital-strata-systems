"""
REA Capital Trading Engine
Phase 12 — Screen & UI Orchestration (Backend Entry Point)
Phase 13.2 — Posting screens registered as safe placeholders

HARD CONSTRAINTS (ENFORCED):
- NO trade execution
- NO order placement
- NO auto-risk escalation
- Prompt / diagnostics / routing ONLY

Architecture:
- main.py is thin orchestration gateway
- screen handlers live under backend/app/screens/
- screen taxonomy is authoritative
- contracts are centralized in orchestrator_contracts.py
"""

from typing import Dict, Callable
from .screen_taxonomy import SCREEN_INDEX, list_screen_ids
from .orchestrator_contracts import ScreenRequest, ScreenResponse

from .screens.core import (
    health_check_handler,
    diagnostics_handler,
    screen_index_handler,
)
from .screens.not_implemented import not_implemented_payload


# ---------------------------------------------------------------------
# Screen Registry
# ---------------------------------------------------------------------

class ScreenRegistry:
    def __init__(self) -> None:
        self._registry: Dict[str, Callable[[ScreenRequest], ScreenResponse]] = {}

    def register(self, screen_id: str, handler: Callable[[ScreenRequest], ScreenResponse]) -> None:
        if screen_id not in SCREEN_INDEX:
            raise ValueError(f"Cannot register screen not in taxonomy: {screen_id}")
        if screen_id in self._registry:
            raise ValueError(f"Screen already registered: {screen_id}")
        self._registry[screen_id] = handler

    def registry_map(self) -> Dict[str, bool]:
        return {sid: (sid in self._registry) for sid in list_screen_ids()}

    def dispatch(self, request: ScreenRequest) -> ScreenResponse:
        if request.screen_id not in SCREEN_INDEX:
            return ScreenResponse(
                screen_id=request.screen_id,
                status="error",
                message="Unknown screen (not in taxonomy)",
                data={"known_screens": list_screen_ids()},
            )

        if request.screen_id not in self._registry:
            return ScreenResponse(
                screen_id=request.screen_id,
                status="error",
                message="Screen exists in taxonomy but is not registered",
                data={"screen_def": SCREEN_INDEX[request.screen_id].__dict__},
            )

        return self._registry[request.screen_id](request)


SCREEN_REGISTRY = ScreenRegistry()


# ---------------------------------------------------------------------
# Screen Adapters (wrap pure handlers into ScreenResponse)
# ---------------------------------------------------------------------

def health_check_screen(request: ScreenRequest) -> ScreenResponse:
    data = health_check_handler(SCREEN_REGISTRY.registry_map())
    return ScreenResponse(
        screen_id=request.screen_id,
        status="ok",
        message="Backend orchestration online",
        data=data,
    )


def diagnostics_screen(request: ScreenRequest) -> ScreenResponse:
    data = diagnostics_handler(request.action, request.payload, request.screen_id)
    return ScreenResponse(
        screen_id=request.screen_id,
        status="ok",
        message="Diagnostics endpoint",
        data=data,
    )


def screen_index_screen(request: ScreenRequest) -> ScreenResponse:
    data = screen_index_handler(SCREEN_REGISTRY.registry_map())
    return ScreenResponse(
        screen_id=request.screen_id,
        status="ok",
        message="Screen index",
        data=data,
    )


def placeholder_screen(request: ScreenRequest) -> ScreenResponse:
    data = not_implemented_payload(request.screen_id, request.action)
    return ScreenResponse(
        screen_id=request.screen_id,
        status="not_implemented",
        message="Screen not implemented yet",
        data=data,
    )


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

# Implemented screens
SCREEN_REGISTRY.register("health_check", health_check_screen)
SCREEN_REGISTRY.register("diagnostics", diagnostics_screen)
SCREEN_REGISTRY.register("screen_index", screen_index_screen)

# Placeholder (taxonomy-defined, not implemented yet)
SCREEN_REGISTRY.register("engine_replay_runner", placeholder_screen)
SCREEN_REGISTRY.register("risk_override_review", placeholder_screen)
SCREEN_REGISTRY.register("reports_center", placeholder_screen)

# Phase 13 — Posting screens (placeholder now; implement next)
SCREEN_REGISTRY.register("posting_entry", placeholder_screen)
SCREEN_REGISTRY.register("posting_review", placeholder_screen)
SCREEN_REGISTRY.register("posting_approval", placeholder_screen)
SCREEN_REGISTRY.register("posting_result", placeholder_screen)


# ---------------------------------------------------------------------
# Orchestration Entry Function
# ---------------------------------------------------------------------

def handle_screen_request(screen_id: str, action: str, payload: dict, user_id: str | None = None) -> ScreenResponse:
    request = ScreenRequest(
        screen_id=screen_id,
        action=action,
        payload=payload,
        user_id=user_id,
    )
    return SCREEN_REGISTRY.dispatch(request)


# ---------------------------------------------------------------------
# Manual Test Hook (safe, non-executing)
# ---------------------------------------------------------------------

if __name__ == "__main__":
    print(handle_screen_request("health_check", "ping", {}))
    print(handle_screen_request("screen_index", "list", {}))
    print(handle_screen_request("posting_entry", "open", {}))
    print(handle_screen_request("unknown_screen", "noop", {}))
