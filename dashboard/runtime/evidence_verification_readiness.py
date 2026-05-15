from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


EVIDENCE_VERIFICATION_READINESS_VERSION = "css.evidence_verification_readiness.v1"
VERIFICATION_STATUS_NOT_VERIFIED = "NOT_VERIFIED"
VERIFICATION_STATUS_READY_FOR_MANUAL_VERIFICATION_REVIEW = (
    "READY_FOR_MANUAL_VERIFICATION_REVIEW"
)
VERIFICATION_STATUS_BLOCKED = "BLOCKED"

_SAFE_SIGNATURE_STATUSES = {
    "",
    "NOT_SIGNED",
    "BLOCKED",
    "READY_FOR_MANUAL_SIGNATURE_REVIEW",
}
_SAFE_NOTARIZATION_STATUSES = {
    "",
    "NOT_NOTARIZED",
    "BLOCKED",
    "READY_FOR_MANUAL_NOTARIZATION_REVIEW",
}
_SAFETY_DISCLAIMER = (
    "Evidence verification readiness is metadata only. CSS does not read private "
    "external archive files, perform hash re-verification, verify signatures, "
    "verify notarization, write archive files, approve trading, arm execution, "
    "place orders, mutate broker state, bypass governance, or enable runtime "
    "event persistence from this layer."
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
    "archive_read_performed",
    "archive_write_performed",
    "broker_mutation_allowed",
    "execution_allowed",
    "external_file_read_performed",
    "hash_recheck_available",
    "manual_verification_review_required",
    "notarization_verified",
    "persistence_enabled",
    "redaction_required",
    "signature_verified",
    "trading_armed",
    "verification_performed",
}


