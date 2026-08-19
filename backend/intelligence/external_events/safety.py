"""Safety assertions — external events never enable execution."""

from __future__ import annotations

from backend.intelligence.external_events.models import ExternalEvent


class ExecutionAuthorityViolation(RuntimeError):
    pass


def assert_advisory_only(event: ExternalEvent) -> None:
    if event.execution_allowed or not event.advisory_only:
        raise ExecutionAuthorityViolation(
            f"event {event.event_id} attempted execution authority"
        )


def event_cannot_enable_execution(event: ExternalEvent) -> bool:
    """Return True when the event is correctly barred from enabling execution."""
    try:
        assert_advisory_only(event)
    except ExecutionAuthorityViolation:
        return False
    return True
