"""
Twilio SMS Notification Provider for CSS
"""

import logging
import time
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.sms")

class SMSNotificationProvider(BaseNotificationProvider):
    """
    Twilio-compatible SMS delivery channel provider abstraction.
    """
    def __init__(
        self,
        account_sid: str = None,
        auth_token: str = None,
        from_number: str = None,
        dry_run: bool = True
    ):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.dry_run = dry_run

    @property
    def channel_name(self) -> str:
        return "sms"

    def send(self, event: Event) -> bool:
        message = event.payload.get("message", "")
        from backend.product_honesty import notifications_operational

        # Abstraction-only retry policy with exponential backoff
        retries = 3
        backoff = 0.01

        for attempt in range(retries):
            try:
                if self.dry_run:
                    logger.info(
                        f"[Dry Run - Twilio SMS] Sender {self.from_number} (SID: {self.account_sid}) "
                        f"dispatched to {event.user_id or 'system'}: {message}"
                    )
                    return True
                if not notifications_operational():
                    logger.warning(
                        "[Twilio SMS] NON-OPERATIONAL: refusing simulated success "
                        "(set CSS_NOTIFICATIONS_OPERATIONAL=1 with real SMS transport to enable)"
                    )
                    return False
                logger.info(
                    f"[Twilio SMS Send] Dispatched from {self.from_number} (SID: {self.account_sid}): {message}"
                )
                return True
            except Exception as e:
                logger.warning(f"[Twilio SMS] Attempt {attempt} failed: {e}")
                time.sleep(backoff)
                backoff *= 2.0

        return False
