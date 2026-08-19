"""Phase 187A / 187A-R1 — immutable read-only certification evidence (no secrets)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from backend.app.market.oanda_readonly_certification.contracts import (
    FRAMEWORK_VERSION,
    PROVIDER_NAME,
    PROVIDER_VERSION,
    SCHEMA_VERSION,
)

_FORBIDDEN_SECRET_FRAGMENTS: tuple[str, ...] = (
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "private_key",
    "account_balance",
    "balance",
    "nav",
    "equity",
)


def redact_diagnostics(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Drop any key whose name suggests secrets or balances."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).lower()
        if any(frag in lowered for frag in _FORBIDDEN_SECRET_FRAGMENTS):
            out[str(key)] = "[REDACTED]"
            continue
        if isinstance(value, Mapping):
            out[str(key)] = redact_diagnostics(value)
        elif isinstance(value, str) and len(value) > 64 and any(
            frag in lowered for frag in ("auth", "header", "key")
        ):
            out[str(key)] = "[REDACTED]"
        else:
            out[str(key)] = value
    return out


@dataclass(frozen=True)
class OandaReadOnlyEvidencePackage:
    schema_id: str = "OANDA_READONLY_EVIDENCE"
    schema_version: str = SCHEMA_VERSION
    framework_version: str = FRAMEWORK_VERSION
    provider_name: str = PROVIDER_NAME
    provider_version: str = PROVIDER_VERSION
    timestamp: str = ""
    certification_state: str = "NOT_STARTED"
    connection_diagnostics: Mapping[str, Any] = field(default_factory=dict)
    provider_versions: Mapping[str, str] = field(default_factory=dict)
    schema_versions: Mapping[str, str] = field(default_factory=dict)
    latency_ms: Mapping[str, float] = field(default_factory=dict)
    endpoint: str = ""
    certificate_info: Mapping[str, Any] = field(default_factory=dict)
    account_scope: Mapping[str, Any] = field(default_factory=dict)
    market_data_quality: Mapping[str, Any] = field(default_factory=dict)
    gate_results: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    evidence_hash: str = ""
    # 187A-R1 lineage (immutable once built)
    parent_certification_id: str = ""
    previous_evidence_hash: str = ""
    current_evidence_hash: str = ""
    lineage_generation: int = 0
    provider_fingerprint_hash: str = ""
    certification_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def compute_evidence_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def build_evidence_package(
    *,
    timestamp: str,
    certification_state: str,
    connection_diagnostics: Mapping[str, Any] | None = None,
    provider_versions: Mapping[str, str] | None = None,
    schema_versions: Mapping[str, str] | None = None,
    latency_ms: Mapping[str, float] | None = None,
    endpoint: str = "",
    certificate_info: Mapping[str, Any] | None = None,
    account_scope: Mapping[str, Any] | None = None,
    market_data_quality: Mapping[str, Any] | None = None,
    gate_results: Sequence[Mapping[str, Any]] | None = None,
    parent_certification_id: str = "",
    previous_evidence_hash: str = "",
    lineage_generation: int = 0,
    provider_fingerprint_hash: str = "",
    certification_id: str = "",
) -> OandaReadOnlyEvidencePackage:
    conn = redact_diagnostics(dict(connection_diagnostics or {}))
    cert = redact_diagnostics(dict(certificate_info or {}))
    scope = redact_diagnostics(dict(account_scope or {}))
    quality = redact_diagnostics(dict(market_data_quality or {}))
    gates = tuple(dict(g) for g in (gate_results or ()))

    body = {
        "schema_id": "OANDA_READONLY_EVIDENCE",
        "schema_version": SCHEMA_VERSION,
        "framework_version": FRAMEWORK_VERSION,
        "provider_name": PROVIDER_NAME,
        "provider_version": PROVIDER_VERSION,
        "timestamp": timestamp,
        "certification_state": certification_state,
        "connection_diagnostics": conn,
        "provider_versions": dict(provider_versions or {}),
        "schema_versions": dict(schema_versions or {}),
        "latency_ms": dict(latency_ms or {}),
        "endpoint": endpoint,
        "certificate_info": cert,
        "account_scope": scope,
        "market_data_quality": quality,
        "gate_results": list(gates),
        "parent_certification_id": parent_certification_id,
        "previous_evidence_hash": previous_evidence_hash,
        "lineage_generation": lineage_generation,
        "provider_fingerprint_hash": provider_fingerprint_hash,
        "certification_id": certification_id,
    }
    digest = compute_evidence_hash(body)
    return OandaReadOnlyEvidencePackage(
        timestamp=timestamp,
        certification_state=certification_state,
        connection_diagnostics=conn,
        provider_versions=dict(provider_versions or {}),
        schema_versions=dict(schema_versions or {}),
        latency_ms=dict(latency_ms or {}),
        endpoint=endpoint,
        certificate_info=cert,
        account_scope=scope,
        market_data_quality=quality,
        gate_results=gates,
        evidence_hash=digest,
        parent_certification_id=parent_certification_id,
        previous_evidence_hash=previous_evidence_hash,
        current_evidence_hash=digest,
        lineage_generation=lineage_generation,
        provider_fingerprint_hash=provider_fingerprint_hash,
        certification_id=certification_id,
    )
