"""
Notification Models for CSS Notification Framework

Helper functions to instantiate or extract notification payloads
using the canonical Enterprise Event model from backend.events.
"""

from backend.events.event_models import Event
from typing import List, Dict, Any, Optional

def create_notification_event(
    severity: str,
    category: str,
    title: str,
    message: str,
    user_id: str,
    delivery_channels: List[str],
    source: str = "notification_service",
    correlation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None
) -> Event:
    """
    Helper to construct a canonical Event formatted as a notification.
    
    Responsibility: Standardizes Event creation for notifications.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Pure function, safe.
    Integration: Exposes builders for other subsystems producing notification requests.
    """
    event_payload = {
        "title": title,
        "message": message,
        "delivery_channels": list(delivery_channels),
        "retry_count": 0,
        "delivery_status": "PENDING",
        "custom_payload": payload or {}
    }
    return Event(
        event_type="NOTIFICATION_DISPATCH",
        severity=severity,
        category=category,
        source=source,
        payload=event_payload,
        user_id=user_id,
        correlation_id=correlation_id,
        session_id=session_id
    )

def get_notification_channels(event: Event) -> List[str]:
    """Extract list of target channels from an Event's payload."""
    return event.payload.get("delivery_channels", [])

def get_notification_retry_count(event: Event) -> int:
    """Extract retry count from an Event's payload."""
    return event.payload.get("retry_count", 0)

def set_notification_retry_count(event: Event, count: int) -> None:
    """Set retry count in an Event's payload."""
    event.payload["retry_count"] = count

def get_notification_status(event: Event) -> str:
    """Extract delivery status from an Event's payload."""
    return event.payload.get("delivery_status", "PENDING")

def set_notification_status(event: Event, status: str) -> None:
    """Set delivery status in an Event's payload."""
    event.payload["delivery_status"] = status
