"""External event pipeline — fail-closed, never enables execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from backend.intelligence.external_events.adapter import AdapterResult, ExternalSourceAdapter
from backend.intelligence.external_events.catalogue import SourceCatalogue
from backend.intelligence.external_events.constants import ADVISORY_ONLY, EXECUTION_ALLOWED
from backend.intelligence.external_events.dedup import deduplicate_events, lower_tier_cannot_override
from backend.intelligence.external_events.freshness import is_actionable_freshness
from backend.intelligence.external_events.impact import assess_impact
from backend.intelligence.external_events.models import ExternalEvent, SourceHealth


@dataclass
class PipelineResult:
    events: list[ExternalEvent] = field(default_factory=list)
    actionable_events: list[ExternalEvent] = field(default_factory=list)
    health: list[SourceHealth] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    advisory_only: bool = ADVISORY_ONLY
    execution_allowed: bool = EXECUTION_ALLOWED


class ExternalEventPipeline:
    def __init__(self, catalogue: SourceCatalogue, adapters: Iterable[ExternalSourceAdapter]):
        self.catalogue = catalogue
        self.adapters = list(adapters)

    def run(self, *, now_utc_iso: str | None = None) -> PipelineResult:
        result = PipelineResult()
        collected: list[ExternalEvent] = []
        for adapter in self.adapters:
            try:
                adapter_result: AdapterResult = adapter.run(now_utc_iso=now_utc_iso)
            except Exception as exc:  # noqa: BLE001 — never crash caller
                result.errors.append({"code": "adapter_crash_contained", "message": str(exc)[:300]})
                continue
            collected.extend(adapter_result.events)
            if adapter_result.health is not None:
                result.health.append(adapter_result.health)
            result.errors.extend(adapter_result.errors)

        try:
            merged = deduplicate_events(collected, self.catalogue)
        except Exception as exc:  # noqa: BLE001
            result.errors.append({"code": "dedup_failed", "message": str(exc)[:300]})
            merged = []

        assessed: list[ExternalEvent] = []
        for event in merged:
            try:
                assessed.append(assess_impact(event))
            except Exception as exc:  # noqa: BLE001
                result.errors.append({"code": "impact_failed", "message": str(exc)[:300]})

        # Enforce tier dominance for identical titles after merge
        by_title: dict[str, ExternalEvent] = {}
        for event in assessed:
            key = event.title.casefold()
            if key not in by_title:
                by_title[key] = event
            else:
                by_title[key] = lower_tier_cannot_override(by_title[key], event)

        final_events = list(by_title.values())
        for event in final_events:
            if event.execution_allowed or not event.advisory_only:
                result.errors.append({"code": "execution_authority_blocked", "message": event.event_id})
        final_events = [e for e in final_events if (not e.execution_allowed and e.advisory_only)]

        result.events = sorted(final_events, key=lambda e: (e.published_at, e.event_id))
        result.actionable_events = [e for e in result.events if is_actionable_freshness(e.freshness_status)]
        result.execution_allowed = False
        result.advisory_only = True
        return result
