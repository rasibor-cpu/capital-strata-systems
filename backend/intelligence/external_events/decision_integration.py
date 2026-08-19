"""Advisory-only MI-EXT integration for current TAI/ranking architecture.

Historical DIP / Trade DNA decision-integration language is not copied into
execution. External events contribute diagnostics and advisory context only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from backend.intelligence.external_events.constants import (
    ADVISORY_ONLY,
    EXECUTION_ALLOWED,
    UNKNOWN,
    UNAVAILABLE,
    TrustTier,
)
from backend.intelligence.external_events.freshness import is_actionable_freshness, parse_utc
from backend.intelligence.external_events.models import ExternalEvent

EXTERNAL_EVENT_INTELLIGENCE_SCHEMA = "css.mi_ext_001.external_event_intelligence.v1"


@dataclass(frozen=True)
class AdvisoryContextPatch:
    """Soft context patch for decision consumers — never an order authority."""

    market_context_notes: tuple[str, ...]
    event_risk_warnings: tuple[str, ...]
    instrument_watchlist: tuple[str, ...]
    research_opportunities: tuple[str, ...]
    regime_hints: tuple[str, ...]
    confidence_adjustment_hint: str
    advisory_only: bool = ADVISORY_ONLY
    execution_allowed: bool = EXECUTION_ALLOWED
    may_bypass_execution_gate: bool = False
    may_modify_risk_governor: bool = False
    may_modify_anti_bleed: bool = False
    may_change_position_size: bool = False
    may_change_live_authority: bool = False
    may_submit_orders: bool = False


def build_advisory_context(events: list[ExternalEvent]) -> AdvisoryContextPatch:
    # UNKNOWN/FUTURE/STALE freshness fails closed from current influence
    actionable = [
        e
        for e in events
        if is_actionable_freshness(e.freshness_status)
        and e.freshness_status.upper() in {"FRESH", "AGING"}
    ]
    notes = tuple(f"{e.source_tier}:{e.event_category}:{e.title}" for e in actionable[:20])
    warnings = tuple(
        e.title
        for e in actionable
        if e.event_category
        in {"regulatory_action", "market_disruption", "exchange_outage", "sanctions_geopolitics"}
    )
    instruments = tuple(sorted({i for e in actionable for i in e.affected_instruments}))
    research = tuple(
        e.title for e in actionable if e.event_category in {"issuer_earnings", "monetary_policy", "inflation"}
    )
    regime = tuple(
        f"{e.event_category}:{e.impact_direction}"
        for e in actionable
        if e.impact_direction not in {"UNKNOWN", "unknown"}
    )
    conf_hint = (
        "reduce_on_conflict"
        if any(e.contradiction_status in {"CONFLICT", "UNRESOLVED_TIER1_CONFLICT"} for e in actionable)
        else "neutral"
    )
    patch = AdvisoryContextPatch(
        market_context_notes=notes,
        event_risk_warnings=warnings,
        instrument_watchlist=instruments,
        research_opportunities=research,
        regime_hints=regime,
        confidence_adjustment_hint=conf_hint,
    )
    forbidden = {
        "capital",
        "position_size",
        "order",
        "authority",
        "sizing",
        "notional",
        "allocation_pct",
    }
    payload = patch.__dict__
    for key in payload:
        if any(token in key.casefold() for token in forbidden):
            # Structural guard: AdvisoryContextPatch must not grow mutation fields
            if key not in {
                "may_change_position_size",
                "may_change_live_authority",
                "may_submit_orders",
                "may_bypass_execution_gate",
                "may_modify_risk_governor",
                "may_modify_anti_bleed",
            }:
                raise RuntimeError(f"forbidden advisory field: {key}")
            if bool(payload[key]) is not False:
                raise RuntimeError(f"advisory mutation flag must be false: {key}")
    return patch


def profit_attribution_learning_contract() -> dict[str, Any]:
    """Advisory learning contract for current TAI/ranking consumers."""
    return {
        "inputs": [
            "markets",
            "strategies",
            "regimes",
            "events",
            "instruments",
            "sessions",
            "entry_conditions",
            "exit_conditions",
        ],
        "architecture_targets": [
            "technical_intelligence",
            "autonomous_opportunity_intelligence",
            "opportunity_ranking",
            "mission_control_observability",
        ],
        "status_on_this_branch": "ADVISORY_OVERLAY_ONLY",
        "auto_allocation_authority": False,
        "advisory_only": True,
        "execution_allowed": False,
    }


def empty_external_event_intelligence(*reasons: str) -> dict[str, Any]:
    return _overlay(
        score=0.0,
        confidence=0.0,
        freshness="UNKNOWN",
        categories=(),
        provenance_count=0,
        conflict_state="NONE",
        reasons=reasons or ("empty_event_set",),
        lookahead_excluded=0,
        duplicate_count=0,
    )


def build_external_event_intelligence(
    events: Sequence[ExternalEvent] | None,
    *,
    instrument: str = "",
    evaluation_time: datetime | None = None,
) -> dict[str, Any]:
    """Build additive advisory diagnostics for TAI/ranking. Never grants execution."""

    if not events:
        return empty_external_event_intelligence("empty_event_set")

    eval_at = evaluation_time or datetime.now(timezone.utc)
    if eval_at.tzinfo is None:
        eval_at = eval_at.replace(tzinfo=timezone.utc)
    eval_at = eval_at.astimezone(timezone.utc)
    symbol = _normalize_symbol(instrument)

    considered: list[ExternalEvent] = []
    lookahead_excluded = 0
    reasons: list[str] = []
    for event in events:
        if event.execution_allowed or not event.advisory_only:
            reasons.append("execution_authority_blocked")
            continue
        published = parse_utc(event.published_at)
        if published is not None and published > eval_at:
            lookahead_excluded += 1
            reasons.append("anti_lookahead_excluded")
            continue
        if event.source_tier == TrustTier.TIER_4_UNVERIFIED_SOCIAL:
            reasons.append("low_confidence_source_excluded")
            continue
        if symbol and event.affected_instruments and not _instrument_match(symbol, event.affected_instruments):
            continue
        considered.append(event)

    if not considered:
        if lookahead_excluded:
            return _overlay(
                score=0.0,
                confidence=0.0,
                freshness="FUTURE",
                categories=(),
                provenance_count=0,
                conflict_state="NONE",
                reasons=tuple(sorted(set(reasons))) or ("anti_lookahead_excluded",),
                lookahead_excluded=lookahead_excluded,
                duplicate_count=0,
            )
        return empty_external_event_intelligence(*(reasons or ("empty_event_set",)))

    actionable = [e for e in considered if is_actionable_freshness(e.freshness_status)]
    conflict_state = "NONE"
    if any(e.contradiction_status == "UNRESOLVED_TIER1_CONFLICT" for e in considered):
        conflict_state = "UNRESOLVED_TIER1_CONFLICT"
    elif any(e.contradiction_status == "CONFLICT" for e in considered):
        conflict_state = "CONFLICT"

    freshness = _aggregate_freshness(considered)
    categories = tuple(sorted({e.event_category for e in considered if e.event_category}))
    provenance_count = len({e.source_id for e in considered if e.source_id})
    duplicate_count = max((int(e.duplicate_count or 1) for e in considered), default=1)

    if conflict_state != "NONE":
        reasons.append("source_conflict_fail_closed")
        score = 0.0
        confidence = 0.0
    elif not actionable:
        reasons.append("non_actionable_freshness")
        score = 0.0
        confidence = 0.0
    else:
        # Conviction is the max of explicit confidences — never a sum, never amplified by duplicates.
        confidences = [float(e.confidence) for e in actionable if e.confidence is not None]
        confidence = max(confidences) if confidences else 0.0
        score = confidence
        reasons.append("actionable_advisory_evidence")

    return _overlay(
        score=score,
        confidence=confidence,
        freshness=freshness,
        categories=categories,
        provenance_count=provenance_count,
        conflict_state=conflict_state,
        reasons=tuple(sorted(set(reasons))),
        lookahead_excluded=lookahead_excluded,
        duplicate_count=duplicate_count,
    )


def coerce_external_events(raw: Any) -> list[ExternalEvent]:
    """Fail-closed conversion of mappings/events. Malformed rows are dropped."""

    if raw in (None, "", (), []):
        return []
    if isinstance(raw, ExternalEvent):
        return [raw] if _event_is_attributed(raw) else []
    if isinstance(raw, Mapping):
        try:
            parsed = ExternalEvent.from_mapping(dict(raw))
        except Exception:
            return []
        return [parsed] if _event_is_attributed(parsed) else []
    if isinstance(raw, Iterable):
        events: list[ExternalEvent] = []
        for item in raw:
            if isinstance(item, ExternalEvent):
                if _event_is_attributed(item):
                    events.append(item)
                continue
            if isinstance(item, Mapping):
                try:
                    parsed = ExternalEvent.from_mapping(dict(item))
                except Exception:
                    continue
                if _event_is_attributed(parsed):
                    events.append(parsed)
        return events
    return []


def _event_is_attributed(event: ExternalEvent) -> bool:
    if event.source_id in {"", UNKNOWN, UNAVAILABLE}:
        return False
    if event.title in {"", UNKNOWN}:
        return False
    if event.raw_content_hash in {"", UNKNOWN, UNAVAILABLE}:
        return False
    return True


def _overlay(
    *,
    score: float,
    confidence: float,
    freshness: str,
    categories: tuple[str, ...],
    provenance_count: int,
    conflict_state: str,
    reasons: tuple[str, ...],
    lookahead_excluded: int,
    duplicate_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": EXTERNAL_EVENT_INTELLIGENCE_SCHEMA,
        "external_event_score": round(float(score), 8),
        "event_confidence": round(float(confidence), 8),
        "event_freshness": freshness or UNKNOWN,
        "event_categories": list(categories),
        "event_provenance_count": int(provenance_count),
        "event_conflict_state": conflict_state,
        "event_reasons": list(reasons),
        "event_lookahead_excluded_count": int(lookahead_excluded),
        "event_duplicate_count": int(duplicate_count),
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "live_network_ingestion": False,
        "direct_execution_influence": False,
    }


def _aggregate_freshness(events: Sequence[ExternalEvent]) -> str:
    states = {str(e.freshness_status or UNKNOWN).upper() for e in events}
    for state in ("FUTURE", "UNKNOWN", "EXPIRED", "STALE", "AGING", "FRESH"):
        if state in states:
            return state
    return UNKNOWN


def _normalize_symbol(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip().upper() if ch.isalnum())


def _instrument_match(symbol: str, instruments: Sequence[str]) -> bool:
    wanted = _normalize_symbol(symbol)
    if not wanted:
        return True
    for item in instruments:
        candidate = _normalize_symbol(item)
        if not candidate:
            continue
        if candidate == wanted or candidate in wanted or wanted in candidate:
            return True
    return False