@dataclass(frozen=True)
class EvidenceVerificationReadiness:
    verification_readiness_id: str
    generated_at_utc: str
    manifest_hash_id: str
    combined_manifest_hash: str
    signature_readiness_id: str
    notarization_readiness_id: str
    verification_status: str
    verification_performed: bool
    archive_read_performed: bool
    external_file_read_performed: bool
    signature_verified: bool
    notarization_verified: bool
    hash_recheck_available: bool
    manual_verification_review_required: bool
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    blockers: list[str]
    warnings: list[str]
    safety_disclaimer: str
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = EVIDENCE_VERIFICATION_READINESS_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_verification_readiness_payload(
    manifest_hash_payload: Mapping[str, Any] | None = None,
    *,
    signature_readiness_payload: Mapping[str, Any] | None = None,
    notarization_readiness_payload: Mapping[str, Any] | None = None,
    verification_performed: bool = False,
    archive_read_performed: bool = False,
    external_file_read_performed: bool = False,
    signature_verified: bool = False,
    notarization_verified: bool = False,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    manifest = _mapping(manifest_hash_payload)
    signature = _mapping(signature_readiness_payload)
    notarization = _mapping(notarization_readiness_payload)
    manifest_hash_id = _first_text(
        manifest.get("manifest_hash_id"),
        signature.get("manifest_hash_id"),
        notarization.get("manifest_hash_id"),
    )
    combined_manifest_hash = _first_text(
        manifest.get("combined_manifest_hash"),
        signature.get("combined_manifest_hash"),
        notarization.get("combined_manifest_hash"),
    )
    signature_readiness_id = _first_text(
        signature.get("signature_readiness_id"),
        notarization.get("signature_readiness_id"),
    )
    notarization_readiness_id = _first_text(
        notarization.get("notarization_readiness_id"),
    )
    hash_recheck_available = bool(manifest_hash_id and combined_manifest_hash)
    blockers = _blockers(
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        signature_status=str(signature.get("signing_status") or ""),
        notarization_status=str(notarization.get("notarization_status") or ""),
        signature_generated=bool(signature.get("signature_generated")),
        verification_performed=verification_performed,
        archive_read_performed=archive_read_performed,
        external_file_read_performed=external_file_read_performed,
        signature_verified=signature_verified,
        notarization_verified=notarization_verified,
        archive_write_performed=_any_true(
            manifest.get("archive_write_performed"),
            signature.get("archive_write_performed"),
            notarization.get("archive_write_performed"),
        ),
        trading_armed=_any_true(
            manifest.get("trading_armed"),
            signature.get("trading_armed"),
            notarization.get("trading_armed"),
        ),
        execution_allowed=_any_true(
            manifest.get("execution_allowed"),
            signature.get("execution_allowed"),
            notarization.get("execution_allowed"),
        ),
        broker_mutation_allowed=_any_true(
            manifest.get("broker_mutation_allowed"),
            signature.get("broker_mutation_allowed"),
            notarization.get("broker_mutation_allowed"),
        ),
        persistence_enabled=_any_true(
            manifest.get("persistence_enabled"),
            signature.get("persistence_enabled"),
            notarization.get("persistence_enabled"),
        ),
    )
    warnings = _warnings(blockers, hash_recheck_available)
    status = _verification_status(blockers)
    readiness_id = _readiness_id(
        {
            "generated_at_utc": generated,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "signature_readiness_id": signature_readiness_id,
            "notarization_readiness_id": notarization_readiness_id,
            "status": status,
            "blockers": blockers,
        }
    )
    payload = EvidenceVerificationReadiness(
        verification_readiness_id=readiness_id,
        generated_at_utc=generated,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        signature_readiness_id=signature_readiness_id,
        notarization_readiness_id=notarization_readiness_id,
        verification_status=status,
        verification_performed=False,
        archive_read_performed=False,
        external_file_read_performed=False,
        signature_verified=False,
        notarization_verified=False,
        hash_recheck_available=hash_recheck_available,
        manual_verification_review_required=True,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        blockers=blockers,
        warnings=warnings,
        safety_disclaimer=_SAFETY_DISCLAIMER,
        audit_payload=_audit_payload(
            verification_readiness_id=readiness_id,
            generated_at_utc=generated,
            manifest_hash_id=manifest_hash_id,
            combined_manifest_hash=combined_manifest_hash,
            signature_readiness_id=signature_readiness_id,
            notarization_readiness_id=notarization_readiness_id,
            verification_status=status,
            hash_recheck_available=hash_recheck_available,
            blockers=blockers,
            warnings=warnings,
        ),
        source_metadata={
            "source": "dashboard.runtime.evidence_verification_readiness",
            "read_only": True,
            "verification_readiness_only": True,
            "no_external_archive_read": True,
            "no_external_file_read": True,
            "no_verification_performed": True,
            "no_signature_verification": True,
            "no_notarization_verification": True,
            "no_real_digital_signing": True,
            "no_external_notarization": True,
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
    signature_status: str,
    notarization_status: str,
    signature_generated: bool,
    verification_performed: bool,
    archive_read_performed: bool,
    external_file_read_performed: bool,
    signature_verified: bool,
    notarization_verified: bool,
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
    if signature_status not in _SAFE_SIGNATURE_STATUSES:
        blockers.append("SIGNATURE_STATUS_UNEXPECTED")
    if notarization_status not in _SAFE_NOTARIZATION_STATUSES:
        blockers.append("NOTARIZATION_STATUS_UNEXPECTED")
    if signature_generated:
        blockers.append("SIGNATURE_GENERATED_UNEXPECTED")
    if verification_performed:
        blockers.append("VERIFICATION_PERFORMED_UNEXPECTED")
    if archive_read_performed:
        blockers.append("ARCHIVE_READ_PERFORMED_UNEXPECTED")
    if external_file_read_performed:
        blockers.append("EXTERNAL_FILE_READ_PERFORMED_UNEXPECTED")
    if signature_verified:
        blockers.append("SIGNATURE_VERIFIED_UNEXPECTED")
    if notarization_verified:
        blockers.append("NOTARIZATION_VERIFIED_UNEXPECTED")
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


def _warnings(blockers: list[str], hash_recheck_available: bool) -> list[str]:
    warnings = [
        "MANUAL_VERIFICATION_REVIEW_REQUIRED",
        "VERIFICATION_PERFORMED_FALSE_FOR_CURRENT_PHASE",
        "NO_EXTERNAL_ARCHIVE_READ",
    ]
    warnings.append(
        "HASH_RECHECK_AVAILABLE"
        if hash_recheck_available
        else "HASH_RECHECK_UNAVAILABLE"
    )
    if blockers:
        warnings.append("VERIFICATION_READINESS_BLOCKERS_PRESENT")
    return warnings


def _verification_status(blockers: list[str]) -> str:
    if blockers:
        return VERIFICATION_STATUS_BLOCKED
    return VERIFICATION_STATUS_NOT_VERIFIED


def _audit_payload(
    *,
    verification_readiness_id: str,
    generated_at_utc: str,
    manifest_hash_id: str,
    combined_manifest_hash: str,
    signature_readiness_id: str,
    notarization_readiness_id: str,
    verification_status: str,
    hash_recheck_available: bool,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "verification_readiness_id": verification_readiness_id,
            "generated_at_utc": generated_at_utc,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "signature_readiness_id": signature_readiness_id,
            "notarization_readiness_id": notarization_readiness_id,
            "verification_status": verification_status,
            "verification_performed": False,
            "archive_read_performed": False,
            "external_file_read_performed": False,
            "signature_verified": False,
            "notarization_verified": False,
            "hash_recheck_available": hash_recheck_available,
            "manual_verification_review_required": True,
            "blockers": blockers,
            "warnings": warnings,
            "review_only": True,
            "verification_readiness_only": True,
            "audit_safe": True,
            "redaction_required": True,
            "trading_armed": False,
            "execution_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "approval_grant_endpoint_exists": False,
            "no_external_archive_read": True,
            "no_external_file_read": True,
            "no_verification_performed": True,
            "no_signature_verification": True,
            "no_notarization_verification": True,
            "no_real_digital_signing": True,
            "no_external_notarization": True,
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
    return f"VERIFYREADY-{digest}"


def _first_text(*values: Any) -> str:
    for value in values:
        if value:
            return str(value)
    return ""


def _any_true(*values: Any) -> bool:
    return any(bool(value) for value in values)


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
    "EVIDENCE_VERIFICATION_READINESS_VERSION",
    "VERIFICATION_STATUS_BLOCKED",
    "VERIFICATION_STATUS_NOT_VERIFIED",
    "VERIFICATION_STATUS_READY_FOR_MANUAL_VERIFICATION_REVIEW",
    "EvidenceVerificationReadiness",
    "build_evidence_verification_readiness_payload",
]
