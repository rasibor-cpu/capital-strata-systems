"""Phase 189 — broker-agnostic evidence packaging with redaction."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from backend.app.brokers.multi_broker_readiness.contracts import (
    FRAMEWORK_VERSION,
    SCHEMA_VERSION,
    AssetClass,
    BrokerCertificationEvidence,
)

_FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "private_key",
    "account_id",
    "accountid",
    "balance",
    "nav",
    "equity",
)


def redact_diagnostics(payload: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(frag in lowered for frag in _FORBIDDEN_FRAGMENTS):
            out[str(key)] = "[REDACTED]"
            continue
        if isinstance(value, Mapping):
            out[str(key)] = redact_diagnostics(value)
        else:
            out[str(key)] = value
    return out


def compute_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def build_broker_evidence(
    *,
    broker_type: str,
    asset_class: str = AssetClass.NONE.value,
    timestamp: str,
    certification_state: str,
    provider_fingerprint_hash: str,
    capability_profile: Mapping[str, Any],
    operational_readiness: Mapping[str, Any],
    remaining_blockers: Sequence[str],
    ttl_status: Mapping[str, Any],
    rc004_readiness: Mapping[str, Any],
    provider_versions: Mapping[str, str] | None = None,
    schema_versions: Mapping[str, str] | None = None,
    gate_results: Sequence[Mapping[str, Any]] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
    parent_certification_id: str = "",
    previous_evidence_hash: str = "",
    lineage_generation: int = 0,
) -> BrokerCertificationEvidence:
    body = {
        "schema_id": "BROKER_CERTIFICATION_EVIDENCE",
        "schema_version": SCHEMA_VERSION,
        "broker_type": broker_type,
        "asset_class": asset_class,
        "timestamp": timestamp,
        "certification_state": certification_state,
        "provider_fingerprint_hash": provider_fingerprint_hash,
        "capability_profile": redact_diagnostics(dict(capability_profile)),
        "operational_readiness": redact_diagnostics(dict(operational_readiness)),
        "remaining_blockers": list(remaining_blockers),
        "ttl_status": redact_diagnostics(dict(ttl_status)),
        "rc004_readiness": redact_diagnostics(dict(rc004_readiness)),
        "provider_versions": dict(provider_versions or {"framework": FRAMEWORK_VERSION}),
        "schema_versions": dict(schema_versions or {"contracts": SCHEMA_VERSION}),
        "gate_results": [dict(g) for g in (gate_results or ())],
        "parent_certification_id": parent_certification_id,
        "previous_evidence_hash": previous_evidence_hash,
        "lineage_generation": lineage_generation,
        "diagnostics": redact_diagnostics(dict(diagnostics or {})),
    }
    digest = compute_hash(body)
    return BrokerCertificationEvidence(
        broker_type=broker_type,
        asset_class=asset_class,
        timestamp=timestamp,
        certification_state=certification_state,
        provider_fingerprint_hash=provider_fingerprint_hash,
        capability_profile=body["capability_profile"],
        operational_readiness=body["operational_readiness"],
        remaining_blockers=tuple(remaining_blockers),
        ttl_status=body["ttl_status"],
        rc004_readiness=body["rc004_readiness"],
        provider_versions=body["provider_versions"],
        schema_versions=body["schema_versions"],
        gate_results=tuple(body["gate_results"]),
        parent_certification_id=parent_certification_id,
        previous_evidence_hash=previous_evidence_hash,
        current_evidence_hash=digest,
        lineage_generation=lineage_generation,
        evidence_hash=digest,
        diagnostics=body["diagnostics"],
    )
