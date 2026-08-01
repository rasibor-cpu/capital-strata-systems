"""Decision-layer integration design for MI-EXT-001 (advisory only).

This module documents how verified external events feed existing CSS decision
surfaces without granting execution authority. DIP / Trade DNA / Edge
Intelligence live on maintenance and are design targets after MR-001 merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.intelligence.external_events.constants import ADVISORY_ONLY, EXECUTION_ALLOWED
from backend.intelligence.external_events.freshness import is_actionable_freshness
from backend.intelligence.external_events.models import ExternalEvent


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
    # UNKNOWN freshness fails closed from current influence (same as STALE/EXPIRED)
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
    """Future advisory learning inputs after DIP/Trade DNA land via MR-001."""
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
            "trade_dna",
            "decision_analytics",
            "edge_intelligence",
            "enterprise_intelligence",
        ],
        "status_on_this_branch": "ABSENT_UNTIL_MR_001",
        "auto_allocation_authority": False,
        "advisory_only": True,
        "execution_allowed": False,
    }
