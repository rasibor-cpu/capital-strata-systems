"""
Notification Service for CSS Enterprise Notification Framework

Integrates templates, preferences, delivery routing, persistent queues,
and scheduling into a unified service interface.
"""

import threading
from typing import Dict, List, Optional
from backend.events.event_models import Event
from backend.common.configuration import NotificationConfig
from backend.common.exceptions import ValidationException
from backend.common.logger import get_logger
from backend.notifications.notification_models import (
    get_notification_channels,
    get_notification_retry_count,
    set_notification_retry_count,
    get_notification_status,
    set_notification_status,
)
from backend.notifications.notification_queue import NotificationQueue
from backend.notifications.notification_history import NotificationHistory
from backend.notifications.notification_delivery import NotificationDeliveryRouter
from backend.notifications.notification_templates import NotificationTemplates
from backend.notifications.notification_scheduler import NotificationScheduler
from backend.notifications.notification_preferences import UserPreferences

logger = get_logger("css.notifications.service")

class NotificationService:
    """
    Primary service interface for the Notification Framework.
    Supports dependency injection and manages notification flows.
    
    Responsibility: Orchestrate preference filtering, routing, scheduling, queueing, and history tracking.
    Dependencies: NotificationConfig, NotificationQueue, NotificationHistory, NotificationDeliveryRouter, NotificationTemplates, NotificationScheduler
    Thread-safety: Fully thread-safe operations on preferences and relies on locked sub-components.
    Integration: Exposes standard APIs for trading engines, risk monitors, and administrative scripts.
    """
    def __init__(
        self,
        config: NotificationConfig,
        queue: NotificationQueue,
        history: NotificationHistory,
        router: NotificationDeliveryRouter,
        templates: NotificationTemplates,
        scheduler: NotificationScheduler
    ):
        config.validate()
        self.config = config
        self.queue = queue
        self.history = history
        self.router = router
        self.templates = templates
        self.scheduler = scheduler
        self._preferences: Dict[str, UserPreferences] = {}
        self._pref_lock = threading.Lock()

    def set_user_preferences(self, user_id: str, prefs: UserPreferences) -> None:
        """Assign preferences configuration for a specific user ID."""
        with self._pref_lock:
            self._preferences[user_id] = prefs

    def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Retrieve preferences configuration for a user ID, falling back to defaults."""
        with self._pref_lock:
            return self._preferences.get(user_id, UserPreferences(user_id=user_id))

    def notify(self, event: Event) -> bool:
        """
        Deliver a notification Event.
        Checks user preferences. Routes to registered channel providers.
        Saves outcome to delivery history. If failed, appends to persistent retry queue.
        """
        event.validate()
        user_id = event.user_id or "system"
        prefs = self.get_user_preferences(user_id)

        # Check quiet hours and severity
        if not prefs.should_deliver(event.severity, event.timestamp):
            set_notification_status(event, "FILTERED")
            self.history.append(event)
            logger.info(f"Notification event {event.event_id} filtered for user {user_id}")
            return False

        channels = get_notification_channels(event)
        if not channels:
            channels = self.config.default_channels

        attempted = []
        all_successful = True

        for channel in channels:
            if prefs.is_channel_enabled(channel):
                attempted.append(channel)
                success = self.router.deliver_channel(channel, event)
                if not success:
                    all_successful = False
                    # Escalation Rule: if email fails, escalate to SMS
                    if channel == "email" and "sms" not in channels and prefs.is_channel_enabled("sms"):
                        logger.warning(f"Email delivery failed for event {event.event_id}. Escalating to SMS channel.")
                        sms_success = self.router.deliver_channel("sms", event)
                        if sms_success:
                            logger.info(f"Escalation delivery of {event.event_id} via SMS successful.")
                            all_successful = True

        if not attempted:
            set_notification_status(event, "FILTERED_NO_CHANNELS")
            self.history.append(event)
            return False

        if all_successful:
            set_notification_status(event, "SENT")
            self.history.append(event)
            return True
        else:
            set_notification_status(event, "RETRYING")
            self.queue.append(event)
            return False

    def honesty_status(self) -> dict:
        """AR-022 customer-visible notification operational honesty."""
        from backend.product_honesty import notification_honesty_status

        return notification_honesty_status()

    def process_queue(self) -> int:
        """
        Process all currently queued notifications, retrying delivery.
        Updates retry counts and records failures to history if max retries is exceeded.
        """
        pending = self.queue.load()
        self.queue.clear()
        processed = 0

        for event in pending:
            processed += 1
            retries = get_notification_retry_count(event)
            if retries >= self.config.max_retries:
                set_notification_status(event, "FAILED_MAX_RETRIES")
                self.history.append(event)
                continue

            set_notification_retry_count(event, retries + 1)
            user_id = event.user_id or "system"
            prefs = self.get_user_preferences(user_id)

            channels = get_notification_channels(event)
            if not channels:
                channels = self.config.default_channels

            all_successful = True
            for channel in channels:
                if prefs.is_channel_enabled(channel):
                    success = self.router.deliver_channel(channel, event)
                    if not success:
                        all_successful = False

            if all_successful:
                set_notification_status(event, "SENT")
                self.history.append(event)
            else:
                if get_notification_retry_count(event) >= self.config.max_retries:
                    set_notification_status(event, "FAILED")
                    self.history.append(event)
                else:
                    self.queue.append(event)

        return processed

    def process_scheduler(self, current_time: Optional[float] = None) -> int:
        """
        Check scheduler for due notifications and dispatch them.
        """
        due_events = self.scheduler.get_pending(current_time)
        for event in due_events:
            self.notify(event)
        return len(due_events)

    def handle_event(self, event: Event) -> None:
        """Passive event bus subscriber callback."""
        try:
            if event.event_type == "REPORT_GENERATED":
                from backend.notifications.notification_models import create_notification_event
                title = event.payload.get("title", "Report Generated")
                report_type = event.payload.get("report_type", "UNKNOWN")
                message = f"Report '{title}' ({report_type}) is ready for review."
                notif = create_notification_event(
                    severity="INFO",
                    category="REPORTING",
                    title=title,
                    message=message,
                    user_id=event.user_id or "system",
                    delivery_channels=["email", "desktop"],
                    source="reporting_delivery"
                )
                self.notify(notif)
            elif event.severity in ("WARNING", "CRITICAL") or "delivery_channels" in event.payload:
                self.notify(event)
        except Exception as e:
            logger.error(f"Error in NotificationService handle_event: {e}")

