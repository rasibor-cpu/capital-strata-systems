from __future__ import annotations

from typing import Any

from .economic_calendar_provider import EconomicCalendarProvider
from .event_models import EventSeverity, GovernanceResponse, IntelligenceEvent, RegimeState
from .intelligence_state_manager import IntelligenceStateManager


def _safe_list(value: Any) -> list[Any]:
    try:
        return list(value) if value is not None else []
    except Exception:
        return []


def build_global_risk_meter(active_events: list[IntelligenceEvent] | None = None, current_regime: RegimeState | None = None) -> str:
    active_events = active_events or []
    highest = EventSeverity.LOW
    for event in active_events:
        if isinstance(event, IntelligenceEvent) and event.severity.value > highest.value:
            highest = event.severity
    if current_regime and current_regime == RegimeState.PANIC:
        return "PANIC"
    if highest == EventSeverity.CRITICAL:
        return "PANIC"
    if highest in (EventSeverity.SEVERE,):
        return "DEFENSIVE"
    if highest in (EventSeverity.HIGH, EventSeverity.MODERATE):
        return "CAUTION"
    return "NORMAL"


def build_active_event_feed(active_events: list[IntelligenceEvent] | None = None) -> list[dict[str, Any]]:
    active_events = active_events or []
    feed = []
    for event in active_events:
        if not isinstance(event, IntelligenceEvent):
            continue
        feed.append({
            "title": event.title,
            "severity": event.severity.name,
            "confidence": float(event.confidence or 0.0),
            "impacted_assets": _safe_list(event.affected_assets),
        })
    return feed


def build_upcoming_macro_events(calendar_provider: EconomicCalendarProvider | None = None, now: Any = None) -> list[dict[str, Any]]:
    try:
        provider = calendar_provider or EconomicCalendarProvider()
        return provider.get_week_events(now=now)
    except Exception:
        return []


def build_governance_status(governance_response: GovernanceResponse | None = None) -> dict[str, Any]:
    if not isinstance(governance_response, GovernanceResponse):
        return {
            "current_restrictions": [],
            "leverage_multiplier": 1.0,
            "freeze_status": "NONE",
        }

    restrictions = []
    if governance_response.freeze_new_positions:
        restrictions.append("freeze_new_positions")
    if governance_response.freeze_options:
        restrictions.append("freeze_options")
    if governance_response.suppress_scalping:
        restrictions.append("suppress_scalping")
    if governance_response.reduce_allocation_pct > 0:
        restrictions.append(f"reduce_allocation_pct:{governance_response.reduce_allocation_pct}")

    freeze_status = "FROZEN" if governance_response.freeze_new_positions or governance_response.freeze_options else "NONE"
    return {
        "current_restrictions": restrictions,
        "leverage_multiplier": float(governance_response.leverage_multiplier or 1.0),
        "freeze_status": freeze_status,
    }


def build_dashboard_widgets(state_manager: IntelligenceStateManager | None = None) -> dict[str, Any]:
    try:
        active_events = state_manager.get_active_events() if state_manager else []
        governance_response = state_manager.get_governance_response() if state_manager else None
        current_regime = state_manager.get_current_regime() if state_manager else RegimeState.NORMAL

        return {
            "global_risk_meter": build_global_risk_meter(active_events, current_regime),
            "active_event_feed": build_active_event_feed(active_events),
            "upcoming_macro_events": build_upcoming_macro_events(),
            "governance_status": build_governance_status(governance_response),
            "event_count": len(active_events),
            "dashboard_safe": True,
        }
    except Exception:
        return {
            "global_risk_meter": "NORMAL",
            "active_event_feed": [],
            "upcoming_macro_events": [],
            "governance_status": {
                "current_restrictions": [],
                "leverage_multiplier": 1.0,
                "freeze_status": "NONE",
            },
            "event_count": 0,
            "dashboard_safe": False,
        }
