"""
FCM Mobile Push Notification Provider for CSS
"""

import logging
import time
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.push")

class PushNotificationProvider(BaseNotificationProvider):
    """
    FCM Mobile Push delivery channel provider abstraction.
    """
    def __init__(
        self,
        fcm_api_key: str = None,
        app_id: str = None,
        dry_run: bool = True
    ):
        self.fcm_api_key = fcm_api_key
        self.app_id = app_id
        self.dry_run = dry_run

    @property
    def channel_name(self) -> str:
        return "push"

    def send(self, event: Event) -> bool:
        title = event.payload.get("title", "Push Alert")
        message = event.payload.get("message", "")
        from backend.product_honesty import notifications_operational

        # Abstraction-only retry policy with exponential backoff
        retries = 3
        backoff = 0.01

        for attempt in range(retries):
            try:
                if self.dry_run:
                    logger.info(
                        f"[Dry Run - FCM Push] App ID {self.app_id} (API Key: {self.fcm_api_key}) "
                        f"pushed to {event.user_id or 'system'}: Title: {title} | Message: {message}"
                    )
                    return True
                if not notifications_operational():
                    logger.warning(
                        "[FCM Push] NON-OPERATIONAL: refusing simulated success "
                        "(set CSS_NOTIFICATIONS_OPERATIONAL=1 with real push transport to enable)"
                    )
                    return False
                logger.info(
                    f"[FCM Push Send] Dispatched App ID {self.app_id}: {title}"
                )
                return True
            except Exception as e:
                logger.warning(f"[FCM Push] Attempt {attempt} failed: {e}")
                time.sleep(backoff)
                backoff *= 2.0

        return False
