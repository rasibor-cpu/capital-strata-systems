"""
Notification Delivery Router for CSS

Registers delivery channels and routes Events to appropriate provider instances.
"""

from typing import Dict
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

class NotificationDeliveryRouter:
    """
    Manages channel providers and triggers send calls.
    
    Responsibility: Route alerts to their target delivery channels.
    Dependencies: backend.events.event_models.Event, BaseNotificationProvider
    Thread-safety: Read/write registration list should be synchronized if altered dynamically.
    Integration: Leveraged by NotificationService.
    """
    def __init__(self):
        self._providers: Dict[str, BaseNotificationProvider] = {}

    def register_provider(self, provider: BaseNotificationProvider) -> None:
        """Register a delivery channel provider."""
        self._providers[provider.channel_name] = provider

    def unregister_provider(self, channel_name: str) -> None:
        """Unregister a delivery channel provider."""
        self._providers.pop(channel_name, None)

    def deliver_channel(self, channel_name: str, event: Event) -> bool:
        """Deliver the notification Event via specified channel."""
        provider = self._providers.get(channel_name)
        if not provider:
            return False
        return provider.send(event)
