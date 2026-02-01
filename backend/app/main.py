"""
REA Capital Trading Engine
Screen Orchestration (Backend Entry Point)

HARD CONSTRAINTS (ENFORCED):
- NO trade execution
- NO order placement
- NO auto-risk escalation
- Prompt / diagnostics / routing ONLY

Posting (Phase 13):
- posting_entry: validate + store DRAFT (in-memory)
- posting_submit: DRAFT -> SUBMITTED
- posting_review: read-only ticket view
- posting_approval: checker APPROVE / REJECT / RETURN (state transitions only)
- posting_result: placeholder (next)

NOTE:
- Store is in-memory; restart clears tickets (expected at this phase).
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

from .posting_store import approve_ticket, reject_ticket, return_ticket


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


def posting_approval_screen(request: ScreenRequest) -> ScreenResponse:
    """
    Checker decision screen.

    Expected payload:
      {
        "ticket_id": "T-1002",
        "decision": "approve" | "reject" | "return",
        "reason": "optional but recommended"
      }

    Enforces maker-checker separation via posting_store rules.
    """
    ticket_id = str(request.payload.get("ticket_id", "")).strip()
    decision = str(request.payload.get("decision", "")).strip().lower()
    reason = str(request.payload.get("reason", "")).strip()
    checker_id = request.user_id or "anonymous_checker"

    if not ticket_id:
        return ScreenResponse(
            screen_id=request.screen_id,
            status="error",
            message="Approval failed",
            data={"ok": False, "error": "ticket_id is required"},
        )

    if decision not in {"approve", "reject", "return"}:
        return ScreenResponse(
            screen_id=request.screen_id,
            status="error",
            message="Approval failed",
            data={"ok": False, "error": "decision must be one of: approve, reject, return"},
        )

    try:
        if decision == "approve":
            t = approve_ticket(ticket_id, checker_id)
            data = {
                "ok": True,
                "decision": "approve",
                "ticket": {"ticket_id": t.ticket_id, "status": t.status.value},
                "next_actions": ["posting_result"],
                "note": "Approved (no ledger write yet).",
            }
            return ScreenResponse(
                screen_id=request.screen_id,
                status="ok",
                message="Ticket approved",
                data=data,
            )

        if decision == "reject":
            if not reason:
                reason = "Rejected by checker"
            t = reject_ticket(ticket_id, checker_id, reason)
            data = {
                "ok": True,
                "decision": "reject",
                "ticket": {"ticket_id": t.ticket_id, "status": t.status.value},
                "reason": reason,
                "next_actions": ["posting_result"],
                "note": "Rejected (no ledger write).",
            }
            return ScreenResponse(
                screen_id=request.screen_id,
                status="ok",
                message="Ticket rejected",
                data=data,
            )

        # decision == "return"
        if not reason:
            reason = "Returned for correction"
        t = return_ticket(ticket_id, checker_id, reason)
        data = {
            "ok": True,
            "decision": "return",
            "ticket": {"ticket_id": t.ticket_id, "status": t.status.value},
            "reason": reason,
            "next_actions": ["posting_entry", "posting_submit"],
            "note": "Returned to maker (no ledger write).",
        }
        return ScreenResponse(
            screen_id=request.screen_id,
            status="ok",
            message="Ticket returned",
            data=data,
        )

    except Exception as e:
        return ScreenResponse(
            screen_id=request.screen_id,
            status="error",
            message="Approval failed",
            data={"ok": False, "error": str(e)},
        )


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

# Core screens
SCREEN_REGISTRY.register("health_check", health_check_screen)
SCREEN_REGISTRY.register("diagnostics", diagnostics_screen)
SCREEN_REGISTRY.register("screen_index", screen_index_screen)

# Engine/Risk/Reporting placeholders (for now)
SCREEN_REGISTRY.register("engine_replay_runner", placeholder_screen)
SCREEN_REGISTRY.register("risk_override_review", placeholder_screen)
SCREEN_REGISTRY.register("reports_center", placeholder_screen)

# Posting screens (implemented)
SCREEN_REGISTRY.register("posting_entry", posting_entry_screen)
SCREEN_REGISTRY.register("posting_submit", posting_submit_screen)
SCREEN_REGISTRY.register("posting_review", posting_review_screen)
SCREEN_REGISTRY.register("posting_approval", posting_approval_screen)

# Posting result placeholder (next)
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
