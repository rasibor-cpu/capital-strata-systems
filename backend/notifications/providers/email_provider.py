"""
Email Notification Provider Stub for CSS
"""

import logging
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.email")

class EmailNotificationProvider(BaseNotificationProvider):
    """
    Email delivery channel provider stub.
    
    Responsibility: Simulate sending email alerts.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Stateless and thread-safe.
    Integration: Configured and registered inside NotificationDeliveryRouter.
    """
    @property
    def channel_name(self) -> str:
        return "email"

    def send(self, event: Event) -> bool:
        title = event.payload.get("title", "")
        message = event.payload.get("message", "")
        logger.info(f"[Email Provider Stub] Sending email to user {event.user_id}: Title: {title} | Message: {message}")
        return True
