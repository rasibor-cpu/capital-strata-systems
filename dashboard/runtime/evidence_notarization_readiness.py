from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


EVIDENCE_NOTARIZATION_READINESS_VERSION = "css.evidence_notarization_readiness.v1"
NOTARIZATION_STATUS_NOT_NOTARIZED = "NOT_NOTARIZED"
NOTARIZATION_STATUS_READY_FOR_MANUAL_NOTARIZATION_REVIEW = (
    "READY_FOR_MANUAL_NOTARIZATION_REVIEW"
)
NOTARIZATION_STATUS_BLOCKED = "BLOCKED"
HASH_ALGORITHM = "sha256"

_SAFETY_DISCLAIMER = (
    "Notarization readiness is metadata only. CSS does not perform external "
    "notarization, select a notarization provider, create receipts, write "
    "notarization files, load signing keys, approve trading, arm execution, "
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
    "archive_write_performed",
    "broker_mutation_allowed",
    "execution_allowed",
    "external_notarization_performed",
    "external_notarization_required",
    "manual_notarization_review_required",
    "notarization_file_written",
    "notarization_provider_selected",
    "notarization_receipt_present",
    "notarization_timestamp_present",
    "no_notarization_file_write",
    "no_notarization_performed",
    "no_notarization_provider_selected",
    "no_private_key_loaded",
    "persistence_enabled",
    "redaction_required",
    "signing_key_exposed",
    "signing_key_present",
    "trading_armed",
}


