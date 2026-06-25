from __future__ import annotations

from datetime import datetime, timezone
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


def build_dashboard_intelligence_payload(
    state_manager: IntelligenceStateManager,
    *,
    canonical_decision: dict[str, Any] | None = None,
) -> dict:
    default_payload = {
        "current_regime": "NORMAL",
        "governance_response": {},
        "active_events": [],
        "event_count": 0,
        "highest_severity": "LOW",
        "average_confidence": 0.0,
        "gie_status": "OK",
        "decision_state": _default_decision_state(),
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
            "decision_state": _decision_state(canonical_decision),
        }
    except Exception:
        return {**default_payload, "gie_status": "ERROR"}


def _default_decision_state() -> dict[str, Any]:
    return {
        "current_market_regime": "UNKNOWN",
        "selected_strategy": "",
        "confidence_score": 0.0,
        "signal_strength": 0.0,
        "portfolio_risk": 0.0,
        "allocation": 0.0,
        "position_size": 0.0,
        "current_decision": "UNKNOWN",
        "decision_age_seconds": 0.0,
        "learning_confidence": 0.0,
        "last_strategy_outcome": "",
    }


def _decision_state(canonical_decision: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(canonical_decision, dict):
        return _default_decision_state()

    timestamp = str(canonical_decision.get("timestamp") or "").strip()
    decision_age_seconds = 0.0
    if timestamp:
        try:
            then = datetime.fromisoformat(timestamp)
            if then.tzinfo is None:
                then = then.replace(tzinfo=timezone.utc)
            decision_age_seconds = max(0.0, (datetime.now(timezone.utc) - then).total_seconds())
        except Exception:
            decision_age_seconds = 0.0

    allocation_payload = canonical_decision.get("allocation", {})
    position_payload = canonical_decision.get("position_size", {})
    learning_context = canonical_decision.get("learning_context", {})

    return {
        "current_market_regime": str(canonical_decision.get("market_regime") or "UNKNOWN"),
        "selected_strategy": str(canonical_decision.get("selected_strategy") or ""),
        "confidence_score": float(canonical_decision.get("confidence", 0.0) or 0.0),
        "signal_strength": float(canonical_decision.get("signal_strength", 0.0) or 0.0),
        "portfolio_risk": float(canonical_decision.get("portfolio_risk", 0.0) or 0.0),
        "allocation": float((allocation_payload or {}).get("allocation_amount", 0.0) or 0.0),
        "position_size": float((position_payload or {}).get("recommended_position_size", 0.0) or 0.0),
        "current_decision": str(canonical_decision.get("entry_decision") or "UNKNOWN"),
        "decision_age_seconds": round(decision_age_seconds, 8),
        "learning_confidence": float((learning_context or {}).get("confidence", 0.0) or 0.0),
        "last_strategy_outcome": str((learning_context or {}).get("last_strategy_outcome") or ""),
    }
