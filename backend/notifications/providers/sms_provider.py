"""
SMS Notification Provider Stub for CSS
"""

import logging
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.sms")

class SMSNotificationProvider(BaseNotificationProvider):
    """
    SMS delivery channel provider stub.
    
    Responsibility: Simulate sending SMS alerts.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Stateless and thread-safe.
    Integration: Configured and registered inside NotificationDeliveryRouter.
    """
    @property
    def channel_name(self) -> str:
        return "sms"

    def send(self, event: Event) -> bool:
        message = event.payload.get("message", "")
        logger.info(f"[SMS Provider Stub] Sending SMS text to user {event.user_id}: {message}")
        return True
