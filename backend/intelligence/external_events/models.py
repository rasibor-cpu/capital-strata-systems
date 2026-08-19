"""Canonical MI-EXT-001 external event models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from backend.intelligence.external_events.constants import (
    ADVISORY_ONLY,
    EXECUTION_ALLOWED,
    PARSER_VERSION,
    SCHEMA_VERSION,
    TrustTier,
    UNAVAILABLE,
    UNKNOWN,
)


def _s(value: Any, default: str = UNKNOWN) -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else default


@dataclass(frozen=True)
class ExternalEvent:
    event_id: str
    source_id: str
    source_name: str
    source_tier: str
    source_url: str
    publisher: str
    jurisdiction: str
    published_at: str
    retrieved_at: str
    effective_at: str
    title: str
    normalized_summary: str
    event_category: str
    affected_instruments: tuple[str, ...]
    affected_asset_classes: tuple[str, ...]
    raw_content_hash: str
    normalized_content_hash: str
    parser_version: str = PARSER_VERSION
    schema_version: str = SCHEMA_VERSION
    confidence: float | None = None
    verification_status: str = UNKNOWN
    corroborating_source_ids: tuple[str, ...] = ()
    contradiction_status: str = "NONE"
    freshness_status: str = UNKNOWN
    licensing_usage_classification: str = UNKNOWN
    advisory_only: bool = ADVISORY_ONLY
    execution_allowed: bool = EXECUTION_ALLOWED
    primary_source_id: str | None = None
    conflicting_source_ids: tuple[str, ...] = ()
    duplicate_count: int = 1
    first_seen: str = UNAVAILABLE
    last_updated: str = UNAVAILABLE
    canonical_event_hash: str = UNAVAILABLE
    impact_direction: str = UNKNOWN
    impact_magnitude: str = UNKNOWN
    impact_horizon: str = UNKNOWN
    impact_evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()
    data_completeness: str = UNKNOWN

    def __post_init__(self) -> None:
        if self.confidence is not None and not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError("confidence must be in [0.0, 1.0] or None (UNKNOWN)")
        if self.execution_allowed:
            raise ValueError("MI-EXT-001 events must keep execution_allowed=false")
        if not self.advisory_only:
            raise ValueError("MI-EXT-001 events must keep advisory_only=true")
        if self.source_tier not in TrustTier.ORDER and self.source_tier != UNKNOWN:
            raise ValueError(f"unsupported source_tier: {self.source_tier}")

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["affected_instruments"] = list(self.affected_instruments)
        payload["affected_asset_classes"] = list(self.affected_asset_classes)
        payload["corroborating_source_ids"] = list(self.corroborating_source_ids)
        payload["conflicting_source_ids"] = list(self.conflicting_source_ids)
        payload["impact_evidence"] = list(self.impact_evidence)
        payload["counter_evidence"] = list(self.counter_evidence)
        if self.confidence is None:
            payload["confidence"] = UNKNOWN
        return payload

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ExternalEvent":
        def tup(key: str) -> tuple[str, ...]:
            raw = payload.get(key, ())
            if raw in (None, UNKNOWN, UNAVAILABLE):
                return ()
            if isinstance(raw, str):
                return (raw,) if raw.strip() else ()
            return tuple(str(x) for x in raw if str(x).strip())

        confidence = payload.get("confidence", None)
        if confidence in (None, UNKNOWN, UNAVAILABLE, ""):
            conf: float | None = None
        else:
            conf = float(confidence)

        return cls(
            event_id=_s(payload.get("event_id")),
            source_id=_s(payload.get("source_id")),
            source_name=_s(payload.get("source_name")),
            source_tier=_s(payload.get("source_tier")),
            source_url=_s(payload.get("source_url"), UNAVAILABLE),
            publisher=_s(payload.get("publisher")),
            jurisdiction=_s(payload.get("jurisdiction")),
            published_at=_s(payload.get("published_at"), UNAVAILABLE),
            retrieved_at=_s(payload.get("retrieved_at"), UNAVAILABLE),
            effective_at=_s(payload.get("effective_at"), UNAVAILABLE),
            title=_s(payload.get("title")),
            normalized_summary=_s(payload.get("normalized_summary"), UNAVAILABLE),
            event_category=_s(payload.get("event_category"), "unknown"),
            affected_instruments=tup("affected_instruments"),
            affected_asset_classes=tup("affected_asset_classes"),
            raw_content_hash=_s(payload.get("raw_content_hash"), UNAVAILABLE),
            normalized_content_hash=_s(payload.get("normalized_content_hash"), UNAVAILABLE),
            parser_version=_s(payload.get("parser_version"), PARSER_VERSION),
            schema_version=_s(payload.get("schema_version"), SCHEMA_VERSION),
            confidence=conf,
            verification_status=_s(payload.get("verification_status")),
            corroborating_source_ids=tup("corroborating_source_ids"),
            contradiction_status=_s(payload.get("contradiction_status"), "NONE"),
            freshness_status=_s(payload.get("freshness_status")),
            licensing_usage_classification=_s(payload.get("licensing_usage_classification")),
            advisory_only=bool(payload.get("advisory_only", ADVISORY_ONLY)),
            execution_allowed=bool(payload.get("execution_allowed", EXECUTION_ALLOWED)),
            primary_source_id=(None if payload.get("primary_source_id") in (None, "", UNKNOWN) else str(payload.get("primary_source_id"))),
            conflicting_source_ids=tup("conflicting_source_ids"),
            duplicate_count=int(payload.get("duplicate_count", 1) or 1),
            first_seen=_s(payload.get("first_seen"), UNAVAILABLE),
            last_updated=_s(payload.get("last_updated"), UNAVAILABLE),
            canonical_event_hash=_s(payload.get("canonical_event_hash"), UNAVAILABLE),
            impact_direction=_s(payload.get("impact_direction")),
            impact_magnitude=_s(payload.get("impact_magnitude")),
            impact_horizon=_s(payload.get("impact_horizon")),
            impact_evidence=tup("impact_evidence"),
            counter_evidence=tup("counter_evidence"),
            data_completeness=_s(payload.get("data_completeness")),
        )


@dataclass
class SourceHealth:
    source_id: str
    enabled: bool
    last_successful_retrieval: str = UNAVAILABLE
    last_attempted_retrieval: str = UNAVAILABLE
    freshness: str = UNKNOWN
    latency_ms: float | None = None
    failure_count: int = 0
    consecutive_failures: int = 0
    rate_limit_state: str = "CLEAR"
    parser_version: str = PARSER_VERSION
    last_event_count: int = 0
    last_error_redacted: str = UNAVAILABLE
    trust_tier: str = UNKNOWN
    operational_status: str = "UNKNOWN"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
