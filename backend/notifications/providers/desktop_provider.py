"""
HUD Desktop Notification Provider for CSS
"""

import logging
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.desktop")

class DesktopNotificationProvider(BaseNotificationProvider):
    """
    HUD Desktop delivery channel provider.
    """
    def __init__(self, sound_enabled: bool = True):
        self.sound_enabled = sound_enabled

    @property
    def channel_name(self) -> str:
        return "desktop"

    def send(self, event: Event) -> bool:
        title = event.payload.get("title", "Desktop Alert")
        message = event.payload.get("message", "")

        # Local HUD log only — not a customer pager / production notification transport (AR-022).
        logger.info(
            f"[HUD Desktop Alert][SIMULATED_LOCAL_LOG] Render Notification "
            f"(sound={self.sound_enabled}): "
            f"[{event.severity}] {title}: {message}"
        )
        return True

    @property
    def delivery_simulated(self) -> bool:
        return True
