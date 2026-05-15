from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


EVIDENCE_SIGNATURE_READINESS_VERSION = "css.evidence_signature_readiness.v1"
SIGNING_STATUS_NOT_SIGNED = "NOT_SIGNED"
SIGNING_STATUS_READY_FOR_MANUAL_SIGNATURE_REVIEW = (
    "READY_FOR_MANUAL_SIGNATURE_REVIEW"
)
SIGNING_STATUS_BLOCKED = "BLOCKED"
HASH_ALGORITHM = "sha256"

_SAFETY_DISCLAIMER = (
    "Signature readiness is metadata only. CSS does not load signing keys, "
    "perform digital signing, write signature files, approve trading, arm "
    "execution, place orders, mutate broker state, bypass governance, or "
    "enable runtime event persistence from this layer."
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
    "signing_key",
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
    "external_notarization_performed",
    "manual_signature_review_required",
    "no_private_key_loaded",
    "persistence_enabled",
    "redaction_required",
    "signature_required",
    "signature_write_performed",
    "signing_key_exposed",
    "signing_key_present",
    "trading_armed",
}


@dataclass(frozen=True)
class EvidenceSignatureReadiness:
    signature_readiness_id: str
    generated_at_utc: str
    manifest_hash_id: str
    combined_manifest_hash: str
    algorithm: str
    signing_status: str
    signature_required: bool
    manual_signature_review_required: bool
    signing_key_present: bool
    signing_key_exposed: bool
    signature_generated: bool
    signature_write_performed: bool
    external_notarization_performed: bool
    archive_write_performed: bool
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    blockers: list[str]
    warnings: list[str]
    safety_disclaimer: str
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = EVIDENCE_SIGNATURE_READINESS_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_signature_readiness_payload(
    manifest_hash_payload: Mapping[str, Any] | None = None,
    *,
    signing_key_present: bool = False,
    signing_key_exposed: bool = False,
    signature_generated: bool = False,
    signature_write_performed: bool = False,
    external_notarization_performed: bool = False,
    archive_write_performed: bool | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    manifest = _mapping(manifest_hash_payload)
    algorithm = str(manifest.get("algorithm") or HASH_ALGORITHM).lower()
    archive_write = (
        bool(manifest.get("archive_write_performed"))
        if archive_write_performed is None
        else bool(archive_write_performed)
    )
    manifest_hash_id = str(manifest.get("manifest_hash_id") or "")
    combined_manifest_hash = str(manifest.get("combined_manifest_hash") or "")
    blockers = _blockers(
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        algorithm=algorithm,
        signing_key_present=signing_key_present,
        signing_key_exposed=signing_key_exposed,
        signature_generated=signature_generated,
        signature_write_performed=signature_write_performed,
        external_notarization_performed=external_notarization_performed,
        archive_write_performed=archive_write,
        trading_armed=bool(manifest.get("trading_armed")),
        execution_allowed=bool(manifest.get("execution_allowed")),
        broker_mutation_allowed=bool(manifest.get("broker_mutation_allowed")),
        persistence_enabled=bool(manifest.get("persistence_enabled")),
    )
    warnings = _warnings(blockers)
    status = _signing_status(blockers)
    readiness_id = _readiness_id(
        {
            "generated_at_utc": generated,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "status": status,
            "blockers": blockers,
        }
    )
    payload = EvidenceSignatureReadiness(
        signature_readiness_id=readiness_id,
        generated_at_utc=generated,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        algorithm=algorithm,
        signing_status=status,
        signature_required=False,
        manual_signature_review_required=True,
        signing_key_present=False,
        signing_key_exposed=False,
        signature_generated=False,
        signature_write_performed=False,
        external_notarization_performed=False,
        archive_write_performed=False,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        blockers=blockers,
        warnings=warnings,
        safety_disclaimer=_SAFETY_DISCLAIMER,
        audit_payload=_audit_payload(
            signature_readiness_id=readiness_id,
            generated_at_utc=generated,
            manifest_hash_id=manifest_hash_id,
            combined_manifest_hash=combined_manifest_hash,
            algorithm=algorithm,
            signing_status=status,
            blockers=blockers,
            warnings=warnings,
        ),
        source_metadata={
            "source": "dashboard.runtime.evidence_signature_readiness",
            "read_only": True,
            "signature_readiness_only": True,
            "no_real_digital_signing": True,
            "no_private_key_loaded": True,
            "no_signature_file_write": True,
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


def _blockers(
    *,
    manifest_hash_id: str,
    combined_manifest_hash: str,
    algorithm: str,
    signing_key_present: bool,
    signing_key_exposed: bool,
    signature_generated: bool,
    signature_write_performed: bool,
    external_notarization_performed: bool,
    archive_write_performed: bool,
    trading_armed: bool,
    execution_allowed: bool,
    broker_mutation_allowed: bool,
    persistence_enabled: bool,
) -> list[str]:
    blockers: list[str] = []
    if not manifest_hash_id:
        blockers.append("MANIFEST_HASH_ID_MISSING")
    if not combined_manifest_hash:
        blockers.append("COMBINED_MANIFEST_HASH_MISSING")
    if algorithm != HASH_ALGORITHM:
        blockers.append("HASH_ALGORITHM_NOT_SHA256")
    if signing_key_present:
        blockers.append("SIGNING_KEY_PRESENT_UNEXPECTED")
    if signing_key_exposed:
        blockers.append("SIGNING_KEY_EXPOSED")
    if signature_generated:
        blockers.append("SIGNATURE_GENERATED_UNEXPECTED")
    if signature_write_performed:
        blockers.append("SIGNATURE_WRITE_PERFORMED_UNEXPECTED")
    if external_notarization_performed:
        blockers.append("EXTERNAL_NOTARIZATION_PERFORMED_UNEXPECTED")
    if archive_write_performed:
        blockers.append("ARCHIVE_WRITE_PERFORMED_UNEXPECTED")
    if trading_armed:
        blockers.append("TRADING_ARMED_UNEXPECTED")
    if execution_allowed:
        blockers.append("EXECUTION_ALLOWED_UNEXPECTED")
    if broker_mutation_allowed:
        blockers.append("BROKER_MUTATION_ALLOWED_UNEXPECTED")
    if persistence_enabled:
        blockers.append("PERSISTENCE_ENABLED_UNEXPECTED")
    return list(dict.fromkeys(blockers))


def _warnings(blockers: list[str]) -> list[str]:
    warnings = [
        "MANUAL_SIGNATURE_REVIEW_REQUIRED",
        "SIGNATURE_REQUIRED_FALSE_FOR_CURRENT_PHASE",
        "NO_SIGNING_KEY_LOADED",
    ]
    if blockers:
        warnings.append("SIGNATURE_READINESS_BLOCKERS_PRESENT")
    return warnings


def _signing_status(blockers: list[str]) -> str:
    if blockers:
        return SIGNING_STATUS_BLOCKED
    return SIGNING_STATUS_NOT_SIGNED


def _audit_payload(
    *,
    signature_readiness_id: str,
    generated_at_utc: str,
    manifest_hash_id: str,
    combined_manifest_hash: str,
    algorithm: str,
    signing_status: str,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "signature_readiness_id": signature_readiness_id,
            "generated_at_utc": generated_at_utc,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "algorithm": algorithm,
            "signing_status": signing_status,
            "signature_required": False,
            "manual_signature_review_required": True,
            "signing_key_present": False,
            "signing_key_exposed": False,
            "signature_generated": False,
            "signature_write_performed": False,
            "external_notarization_performed": False,
            "archive_write_performed": False,
            "blockers": blockers,
            "warnings": warnings,
            "review_only": True,
            "signature_readiness_only": True,
            "audit_safe": True,
            "redaction_required": True,
            "trading_armed": False,
            "execution_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "approval_grant_endpoint_exists": False,
            "no_real_digital_signing": True,
            "no_private_key_loaded": True,
            "no_signature_file_write": True,
            "no_archive_file_write": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_trading_arm": True,
            "no_runtime_event_persistence": True,
            "secrets_redacted": True,
        }
    )


def _readiness_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"SIGREADY-{digest}"


def _mapping(value: Any) -> dict[str, Any]:
    return _json_safe(dict(value)) if isinstance(value, Mapping) else {}


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
    "EVIDENCE_SIGNATURE_READINESS_VERSION",
    "HASH_ALGORITHM",
    "SIGNING_STATUS_BLOCKED",
    "SIGNING_STATUS_NOT_SIGNED",
    "SIGNING_STATUS_READY_FOR_MANUAL_SIGNATURE_REVIEW",
    "EvidenceSignatureReadiness",
    "build_evidence_signature_readiness_payload",
]
