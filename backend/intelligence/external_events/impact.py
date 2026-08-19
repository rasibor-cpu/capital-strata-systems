"""Advisory-only market impact assessment."""

from __future__ import annotations

from dataclasses import replace

from backend.intelligence.external_events.constants import UNKNOWN
from backend.intelligence.external_events.freshness import is_actionable_freshness
from backend.intelligence.external_events.models import ExternalEvent


_CATEGORY_DEFAULTS: dict[str, dict[str, str]] = {
    "monetary_policy": {"direction": "mixed", "magnitude": "high", "horizon": "medium"},
    "interest_rates": {"direction": "mixed", "magnitude": "high", "horizon": "medium"},
    "inflation": {"direction": "mixed", "magnitude": "medium", "horizon": "medium"},
    "employment": {"direction": "mixed", "magnitude": "medium", "horizon": "short"},
    "regulatory_action": {"direction": "negative", "magnitude": "medium", "horizon": "medium"},
    "crypto_regulation": {"direction": "mixed", "magnitude": "medium", "horizon": "medium"},
    "exchange_outage": {"direction": "negative", "magnitude": "high", "horizon": "short"},
    "broker_outage": {"direction": "negative", "magnitude": "medium", "horizon": "short"},
    "issuer_earnings": {"direction": "mixed", "magnitude": "medium", "horizon": "short"},
    "market_disruption": {"direction": "negative", "magnitude": "high", "horizon": "short"},
}


def assess_impact(event: ExternalEvent) -> ExternalEvent:
    if not is_actionable_freshness(event.freshness_status):
        return replace(
            event,
            impact_direction=UNKNOWN,
            impact_magnitude=UNKNOWN,
            impact_horizon=UNKNOWN,
            impact_evidence=("stale_or_non_actionable_freshness",),
            counter_evidence=(),
            data_completeness=_completeness(event),
            confidence=None if event.confidence is None else min(event.confidence, 0.25),
        )

    defaults = _CATEGORY_DEFAULTS.get(event.event_category, {"direction": UNKNOWN, "magnitude": UNKNOWN, "horizon": UNKNOWN})
    evidence: list[str] = []
    if event.affected_instruments:
        evidence.append("instruments_present")
    else:
        evidence.append("instruments_unavailable")
    if event.verification_status in {"VERIFIED", "CORROBORATED"}:
        evidence.append(f"verification:{event.verification_status.casefold()}")
    if event.contradiction_status in {"CONFLICT", "UNRESOLVED_TIER1_CONFLICT"}:
        return replace(
            event,
            impact_direction="mixed" if event.contradiction_status == "CONFLICT" else UNKNOWN,
            impact_magnitude=defaults["magnitude"] if event.contradiction_status == "CONFLICT" else UNKNOWN,
            impact_horizon=defaults["horizon"] if event.contradiction_status == "CONFLICT" else UNKNOWN,
            impact_evidence=tuple(evidence),
            counter_evidence=tuple(event.counter_evidence) + (
                ("source_conflict_present",)
                if event.contradiction_status == "CONFLICT"
                else ("unresolved_tier1_conflict",)
            ),
            data_completeness=_completeness(event),
            confidence=None if event.confidence is None else min(event.confidence, 0.4),
        )

    return replace(
        event,
        impact_direction=defaults["direction"],
        impact_magnitude=defaults["magnitude"],
        impact_horizon=defaults["horizon"],
        impact_evidence=tuple(evidence) or ("category_default_only",),
        counter_evidence=(),
        data_completeness=_completeness(event),
    )


def _completeness(event: ExternalEvent) -> str:
    required = [
        event.title not in {"", "UNKNOWN"},
        event.published_at not in {"", "UNKNOWN", "UNAVAILABLE"},
        event.source_id not in {"", "UNKNOWN"},
        bool(event.raw_content_hash not in {"", "UNKNOWN", "UNAVAILABLE"}),
    ]
    score = sum(1 for ok in required if ok)
    if score == len(required) and event.affected_instruments:
        return "COMPLETE"
    if score >= 3:
        return "PARTIAL"
    return "INCOMPLETE"
