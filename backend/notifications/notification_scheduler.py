"""
Notification Scheduler for CSS Notification Framework

Tracks scheduled notification events and processes due items.
"""

import time
from dataclasses import dataclass
from typing import List, Optional
from backend.events.event_models import Event

@dataclass
class ScheduledNotification:
    """Wrapper holding an Event and its target epoch execution timestamp."""
    event: Event
    scheduled_time: float

class NotificationScheduler:
    """
    Manages deferred notification triggers in-memory.
    
    Responsibility: Queue future alerts (e.g., digests, hourly checkpoints).
    Dependencies: backend.events.event_models.Event
    Thread-safety: Not thread-safe (should be synchronized by caller).
    Integration: Polled by NotificationService during runtime loop ticks.
    """
    def __init__(self):
        self._schedule: List[ScheduledNotification] = []

    def schedule(self, event: Event, scheduled_time: float) -> None:
        """Schedule a notification Event for later execution."""
        self._schedule.append(ScheduledNotification(event, scheduled_time))

    def get_pending(self, current_time: Optional[float] = None) -> List[Event]:
        """Collect and remove all due notification Events from the schedule list."""
        if current_time is None:
            current_time = time.time()
        
        due = []
        remaining = []
        for item in self._schedule:
            if item.scheduled_time <= current_time:
                due.append(item.event)
            else:
                remaining.append(item)
        self._schedule = remaining
        return due
