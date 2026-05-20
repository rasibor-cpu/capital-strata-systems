from __future__ import annotations

from typing import Any

from .event_models import IntelligenceEvent


class IntelligenceEventRouter:
    def __init__(
        self,
        persistence_engine: Any | None = None,
        lifecycle_manager: Any | None = None,
        health_monitor: Any | None = None,
    ) -> None:
        self.persistence_engine = persistence_engine
        self.lifecycle_manager = lifecycle_manager
        self.health_monitor = health_monitor

    def route_classified_event(
        self,
        event: IntelligenceEvent | None,
        state_manager: Any | None = None,
        persist: bool = True,
    ) -> IntelligenceEvent | None:
        if event is None:
            return None
        if state_manager is not None and hasattr(state_manager, "add_event"):
            state_manager.add_event(event)
        if persist and self.persistence_engine is not None and hasattr(self.persistence_engine, "save_event"):
            self.persistence_engine.save_event(event)
        return event

    def route_dashboard_payload(self, state_manager: Any, widget_builder: Any | None = None) -> dict[str, Any]:
        try:
            if widget_builder is None and hasattr(state_manager, "get_active_events"):
                from .dashboard_intelligence_widgets import build_dashboard_widgets

                widget_builder = build_dashboard_widgets
            if widget_builder is not None:
                return widget_builder(state_manager)
        except Exception:
            pass
        return {
            "global_risk_meter": "NORMAL",
            "active_event_feed": [],
            "upcoming_macro_events": [],
            "governance_status": {"current_restrictions": [], "leverage_multiplier": 1.0, "freeze_status": "NONE"},
            "event_count": 0,
            "dashboard_safe": False,
        }

    def route_persistence_action(self, event: IntelligenceEvent | None = None, archive_expired: bool = False) -> bool:
        if self.persistence_engine is None:
            return False
        if event is not None and hasattr(self.persistence_engine, "save_event"):
            self.persistence_engine.save_event(event)
        if archive_expired and hasattr(self.persistence_engine, "archive_expired_events"):
            self.persistence_engine.archive_expired_events()
        return True

    def route_health_snapshot(self, events: list[IntelligenceEvent] | None = None, ingestion_errors: int = 0) -> dict[str, Any]:
        if self.health_monitor is None or not hasattr(self.health_monitor, "get_health_snapshot"):
            return {"status": "UNKNOWN", "issues": []}
        return self.health_monitor.get_health_snapshot(events, ingestion_errors)
