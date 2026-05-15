from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


EVIDENCE_HASHING_PAYLOAD_VERSION = "css.evidence_hashing.v1"
HASH_ALGORITHM = "sha256"

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "private",
    "pem",
    "authorization",
    "bearer",
)
_SENSITIVE_VALUE_MARKERS = (
    "api_key=",
    "apikey=",
    "bearer ",
    "private key",
    "secret=",
    "token=",
    "password=",
    "authorization:",
)
_PUBLIC_SAFETY_KEYS = {
    "broker_mutation_allowed",
    "execution_allowed",
    "mutation_allowed",
    "order_submit_allowed",
    "persistence_enabled",
    "redaction_required",
    "trading_armed",
}


@dataclass(frozen=True)
class EvidenceHashRecord:
    evidence_hash_id: str
    generated_at_utc: str
    source_type: str
    source_reference: str
    evidence_hash: str
    algorithm: str
    canonical_size_bytes: int
    redaction_required: bool
    mutation_allowed: bool
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    payload_version: str = EVIDENCE_HASHING_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceHashChainPackage:
    chain_id: str
    generated_at_utc: str
    evidence_items: list[dict[str, Any]]
    item_count: int
    combined_chain_hash: str
    algorithm: str
    redaction_required: bool
    mutation_allowed: bool
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    safety_disclaimer: str
    source_metadata: dict[str, Any]
    payload_version: str = EVIDENCE_HASHING_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def hash_evidence_payload(
    payload: Mapping[str, Any] | Any,
    *,
    source_type: str = "json_payload",
    source_reference: str = "",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Hash a JSON-safe evidence-like payload without exposing the payload.

    The hash is computed from a redacted canonical serialization. Generated
    timestamps are metadata only and do not affect deterministic hash results.
    """

    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    canonical = _canonical_json(
        {
            "source_type": str(source_type or "json_payload"),
            "source_reference": str(source_reference or ""),
            "payload": _json_safe(payload),
        }
    )
    evidence_hash = _sha256(canonical)
    record = EvidenceHashRecord(
        evidence_hash_id=f"EVHASH-{evidence_hash[:20].upper()}",
        generated_at_utc=generated,
        source_type=str(source_type or "json_payload"),
        source_reference=str(source_reference or ""),
        evidence_hash=evidence_hash,
        algorithm=HASH_ALGORITHM,
        canonical_size_bytes=len(canonical.encode("utf-8")),
        redaction_required=True,
        mutation_allowed=False,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
    )
    return _json_safe(record.as_dict())


def hash_text_reference(
    text: str,
    *,
    source_type: str = "text_reference",
    source_reference: str = "",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    return hash_evidence_payload(
        {"text_reference": text},
        source_type=source_type,
        source_reference=source_reference,
        generated_at_utc=generated_at_utc,
    )


def build_evidence_hash_chain(
    evidence_sources: Mapping[str, Any] | Iterable[Mapping[str, Any]] | None = None,
    *,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build a read-only hash chain package from evidence payload descriptors.

    `evidence_sources` may be a mapping of source reference to payload or an
    iterable of descriptors with `payload` or `text`, `source_type`, and
    `source_reference` keys.
    """

    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    evidence_items = [
        _hash_source(source, generated_at_utc=generated)
        for source in _iter_sources(evidence_sources or {})
    ]
    chain_input = [
        {
            "source_type": item.get("source_type"),
            "source_reference": item.get("source_reference"),
            "evidence_hash": item.get("evidence_hash"),
            "algorithm": item.get("algorithm"),
        }
        for item in evidence_items
    ]
    combined_chain_hash = _sha256(_canonical_json(chain_input))
    chain = EvidenceHashChainPackage(
        chain_id=f"EVCHAIN-{combined_chain_hash[:20].upper()}",
        generated_at_utc=generated,
        evidence_items=evidence_items,
        item_count=len(evidence_items),
        combined_chain_hash=combined_chain_hash,
        algorithm=HASH_ALGORITHM,
        redaction_required=True,
        mutation_allowed=False,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        safety_disclaimer=(
            "Evidence hashes are integrity metadata only. This package does "
            "not authorize trading, arm execution, place orders, mutate broker "
            "state, grant approval, bypass governance, or enable persistence."
        ),
        source_metadata={
            "source": "dashboard.runtime.evidence_hashing",
            "read_only": True,
            "integrity_only": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_approval_grant_endpoint": True,
            "no_trading_arm": True,
            "no_persistence_activation": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(chain.as_dict())


def _hash_source(
    source: Mapping[str, Any],
    *,
    generated_at_utc: str,
) -> dict[str, Any]:
    source_type = str(source.get("source_type") or "json_payload")
    source_reference = str(source.get("source_reference") or "")
    if "text" in source:
        return hash_text_reference(
            str(source.get("text") or ""),
            source_type=source_type,
            source_reference=source_reference,
            generated_at_utc=generated_at_utc,
        )
    return hash_evidence_payload(
        source.get("payload", source),
        source_type=source_type,
        source_reference=source_reference,
        generated_at_utc=generated_at_utc,
    )


def _iter_sources(
    evidence_sources: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(evidence_sources, Mapping):
        return [
            {
                "source_type": "json_payload",
                "source_reference": str(key),
                "payload": evidence_sources[key],
            }
            for key in sorted(evidence_sources)
        ]
    return list(evidence_sources)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED" if _is_sensitive_key(str(key)) else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, Path)):
        return str(value)
    if isinstance(value, str) and _contains_sensitive_marker(value):
        return "REDACTED"
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    if lowered in _PUBLIC_SAFETY_KEYS:
        return False
    return any(part in lowered for part in _SENSITIVE_KEY_PARTS)


def _contains_sensitive_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SENSITIVE_VALUE_MARKERS)


__all__ = [
    "EVIDENCE_HASHING_PAYLOAD_VERSION",
    "HASH_ALGORITHM",
    "EvidenceHashChainPackage",
    "EvidenceHashRecord",
    "build_evidence_hash_chain",
    "hash_evidence_payload",
    "hash_text_reference",
]
