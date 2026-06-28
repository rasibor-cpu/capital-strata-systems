# Enterprise Notification Framework (EWP-1.A Foundation)

This document covers the architecture, interfaces, and integration details for the Enterprise Notification Framework scaffolding.

## 1. Architecture

The Notification Framework exposes a single orchestrator service: `NotificationService`. It relies on user preferences (enabled channels, quiet hours filters), templates, and a persistent queue for retries.

```mermaid
graph TD
    Trigger[Any Event Generator] -->|notify event| NotificationService
    NotificationService -->|apply| Preferences[UserPreferences]
    NotificationService -->|render| Templates[NotificationTemplates]
    NotificationService -->|dispatch| Router[NotificationDeliveryRouter]
    Router -->|send| Providers[Providers: Email, SMS, Push, Desktop]
    NotificationService -->|failure queue| PersistentQueue[NotificationQueue JSON]
```

## 2. Event Model Standard (Standard #1)

All messages are encapsulated strictly within the canonical `Event` model defined in `backend/events`. Notification parameters are stored inside the `payload` dictionary of the Event:
* `payload["title"]`: Short alert title.
* `payload["message"]`: Complete formatted notification message.
* `payload["delivery_channels"]`: Target channels list (e.g., `["email", "push"]`).
* `payload["retry_count"]`: Number of delivery retry iterations.
* `payload["delivery_status"]`: Status of this dispatch (`PENDING`, `SENT`, `RETRYING`, `FAILED`).

## 3. Public API

### Configuration
Exposed via the `NotificationConfig` dataclass:
```python
from backend.notifications import NotificationConfig

config = NotificationConfig(
    max_retries=3,
    default_channels=["email", "desktop"]
)
```

### Notification Service
```python
from backend.notifications import NotificationService

service = NotificationService(
    config=config,
    queue=queue,
    history=history,
    router=router,
    templates=templates,
    scheduler=scheduler
)

# Dispatch event notification
service.notify(event)
```

## 4. Persistent Formats

Standard persistence APIs are used (`load()`, `save()`, `append()`, `clear()`).

* **Queue File:** `artifacts/notifications/css_notification_queue.json`
* **History File:** `artifacts/notifications/css_notification_history.json`

## 5. Verification

Run the test suite using:
```powershell
python -m pytest tests/test_notification_framework.py
```
