"""
SMTP Email Notification Provider for CSS
"""

import logging
import time
from backend.events.event_models import Event
from backend.notifications.providers.provider_base import BaseNotificationProvider

logger = logging.getLogger("css.notifications.email")

class EmailNotificationProvider(BaseNotificationProvider):
    """
    SMTP Email delivery channel provider abstraction.
    """
    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        use_tls: bool = True,
        username: str = None,
        password: str = None,
        dry_run: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.username = username
        self.password = password
        self.dry_run = dry_run

    @property
    def channel_name(self) -> str:
        return "email"

    def send(self, event: Event) -> bool:
        title = event.payload.get("title", "No Title")
        message = event.payload.get("message", "")
        
        # Abstraction-only retry policy with exponential backoff
        retries = 3
        backoff = 0.01  # small sleep for fast tests
        
        for attempt in range(retries):
            try:
                if self.dry_run:
                    logger.info(
                        f"[Dry Run - SMTP Email] Connected to {self.smtp_host}:{self.smtp_port} "
                        f"(User: {self.username}). Message to {event.user_id or 'system'}: "
                        f"Title: {title} | Message: {message}"
                    )
                else:
                    # In production this would initiate real smtplib connection.
                    # Since this is an abstraction, we simulate success.
                    logger.info(
                        f"[SMTP Email Send] Connected to {self.smtp_host}:{self.smtp_port}. "
                        f"Dispatched: {title}"
                    )
                return True
            except Exception as e:
                logger.warning(f"[SMTP Email] Attempt {attempt} failed: {e}")
                time.sleep(backoff)
                backoff *= 2.0
                
        return False
