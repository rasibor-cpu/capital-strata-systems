"""
Report Models for CSS Reporting Framework

Helper functions to instantiate or extract report payloads
using the canonical Enterprise Event model from backend.events.
"""

from backend.events.event_models import Event
from typing import Dict, Any, Optional

def create_report_event(
    report_type: str,
    title: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    source: str = "reporting_service"
) -> Event:
    """
    Helper to construct a canonical Event formatted as a report.
    
    Responsibility: Standardize Event creation for report artifacts.
    Dependencies: backend.events.event_models.Event
    Thread-safety: Pure function, safe.
    Integration: Exposes builders for report generation logic.
    """
    event_payload = {
        "report_type": report_type.upper(),
        "title": title,
        "content": content,
        "custom_metadata": metadata or {}
    }
    return Event(
        event_type="REPORT_GENERATED",
        severity="INFO",
        category="METRICS",
        source=source,
        payload=event_payload
    )

def get_report_type(event: Event) -> str:
    """Extract report type from an Event's payload."""
    return event.payload.get("report_type", "")

def get_report_title(event: Event) -> str:
    """Extract report title from an Event's payload."""
    return event.payload.get("title", "")

def get_report_content(event: Event) -> str:
    """Extract report content from an Event's payload."""
    return event.payload.get("content", "")
