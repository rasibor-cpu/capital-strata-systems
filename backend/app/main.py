"""
REA Capital Trading Engine
Screen Orchestration (Backend Entry Point)

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

Posting (Phase 13):
- posting_entry: validate + store DRAFT
- posting_submit: DRAFT -> SUBMITTED
- posting_review: read-only ticket view
- posting_approval/result remain placeholders (next)
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
from .screens.posting import posting_entry_handler
from .screens.posting_lifecycle import posting_review_handler, posting_submit_handler


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


def posting_entry_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_entry_handler(request.payload, request.user_id)
    return ScreenResponse(
        screen_id=request.screen_id,
        status="ok",
        message="Posting entry (validate + store draft)",
        data=data,
    )


def posting_submit_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_submit_handler(request.payload, request.user_id)
    if data.get("ok"):
        return ScreenResponse(
            screen_id=request.screen_id,
            status="ok",
            message="Ticket submitted",
            data=data,
        )
    return ScreenResponse(
        screen_id=request.screen_id,
        status="error",
        message="Submit failed",
        data=data,
    )


def posting_review_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_review_handler(request.payload)
    if data.get("ok"):
        return ScreenResponse(
            screen_id=request.screen_id,
            status="ok",
            message="Posting ticket review",
            data=data,
        )
    return ScreenResponse(
        screen_id=request.screen_id,
        status="error",
        message="Review failed",
        data=data,
    )


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

# Implemented screens
SCREEN_REGISTRY.register("health_check", health_check_screen)
SCREEN_REGISTRY.register("diagnostics", diagnostics_screen)
SCREEN_REGISTRY.register("screen_index", screen_index_screen)

# Engine/Risk/Reporting placeholders
SCREEN_REGISTRY.register("engine_replay_runner", placeholder_screen)
SCREEN_REGISTRY.register("risk_override_review", placeholder_screen)
SCREEN_REGISTRY.register("reports_center", placeholder_screen)

# Posting screens (implemented)
SCREEN_REGISTRY.register("posting_entry", posting_entry_screen)
SCREEN_REGISTRY.register("posting_submit", posting_submit_screen)
SCREEN_REGISTRY.register("posting_review", posting_review_screen)

# Posting placeholders (next)
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
