from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from .event_models import EventState, EventSeverity, IntelligenceEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventLifecycleManager:
    COOLDOWN_PERIOD = timedelta(hours=4)
    SEVERITY_DOWNGRADE_WINDOWS = {
        EventSeverity.CRITICAL: timedelta(days=3),
        EventSeverity.SEVERE: timedelta(days=5),
    }

    def __init__(self) -> None:
        pass

    def get_event_age(self, event: IntelligenceEvent, now: datetime | None = None) -> timedelta:
        now = now or _utc_now()
        age = now - event.timestamp if event.timestamp else timedelta(0)
        return max(age, timedelta(0))

    def _downgrade_severity(self, event: IntelligenceEvent, age: timedelta) -> None:
        if event.severity == EventSeverity.CRITICAL and age >= self.SEVERITY_DOWNGRADE_WINDOWS[EventSeverity.CRITICAL]:
            event.severity = EventSeverity.SEVERE
        elif event.severity == EventSeverity.SEVERE and age >= self.SEVERITY_DOWNGRADE_WINDOWS[EventSeverity.SEVERE]:
            event.severity = EventSeverity.HIGH

    def _apply_cooldown(self, event: IntelligenceEvent, now: datetime) -> None:
        if event.event_state == EventState.EXPIRED and event.cooldown_until is None:
            event.cooldown_until = now + self.COOLDOWN_PERIOD
        elif event.event_state == EventState.EXPIRED and event.cooldown_until and now >= event.cooldown_until:
            event.event_state = EventState.ARCHIVED

    def transition_event(self, event: IntelligenceEvent, now: datetime | None = None) -> None:
        now = now or _utc_now()
        age = self.get_event_age(event, now)

        if event.expiration_time and now >= event.expiration_time:
            event.active = False
            event.event_state = EventState.EXPIRED
            self._apply_cooldown(event, now)
            self._downgrade_severity(event, age)
            return

        if event.event_state == EventState.ARCHIVED:
            return

        if age < timedelta(hours=4):
            event.event_state = EventState.NEW
        elif age < timedelta(days=1):
            event.event_state = EventState.ACTIVE
        elif age < timedelta(days=2):
            event.event_state = EventState.MONITORING
        else:
            event.event_state = EventState.STABILIZING

        self._downgrade_severity(event, age)

    def update_events(self, events: Iterable[IntelligenceEvent], now: datetime | None = None) -> None:
        for event in events:
            self.transition_event(event, now)
