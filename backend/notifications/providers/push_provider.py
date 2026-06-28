"""
Push Notification Provider Stub for CSS
"""

import logging
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.push")

class PushNotificationProvider(BaseNotificationProvider):
    """
    Push delivery channel provider stub.
    
    Responsibility: Simulate sending mobile Push notifications.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Stateless and thread-safe.
    Integration: Configured and registered inside NotificationDeliveryRouter.
    """
    @property
    def channel_name(self) -> str:
        return "push"

    def send(self, event: Event) -> bool:
        title = event.payload.get("title", "")
        message = event.payload.get("message", "")
        logger.info(f"[Push Provider Stub] Sending push to user {event.user_id}: Title: {title} | Message: {message}")
        return True
