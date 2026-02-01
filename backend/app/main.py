"""
REA Capital Trading Engine
Screen Orchestration (Backend Entry Point)

Prompt-only / workflow-only:
- No trade execution
- No ledger posting
- No auto-risk escalation

Posting lifecycle:
- posting_entry: validate + store DRAFT
- posting_submit: DRAFT -> SUBMITTED
- posting_review: read-only
- posting_approval: checker decision (approve/reject/return)
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
from .screens.posting_approval import posting_approval_handler


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


def health_check_screen(request: ScreenRequest) -> ScreenResponse:
    data = health_check_handler(SCREEN_REGISTRY.registry_map())
    return ScreenResponse(request.screen_id, "ok", "Backend orchestration online", data)


def diagnostics_screen(request: ScreenRequest) -> ScreenResponse:
    data = diagnostics_handler(request.action, request.payload, request.screen_id)
    return ScreenResponse(request.screen_id, "ok", "Diagnostics endpoint", data)


def screen_index_screen(request: ScreenRequest) -> ScreenResponse:
    data = screen_index_handler(SCREEN_REGISTRY.registry_map())
    return ScreenResponse(request.screen_id, "ok", "Screen index", data)


def placeholder_screen(request: ScreenRequest) -> ScreenResponse:
    data = not_implemented_payload(request.screen_id, request.action)
    return ScreenResponse(request.screen_id, "not_implemented", "Screen not implemented yet", data)


def posting_entry_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_entry_handler(request.payload, request.user_id)
    return ScreenResponse(request.screen_id, "ok", "Posting entry (validate + store draft)", data)


def posting_submit_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_submit_handler(request.payload, request.user_id)
    if data.get("ok"):
        return ScreenResponse(request.screen_id, "ok", "Ticket submitted", data)
    return ScreenResponse(request.screen_id, "error", "Submit failed", data)


def posting_review_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_review_handler(request.payload)
    if data.get("ok"):
        return ScreenResponse(request.screen_id, "ok", "Posting ticket review", data)
    return ScreenResponse(request.screen_id, "error", "Review failed", data)


def posting_approval_screen(request: ScreenRequest) -> ScreenResponse:
    data = posting_approval_handler(request.payload, request.user_id)
    if data.get("ok"):
        msg = f"Ticket {data.get('decision', 'decision')}d"
        return ScreenResponse(request.screen_id, "ok", msg, data)
    return ScreenResponse(request.screen_id, "error", "Approval failed", data)


# Register screens
SCREEN_REGISTRY.register("health_check", health_check_screen)
SCREEN_REGISTRY.register("diagnostics", diagnostics_screen)
SCREEN_REGISTRY.register("screen_index", screen_index_screen)

# Posting implemented
SCREEN_REGISTRY.register("posting_entry", posting_entry_screen)
SCREEN_REGISTRY.register("posting_submit", posting_submit_screen)
SCREEN_REGISTRY.register("posting_review", posting_review_screen)
SCREEN_REGISTRY.register("posting_approval", posting_approval_screen)

# Placeholders still
SCREEN_REGISTRY.register("engine_replay_runner", placeholder_screen)
SCREEN_REGISTRY.register("risk_override_review", placeholder_screen)
SCREEN_REGISTRY.register("reports_center", placeholder_screen)
SCREEN_REGISTRY.register("posting_result", placeholder_screen)


def handle_screen_request(screen_id: str, action: str, payload: dict, user_id: str | None = None) -> ScreenResponse:
    req = ScreenRequest(screen_id=screen_id, action=action, payload=payload, user_id=user_id)
    return SCREEN_REGISTRY.dispatch(req)
