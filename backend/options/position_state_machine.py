from __future__ import annotations

from dataclasses import dataclass


DISCOVERED = "DISCOVERED"
APPROVED = "APPROVED"
PAPER_OPEN = "PAPER_OPEN"
ACTIVE = "ACTIVE"
EXPIRING = "EXPIRING"
EXPIRED_WORTHLESS = "EXPIRED_WORTHLESS"
ASSIGNED = "ASSIGNED"
EXERCISED = "EXERCISED"
CLOSED_EARLY = "CLOSED_EARLY"
COMPLETED = "COMPLETED"

TERMINAL_PRE_COMPLETION = {EXPIRED_WORTHLESS, ASSIGNED, EXERCISED, CLOSED_EARLY}
VALID_STATES = {
    DISCOVERED,
    APPROVED,
    PAPER_OPEN,
    ACTIVE,
    EXPIRING,
    EXPIRED_WORTHLESS,
    ASSIGNED,
    EXERCISED,
    CLOSED_EARLY,
    COMPLETED,
}
ALLOWED_TRANSITIONS = {
    DISCOVERED: {APPROVED},
    APPROVED: {PAPER_OPEN},
    PAPER_OPEN: {ACTIVE},
    ACTIVE: {EXPIRING, CLOSED_EARLY},
    EXPIRING: {EXPIRED_WORTHLESS, ASSIGNED, EXERCISED, CLOSED_EARLY},
    EXPIRED_WORTHLESS: {COMPLETED},
    ASSIGNED: {COMPLETED},
    EXERCISED: {COMPLETED},
    CLOSED_EARLY: {COMPLETED},
    COMPLETED: set(),
}


class PositionStateMachineError(ValueError):
    """Raised when a paper income lifecycle transition is invalid."""


@dataclass(frozen=True)
class StateTransition:
    from_state: str
    to_state: str
    event_type: str


class PositionStateMachine:
    def transition(self, current_state: str, next_state: str) -> StateTransition:
        current = str(current_state or "").strip().upper()
        target = str(next_state or "").strip().upper()
        if current not in VALID_STATES:
            raise PositionStateMachineError(f"Invalid current state: {current_state}")
        if target not in VALID_STATES:
            raise PositionStateMachineError(f"Invalid next state: {next_state}")
        if target not in ALLOWED_TRANSITIONS[current]:
            raise PositionStateMachineError(f"Invalid transition: {current}->{target}")
        return StateTransition(current, target, f"{current}_TO_{target}")


__all__ = [
    "ACTIVE",
    "ALLOWED_TRANSITIONS",
    "APPROVED",
    "ASSIGNED",
    "CLOSED_EARLY",
    "COMPLETED",
    "DISCOVERED",
    "EXERCISED",
    "EXPIRING",
    "EXPIRED_WORTHLESS",
    "PAPER_OPEN",
    "PositionStateMachine",
    "PositionStateMachineError",
    "TERMINAL_PRE_COMPLETION",
]
