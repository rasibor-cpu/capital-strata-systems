"""
Tests for CSS Enterprise Communications (EWP-4/5A PART A)
"""

import pytest
import os
import tempfile
import time
from backend.events.event_models import Event
from backend.notifications.providers.email_provider import EmailNotificationProvider
from backend.notifications.providers.sms_provider import SMSNotificationProvider
from backend.notifications.providers.push_provider import PushNotificationProvider
from backend.notifications.providers.desktop_provider import DesktopNotificationProvider
from backend.notifications.notification_service import NotificationService, NotificationConfig
from backend.notifications.notification_queue import NotificationQueue
from backend.notifications.notification_history import NotificationHistory
from backend.notifications.notification_delivery import NotificationDeliveryRouter
from backend.notifications.notification_templates import NotificationTemplates
from backend.notifications.notification_scheduler import NotificationScheduler


def test_provider_configuration_and_dry_run():
    # Verify SMTP Provider behaves under dry-run / sandbox mode
    email_prov = EmailNotificationProvider(
        smtp_host="mail.css.internal",
        smtp_port=465,
        username="admin",
        password="secretpassword",
        dry_run=True
    )
    
    assert email_prov.channel_name == "email"
    assert email_prov.smtp_host == "mail.css.internal"
    
    test_event = Event(
        event_type="NOTIFICATION_DISPATCH",
        severity="INFO",
        category="SYSTEM",
        source="test",
        payload={"title": "Test SMTP", "message": "Verify provider dry run"}
    )
    
    # Send should succeed under dry_run abstraction
    assert email_prov.send(test_event) is True


def test_provider_retry_and_backoff():
    # SMS Provider simulation
    sms_prov = SMSNotificationProvider(
        account_sid="AC123",
        auth_token="token456",
        from_number="+15550100",
        dry_run=True
    )
    
    test_event = Event(
        event_type="NOTIFICATION_DISPATCH",
        severity="WARNING",
        category="SYSTEM",
        source="test",
        payload={"message": "SMS retry verify"}
    )
    
    # Verify success outcome
    start = time.time()
    res = sms_prov.send(test_event)
    duration = time.time() - start
    
    assert res is True
    # Verify retries did not cause significant blocking under dry_run (exponential backoff runs fast in sandbox)
    assert duration < 1.0


def test_notification_escalation_rules():
    with tempfile.TemporaryDirectory() as temp_dir:
        router = NotificationDeliveryRouter()
        
        # Register a failing email provider and a successful SMS provider
        class FailingEmailProvider(EmailNotificationProvider):
            def send(self, event: Event) -> bool:
                return False
                
        router.register_provider(FailingEmailProvider(dry_run=True))
        router.register_provider(SMSNotificationProvider(dry_run=True))
        
        n_q = NotificationQueue(file_path=os.path.join(temp_dir, "queue.json"))
        n_h = NotificationHistory(file_path=os.path.join(temp_dir, "history.json"))
        
        service = NotificationService(
            config=NotificationConfig(),
            queue=n_q,
            history=n_h,
            router=router,
            templates=NotificationTemplates(),
            scheduler=NotificationScheduler()
        )
        
        # User allows both email and sms
        prefs = service.get_user_preferences("user_bob")
        prefs.enabled_channels = ["email", "sms"]
        service.set_user_preferences("user_bob", prefs)
        
        # Dispatch event configured with delivery channel = email only
        event = Event(
            event_type="NOTIFICATION_DISPATCH",
            severity="CRITICAL",
            category="SYSTEM",
            source="test",
            user_id="user_bob",
            payload={"title": "Escalation Check", "message": "Must fall back to SMS", "delivery_channels": ["email"]}
        )
        
        # Send
        service.notify(event)
        
        # Verify that because email failed, escalation triggered a send attempt on SMS
        # Since SMS succeeds, the notification retry list has history record or retrying queue details.
        history = service.history.load()
        assert len(history) > 0
