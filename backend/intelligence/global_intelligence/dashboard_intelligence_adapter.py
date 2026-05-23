from __future__ import annotations

from typing import Any

from .intelligence_state_manager import IntelligenceStateManager
from .event_models import EventSeverity


def _serialize_event(event: Any) -> dict:
    try:
        return {
            "event_id": getattr(event, "event_id", ""),
            "title": getattr(event, "title", ""),
            "category": getattr(event, "category", "UNKNOWN").value if hasattr(event, "category") else "UNKNOWN",
            "severity": getattr(event, "severity", "LOW").name if hasattr(event, "severity") else EventSeverity.LOW.name,
            "confidence": getattr(event, "confidence", 0.0),
            "source": getattr(event, "source", ""),
            "affected_assets": list(getattr(event, "affected_assets", [])),
            "description": getattr(event, "description", ""),
        }
    except Exception:
        return {
            "event_id": "",
            "title": "",
            "category": "UNKNOWN",
            "severity": EventSeverity.LOW.name,
            "confidence": 0.0,
            "source": "",
            "affected_assets": [],
            "description": "",
        }


def build_dashboard_intelligence_payload(state_manager: IntelligenceStateManager) -> dict:
    default_payload = {
        "current_regime": "NORMAL",
        "governance_response": {},
        "active_events": [],
        "event_count": 0,
        "highest_severity": "LOW",
        "average_confidence": 0.0,
        "gie_status": "OK",
    }

    if state_manager is None:
        return default_payload

    try:
        active_events = state_manager.get_active_events()
        event_count = len(active_events)
        highest_severity = "LOW"
        confidence_values = []

        for event in active_events:
            if event.severity.value > EventSeverity[highest_severity].value:
                highest_severity = event.severity.name
            confidence_values.append(float(event.confidence or 0.0))

        average_confidence = sum(confidence_values) / event_count if event_count else 0.0

        return {
            "current_regime": state_manager.get_current_regime().value,
            "governance_response": state_manager.get_governance_response().__dict__,
            "active_events": [_serialize_event(event) for event in active_events],
            "event_count": event_count,
            "highest_severity": highest_severity,
            "average_confidence": round(average_confidence, 2),
            "gie_status": "OK",
        }
    except Exception:
        return {**default_payload, "gie_status": "ERROR"}
