"""
Desktop Notification Provider Stub for CSS
"""

import logging
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.desktop")

class DesktopNotificationProvider(BaseNotificationProvider):
    """
    Desktop delivery channel provider stub.
    
    Responsibility: Simulate rendering OS/Desktop notifications.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Stateless and thread-safe.
    Integration: Configured and registered inside NotificationDeliveryRouter.
    """
    @property
    def channel_name(self) -> str:
        return "desktop"

    def send(self, event: Event) -> bool:
        title = event.payload.get("title", "")
        message = event.payload.get("message", "")
        logger.info(f"[Desktop Provider Stub] Displaying desktop popup for user {event.user_id}: Title: {title} | Message: {message}")
        return True
