"""
Base Notification Provider Interface for CSS

All delivery channel integrations must inherit from this class.
"""

from abc import ABC, abstractmethod
from backend.events.event_models import Event

class BaseNotificationProvider(ABC):
    """
    Abstract Base Class for notification delivery channels.
    
    Responsibility: Standard interface representing individual alert delivery drivers.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Subclass implementations should ensure thread-safe invocation of send().
    Integration: Subclasses are registered inside NotificationDeliveryRouter.
    """
    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Returns the identifier name for the channel (e.g., 'email', 'sms')."""
        pass

    @abstractmethod
    def send(self, event: Event) -> bool:
        """
        Execute dispatch of the event notification.
        Returns True on success, False otherwise.
        """
        pass