@dataclass(frozen=True)
class EvidenceNotarizationReadiness:
    notarization_readiness_id: str
    generated_at_utc: str
    signature_readiness_id: str
    manifest_hash_id: str
    combined_manifest_hash: str
    notarization_status: str
    external_notarization_required: bool
    manual_notarization_review_required: bool
    notarization_provider_selected: bool
    notarization_provider_name: str
    notarization_timestamp_present: bool
    notarization_receipt_present: bool
    notarization_file_written: bool
    signing_key_present: bool
    signing_key_exposed: bool
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
    payload_version: str = EVIDENCE_NOTARIZATION_READINESS_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_notarization_readiness_payload(
    signature_readiness_payload: Mapping[str, Any] | None = None,
    *,
    notarization_provider_selected: bool = False,
    notarization_provider_name: str = "",
    notarization_timestamp_present: bool = False,
    notarization_receipt_present: bool = False,
    notarization_file_written: bool = False,
    external_notarization_performed: bool = False,
    signing_key_present: bool = False,
    signing_key_exposed: bool = False,
    archive_write_performed: bool | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    signature = _mapping(signature_readiness_payload)
    signature_readiness_id = str(signature.get("signature_readiness_id") or "")
    manifest_hash_id = str(signature.get("manifest_hash_id") or "")
    combined_manifest_hash = str(signature.get("combined_manifest_hash") or "")
    archive_write = (
        bool(signature.get("archive_write_performed"))
        if archive_write_performed is None
        else bool(archive_write_performed)
    )
    signature_generated = bool(signature.get("signature_generated"))
    signature_status = str(signature.get("signing_status") or "")
    signature_external_notarization = bool(
        signature.get("external_notarization_performed")
    )
    provider_name = str(_json_safe(notarization_provider_name or ""))
    provider_selected = bool(notarization_provider_selected) or bool(provider_name)
    external_notarization = (
        bool(external_notarization_performed) or signature_external_notarization
    )
    blockers = _blockers(
        signature_readiness_id=signature_readiness_id,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        signature_status=signature_status,
        signature_generated=signature_generated,
        external_notarization_performed=external_notarization,
        notarization_provider_selected=provider_selected,
        notarization_timestamp_present=notarization_timestamp_present,
        notarization_receipt_present=notarization_receipt_present,
        notarization_file_written=notarization_file_written,
        signing_key_present=signing_key_present
        or bool(signature.get("signing_key_present")),
        signing_key_exposed=signing_key_exposed
        or bool(signature.get("signing_key_exposed")),
        archive_write_performed=archive_write,
        trading_armed=bool(signature.get("trading_armed")),
        execution_allowed=bool(signature.get("execution_allowed")),
        broker_mutation_allowed=bool(signature.get("broker_mutation_allowed")),
        persistence_enabled=bool(signature.get("persistence_enabled")),
    )
    warnings = _warnings(blockers)
    status = _notarization_status(blockers)
    readiness_id = _readiness_id(
        {
            "generated_at_utc": generated,
            "signature_readiness_id": signature_readiness_id,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "status": status,
            "blockers": blockers,
        }
    )
    payload = EvidenceNotarizationReadiness(
        notarization_readiness_id=readiness_id,
        generated_at_utc=generated,
        signature_readiness_id=signature_readiness_id,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        notarization_status=status,
        external_notarization_required=False,
        manual_notarization_review_required=True,
        notarization_provider_selected=False,
        notarization_provider_name="",
        notarization_timestamp_present=False,
        notarization_receipt_present=False,
        notarization_file_written=False,
        signing_key_present=False,
        signing_key_exposed=False,
        archive_write_performed=False,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        blockers=blockers,
        warnings=warnings,
        safety_disclaimer=_SAFETY_DISCLAIMER,
        audit_payload=_audit_payload(
            notarization_readiness_id=readiness_id,
            generated_at_utc=generated,
            signature_readiness_id=signature_readiness_id,
            manifest_hash_id=manifest_hash_id,
            combined_manifest_hash=combined_manifest_hash,
            notarization_status=status,
            blockers=blockers,
            warnings=warnings,
        ),
        source_metadata={
            "source": "dashboard.runtime.evidence_notarization_readiness",
            "read_only": True,
            "notarization_readiness_only": True,
            "no_real_digital_signing": True,
            "no_external_notarization": True,
            "no_notarization_provider_selected": True,
            "no_notarization_receipt": True,
            "no_notarization_file_write": True,
            "no_private_key_loaded": True,
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
    signature_readiness_id: str,
    manifest_hash_id: str,
    combined_manifest_hash: str,
    signature_status: str,
    signature_generated: bool,
    external_notarization_performed: bool,
    notarization_provider_selected: bool,
    notarization_timestamp_present: bool,
    notarization_receipt_present: bool,
    notarization_file_written: bool,
    signing_key_present: bool,
    signing_key_exposed: bool,
    archive_write_performed: bool,
    trading_armed: bool,
    execution_allowed: bool,
    broker_mutation_allowed: bool,
    persistence_enabled: bool,
) -> list[str]:
    blockers: list[str] = []
    if not signature_readiness_id:
        blockers.append("SIGNATURE_READINESS_ID_MISSING")
    if not manifest_hash_id:
        blockers.append("MANIFEST_HASH_ID_MISSING")
    if not combined_manifest_hash:
        blockers.append("COMBINED_MANIFEST_HASH_MISSING")
    if signature_status and signature_status not in {"NOT_SIGNED", "BLOCKED"}:
        blockers.append("SIGNATURE_STATUS_UNEXPECTED")
    if signature_generated:
        blockers.append("SIGNATURE_GENERATED_UNEXPECTED")
    if external_notarization_performed:
        blockers.append("EXTERNAL_NOTARIZATION_PERFORMED_UNEXPECTED")
    if notarization_provider_selected:
        blockers.append("NOTARIZATION_PROVIDER_SELECTED_UNEXPECTED")
    if notarization_timestamp_present:
        blockers.append("NOTARIZATION_TIMESTAMP_PRESENT_UNEXPECTED")
    if notarization_receipt_present:
        blockers.append("NOTARIZATION_RECEIPT_PRESENT_UNEXPECTED")
    if notarization_file_written:
        blockers.append("NOTARIZATION_FILE_WRITTEN_UNEXPECTED")
    if signing_key_present:
        blockers.append("SIGNING_KEY_PRESENT_UNEXPECTED")
    if signing_key_exposed:
        blockers.append("SIGNING_KEY_EXPOSED")
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
        "MANUAL_NOTARIZATION_REVIEW_REQUIRED",
        "EXTERNAL_NOTARIZATION_REQUIRED_FALSE_FOR_CURRENT_PHASE",
        "NO_NOTARIZATION_PROVIDER_SELECTED",
        "NO_NOTARIZATION_RECEIPT_PRESENT",
    ]
    if blockers:
        warnings.append("NOTARIZATION_READINESS_BLOCKERS_PRESENT")
    return warnings


def _notarization_status(blockers: list[str]) -> str:
    if blockers:
        return NOTARIZATION_STATUS_BLOCKED
    return NOTARIZATION_STATUS_NOT_NOTARIZED


def _audit_payload(
    *,
    notarization_readiness_id: str,
    generated_at_utc: str,
    signature_readiness_id: str,
    manifest_hash_id: str,
    combined_manifest_hash: str,
    notarization_status: str,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "notarization_readiness_id": notarization_readiness_id,
            "generated_at_utc": generated_at_utc,
            "signature_readiness_id": signature_readiness_id,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "notarization_status": notarization_status,
            "external_notarization_required": False,
            "manual_notarization_review_required": True,
            "notarization_provider_selected": False,
            "notarization_timestamp_present": False,
            "notarization_receipt_present": False,
            "notarization_file_written": False,
            "signing_key_present": False,
            "signing_key_exposed": False,
            "archive_write_performed": False,
            "blockers": blockers,
            "warnings": warnings,
            "review_only": True,
            "notarization_readiness_only": True,
            "audit_safe": True,
            "redaction_required": True,
            "trading_armed": False,
            "execution_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "approval_grant_endpoint_exists": False,
            "no_real_digital_signing": True,
            "no_external_notarization": True,
            "no_notarization_provider_selected": True,
            "no_notarization_receipt": True,
            "no_notarization_file_write": True,
            "no_private_key_loaded": True,
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
    return f"NOTARYREADY-{digest}"


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
    "EVIDENCE_NOTARIZATION_READINESS_VERSION",
    "HASH_ALGORITHM",
    "NOTARIZATION_STATUS_BLOCKED",
    "NOTARIZATION_STATUS_NOT_NOTARIZED",
    "NOTARIZATION_STATUS_READY_FOR_MANUAL_NOTARIZATION_REVIEW",
    "EvidenceNotarizationReadiness",
    "build_evidence_notarization_readiness_payload",
]
