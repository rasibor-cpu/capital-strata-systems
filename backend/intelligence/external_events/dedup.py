"""Deterministic deduplication and corroboration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Iterable

from backend.intelligence.external_events.catalogue import SourceCatalogue
from backend.intelligence.external_events.constants import TrustTier, UNAVAILABLE
from backend.intelligence.external_events.hashing import canonical_json_hash, normalize_title, semantic_fingerprint
from backend.intelligence.external_events.models import ExternalEvent


def _published_window_key(published_at: str) -> str:
    text = str(published_at or "")
    return text[:13] if len(text) >= 13 else text[:10]


def event_cluster_key(event: ExternalEvent) -> str:
    return semantic_fingerprint(
        title=event.title,
        category=event.event_category,
        instruments=event.affected_instruments,
        published_at=_published_window_key(event.published_at),
    )


def merge_cluster(events: Iterable[ExternalEvent], catalogue: SourceCatalogue | None = None) -> ExternalEvent:
    del catalogue  # reserved for future catalogue-backed tier lookups
    rows = list(events)
    if not rows:
        raise ValueError("cannot merge empty cluster")

    # Primary = highest tier (lowest rank), then earliest published, then source_id
    def sort_key(ev: ExternalEvent) -> tuple:
        return (TrustTier.rank(ev.source_tier), ev.published_at or "", ev.source_id)

    ordered = sorted(rows, key=sort_key)
    primary = ordered[0]
    others = ordered[1:]

    # Append-preserving source history (sorted unique; never overwrites prior IDs)
    source_history = tuple(sorted({ev.source_id for ev in ordered}))
    corroborating = tuple(sorted({ev.source_id for ev in others}))
    conflicting: list[str] = []
    counter_evidence: list[str] = []
    unresolved_tier1 = False

    primary_dir = _direction_hint(primary)
    for ev in others:
        other_dir = _direction_hint(ev)
        if primary_dir == "unknown" or other_dir == "unknown" or primary_dir == other_dir:
            continue
        # Directional contradiction present
        if (
            ev.source_tier == TrustTier.TIER_1_OFFICIAL_PRIMARY
            and primary.source_tier == TrustTier.TIER_1_OFFICIAL_PRIMARY
        ):
            # Same-tier Tier-1 conflict: do not silently resolve
            unresolved_tier1 = True
            conflicting.append(ev.source_id)
            counter_evidence.append(f"unresolved_tier1_conflict:{ev.source_id}")
        elif TrustTier.rank(ev.source_tier) > TrustTier.rank(primary.source_tier):
            # Lower tier cannot override; record as conflict + counter-evidence
            conflicting.append(ev.source_id)
            counter_evidence.append(f"lower_tier_contradiction:{ev.source_id}")
        else:
            conflicting.append(ev.source_id)
            counter_evidence.append(f"same_or_higher_contradiction:{ev.source_id}")

    first_seen = min(
        (ev.first_seen if ev.first_seen != UNAVAILABLE else ev.retrieved_at for ev in ordered),
        default=UNAVAILABLE,
    )
    last_updated = max(
        (ev.last_updated if ev.last_updated != UNAVAILABLE else ev.retrieved_at for ev in ordered),
        default=UNAVAILABLE,
    )
    instruments = tuple(sorted({i for ev in ordered for i in ev.affected_instruments}))
    asset_classes = tuple(sorted({a for ev in ordered for a in ev.affected_asset_classes}))

    # Canonical hash is merge-order independent: sorted sources + primary chosen by sort_key
    canonical = canonical_json_hash(
        {
            "primary": primary.source_id,
            "title": normalize_title(primary.title),
            "category": primary.event_category,
            "instruments": list(instruments),
            "published_window": _published_window_key(primary.published_at),
            "sources": list(source_history),
            "contradiction": (
                "UNRESOLVED_TIER1_CONFLICT"
                if unresolved_tier1
                else ("CONFLICT" if conflicting else "NONE")
            ),
        }
    )

    if unresolved_tier1:
        contradiction_status = "UNRESOLVED_TIER1_CONFLICT"
        verification_status = "UNRESOLVED"
    elif conflicting:
        contradiction_status = "CONFLICT"
        verification_status = "CORROBORATED_WITH_CONFLICT" if corroborating else primary.verification_status
    elif corroborating:
        contradiction_status = "NONE"
        verification_status = "CORROBORATED"
    else:
        contradiction_status = "NONE"
        verification_status = primary.verification_status

    existing_counter = tuple(primary.counter_evidence) + tuple(sorted(set(counter_evidence)))

    return replace(
        primary,
        affected_instruments=instruments,
        affected_asset_classes=asset_classes,
        corroborating_source_ids=corroborating,
        conflicting_source_ids=tuple(sorted(set(conflicting))),
        contradiction_status=contradiction_status,
        duplicate_count=len(ordered),
        primary_source_id=primary.source_id,
        first_seen=first_seen,
        last_updated=last_updated,
        canonical_event_hash=canonical,
        verification_status=verification_status,
        counter_evidence=existing_counter,
        # Preserve every source reference in impact_evidence trail (append-preserving)
        impact_evidence=tuple(
            sorted(
                set(primary.impact_evidence)
                | {f"source_history:{sid}" for sid in source_history}
            )
        ),
    )


def deduplicate_events(events: Iterable[ExternalEvent], catalogue: SourceCatalogue) -> list[ExternalEvent]:
    clusters: dict[str, list[ExternalEvent]] = {}
    for ev in events:
        clusters.setdefault(event_cluster_key(ev), []).append(ev)
    merged = [merge_cluster(group, catalogue) for group in clusters.values()]
    return sorted(merged, key=lambda e: (e.published_at, e.source_id, e.event_id))


def lower_tier_cannot_override(primary: ExternalEvent, challenger: ExternalEvent) -> ExternalEvent:
    """Return the event that should govern when tiers conflict."""
    if TrustTier.rank(challenger.source_tier) < TrustTier.rank(primary.source_tier):
        return challenger
    return primary


def _direction_hint(event: ExternalEvent) -> str:
    text = f"{event.title} {event.normalized_summary}".casefold()
    if "hawkish" in text or "tightening" in text or "negative" in text or "ban" in text:
        return "negative"
    if "dovish" in text or "easing" in text or "positive" in text or "approval" in text:
        return "positive"
    return "unknown"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
