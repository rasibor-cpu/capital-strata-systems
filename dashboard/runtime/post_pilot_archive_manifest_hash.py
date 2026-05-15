from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


POST_PILOT_ARCHIVE_MANIFEST_HASH_VERSION = (
    "css.post_pilot_archive_manifest_hash.v1"
)
HASH_ALGORITHM = "sha256"

_SAFETY_DISCLAIMER = (
    "Archive manifest hashes are tamper-evidence metadata only. This hash "
    "package does not write archive files, approve trading, arm execution, "
    "place orders, mutate broker state, bypass governance, or enable runtime "
    "event persistence."
)
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
    "archive_write_performed",
    "broker_mutation_allowed",
    "execution_allowed",
    "persistence_enabled",
    "redaction_required",
    "secrets_redacted",
    "trading_armed",
}


@dataclass(frozen=True)
class PostPilotArchiveManifestHash:
    manifest_hash_id: str
    generated_at_utc: str
    archive_export_id: str
    reconciliation_id: str
    evidence_hash_chain_id: str
    item_count: int
    evidence_reference_count: int
    manifest_hash: str
    combined_manifest_hash: str
    algorithm: str
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    archive_write_performed: bool
    redaction_required: bool
    safety_disclaimer: str
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = POST_PILOT_ARCHIVE_MANIFEST_HASH_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_post_pilot_archive_manifest_hash_payload(
    archive_export_package: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    archive_package = _mapping(archive_export_package)
    redacted_package = _json_safe(archive_package)
    evidence_references = _evidence_references(redacted_package)
    manifest_hash = _sha256(
        _canonical_json(
            {
                "package": redacted_package,
                "hash_scope": "post_pilot_archive_export_manifest",
            }
        )
    )
    combined_manifest_hash = _sha256(
        _canonical_json(
            [
                {
                    "reference_type": item["reference_type"],
                    "reference_value": item["reference_value"],
                }
                for item in evidence_references
            ]
        )
    )
    manifest_hash_id = f"POSTMAN-{manifest_hash[:20].upper()}"
    archive_export_id = str(redacted_package.get("archive_export_id") or "")
    reconciliation_id = str(redacted_package.get("reconciliation_id") or "")
    evidence_hash_chain_id = str(redacted_package.get("evidence_hash_chain_id") or "")
    payload = PostPilotArchiveManifestHash(
        manifest_hash_id=manifest_hash_id,
        generated_at_utc=generated,
        archive_export_id=archive_export_id,
        reconciliation_id=reconciliation_id,
        evidence_hash_chain_id=evidence_hash_chain_id,
        item_count=len(redacted_package),
        evidence_reference_count=len(evidence_references),
        manifest_hash=manifest_hash,
        combined_manifest_hash=combined_manifest_hash,
        algorithm=HASH_ALGORITHM,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        archive_write_performed=False,
        redaction_required=True,
        safety_disclaimer=_SAFETY_DISCLAIMER,
        audit_payload=_audit_payload(
            manifest_hash_id=manifest_hash_id,
            generated_at_utc=generated,
            archive_export_id=archive_export_id,
            reconciliation_id=reconciliation_id,
            evidence_hash_chain_id=evidence_hash_chain_id,
            manifest_hash=manifest_hash,
            combined_manifest_hash=combined_manifest_hash,
            evidence_references=evidence_references,
        ),
        source_metadata={
            "source": "dashboard.runtime.post_pilot_archive_manifest_hash",
            "read_only": True,
            "integrity_only": True,
            "hashing_only": True,
            "no_archive_file_write": True,
            "no_disk_writes": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_approval_grant_endpoint": True,
            "no_trading_arm": True,
            "no_runtime_event_persistence": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(payload.as_dict())


def _evidence_references(package: Mapping[str, Any]) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for reference_type, key in (
        ("archive_export_id", "archive_export_id"),
        ("reconciliation_id", "reconciliation_id"),
        ("evidence_hash_chain_id", "evidence_hash_chain_id"),
    ):
        value = str(package.get(key) or "")
        if value:
            references.append(
                {
                    "reference_type": reference_type,
                    "reference_value": value,
                }
            )
    for reference_type, key in (
        ("replay_correlation_id", "replay_correlation_ids"),
        ("audit_action_id", "audit_action_ids"),
        ("incident_id", "incident_ids"),
        ("no_go_decision_id", "no_go_decision_ids"),
    ):
        for value in _string_list(package.get(key)):
            references.append(
                {
                    "reference_type": reference_type,
                    "reference_value": value,
                }
            )
    return sorted(
        references,
        key=lambda item: (item["reference_type"], item["reference_value"]),
    )


def _audit_payload(
    *,
    manifest_hash_id: str,
    generated_at_utc: str,
    archive_export_id: str,
    reconciliation_id: str,
    evidence_hash_chain_id: str,
    manifest_hash: str,
    combined_manifest_hash: str,
    evidence_references: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    return _json_safe(
        {
            "manifest_hash_id": manifest_hash_id,
            "generated_at_utc": generated_at_utc,
            "archive_export_id": archive_export_id,
            "reconciliation_id": reconciliation_id,
            "evidence_hash_chain_id": evidence_hash_chain_id,
            "manifest_hash": manifest_hash,
            "combined_manifest_hash": combined_manifest_hash,
            "evidence_references": list(evidence_references),
            "review_only": True,
            "integrity_only": True,
            "audit_safe": True,
            "redaction_required": True,
            "trading_armed": False,
            "execution_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "archive_write_performed": False,
            "approval_grant_endpoint_exists": False,
            "no_archive_file_write": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_trading_arm": True,
            "no_runtime_event_persistence": True,
            "secrets_redacted": True,
        }
    )


def _mapping(value: Any) -> dict[str, Any]:
    return _json_safe(dict(value)) if isinstance(value, Mapping) else {}


def _string_list(values: Any) -> list[str]:
    if isinstance(values, str):
        return [values] if values.strip() else []
    if not isinstance(values, Sequence):
        return []
    return [
        str(item)
        for item in values
        if str(item or "").strip()
    ]


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
    "HASH_ALGORITHM",
    "POST_PILOT_ARCHIVE_MANIFEST_HASH_VERSION",
    "PostPilotArchiveManifestHash",
    "build_post_pilot_archive_manifest_hash_payload",
]
