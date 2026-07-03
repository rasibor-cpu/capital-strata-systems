from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from .event_models import GovernanceResponse, IntelligenceEvent, RegimeState
from .governance_response_engine import build_governance_response
from .regime_mutation_engine import determine_regime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IntelligenceStateManager:
    def __init__(self) -> None:
        self._events: List[IntelligenceEvent] = []

    def add_event(self, event: IntelligenceEvent) -> None:
        if not isinstance(event, IntelligenceEvent):
            return
        self._events.append(event)

    def expire_events(self, now: datetime | None = None) -> None:
        now = now or _utc_now()
        for event in self._events:
            if event.expiration_time is not None and event.expiration_time <= now:
                event.active = False
        self._events = [event for event in self._events if event.active]

    def get_active_events(self) -> List[IntelligenceEvent]:
        return [event for event in self._events if event.active]

    def get_current_regime(self) -> RegimeState:
        return determine_regime(self.get_active_events())

    def get_governance_response(self) -> GovernanceResponse:
        regime = self.get_current_regime()
        return build_governance_response(regime)

    def snapshot(self) -> dict:
        active_events = self.get_active_events()
        regime = self.get_current_regime()
        response = self.get_governance_response()
        return {
            "current_regime": regime.value,
            "governance_response": {
                "reduce_allocation_pct": response.reduce_allocation_pct,
                "freeze_new_positions": response.freeze_new_positions,
                "freeze_options": response.freeze_options,
                "suppress_scalping": response.suppress_scalping,
                "max_open_positions": response.max_open_positions,
                "leverage_multiplier": response.leverage_multiplier,
                "notes": list(response.notes),
            },
            "active_events": [
                {
                    "event_id": event.event_id,
                    "title": event.title,
                    "category": event.category.value,
                    "severity": event.severity.value,
                    "confidence": event.confidence,
                    "source": event.source,
                    "affected_assets": list(event.affected_assets),
                    "description": event.description,
                    "expiration_time": event.expiration_time.isoformat() if event.expiration_time else None,
                }
                for event in active_events
            ],
            "event_count": len(active_events),
        }
