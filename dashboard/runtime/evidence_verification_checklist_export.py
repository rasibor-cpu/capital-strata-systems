from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


EVIDENCE_VERIFICATION_CHECKLIST_EXPORT_VERSION = (
    "css.evidence_verification_checklist_export.v1"
)
_SAFETY_DISCLAIMER = (
    "Evidence verification checklist export is a print-safe operator review "
    "package. No verification was performed by CSS. CSS does not read private "
    "external archive files, perform verification, verify signatures, verify "
    "notarization, perform signing, perform notarization, write archive files, "
    "approve trading, arm execution, place orders, mutate broker state, bypass "
    "governance, or enable runtime event persistence from this export view."
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
    "broker_mutation_allowed",
    "execution_allowed",
    "external_file_read_performed",
    "manual_verification_recorded",
    "manual_verification_required",
    "notarization_verified",
    "persistence_enabled",
    "redaction_required",
    "secrets_redacted",
    "signature_verified",
    "trading_armed",
    "verification_performed",
}


@dataclass(frozen=True)
class EvidenceVerificationChecklistExport:
    verification_export_id: str
    generated_at_utc: str
    verification_checklist_id: str
    verification_readiness_id: str
    manifest_hash_id: str
    combined_manifest_hash: str
    checklist_status: str
    manual_verification_required: bool
    manual_verification_recorded: bool
    archive_read_performed: bool
    external_file_read_performed: bool
    verification_performed: bool
    signature_verified: bool
    notarization_verified: bool
    required_items: list[dict[str, Any]]
    missing_items: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    safety_disclaimer: str
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    source_metadata: dict[str, Any]
    export_format: str = "json"
    payload_version: str = EVIDENCE_VERIFICATION_CHECKLIST_EXPORT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_verification_checklist_export_payload(
    checklist_payload: Mapping[str, Any] | None = None,
    *,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    checklist = _mapping(checklist_payload)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    checklist_id = str(checklist.get("verification_checklist_id") or "")
    readiness_id = str(checklist.get("verification_readiness_id") or "")
    manifest_hash_id = str(checklist.get("manifest_hash_id") or "")
    combined_manifest_hash = str(checklist.get("combined_manifest_hash") or "")
    checklist_status = str(checklist.get("checklist_status") or "INCOMPLETE")
    export_id = _export_id(
        {
            "generated_at_utc": generated,
            "verification_checklist_id": checklist_id,
            "verification_readiness_id": readiness_id,
            "manifest_hash_id": manifest_hash_id,
            "checklist_status": checklist_status,
        }
    )
    payload = EvidenceVerificationChecklistExport(
        verification_export_id=export_id,
        generated_at_utc=generated,
        verification_checklist_id=checklist_id,
        verification_readiness_id=readiness_id,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        checklist_status=checklist_status,
        manual_verification_required=True,
        manual_verification_recorded=False,
        archive_read_performed=False,
        external_file_read_performed=False,
        verification_performed=False,
        signature_verified=False,
        notarization_verified=False,
        required_items=_safe_item_list(checklist.get("required_items")),
        missing_items=_safe_item_list(checklist.get("missing_items")),
        blockers=[_sanitize_text(item) for item in checklist.get("blockers") or []],
        warnings=[_sanitize_text(item) for item in checklist.get("warnings") or []],
        safety_disclaimer=_SAFETY_DISCLAIMER,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        source_metadata={
            "source": "dashboard.runtime.evidence_verification_checklist_export",
            "read_only": True,
            "print_safe": True,
            "export_only": True,
            "verification_checklist_export_only": True,
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


def _safe_item_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append(
                {
                    "item_id": _sanitize_text(item.get("item_id") or ""),
                    "label": _sanitize_text(item.get("label") or ""),
                    "completed": bool(item.get("completed")),
                    "required": bool(item.get("required", True)),
                    "severity": _sanitize_text(item.get("severity") or ""),
                    "message": _sanitize_text(item.get("message") or ""),
                }
            )
        else:
            items.append(
                {
                    "item_id": "",
                    "label": _sanitize_text(item),
                    "completed": False,
                    "required": True,
                    "severity": "",
                    "message": "",
                }
            )
    return items


def _export_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"VERIFYEXPORT-{digest}"


def _mapping(value: Any) -> dict[str, Any]:
    return _json_safe(dict(value)) if isinstance(value, Mapping) else {}


def _sanitize_text(value: Any) -> str:
    text = str(value or "")
    normalized = text.lower()
    if any(marker in normalized for marker in _SENSITIVE_VALUE_MARKERS):
        return "REDACTED"
    return text


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
    "EVIDENCE_VERIFICATION_CHECKLIST_EXPORT_VERSION",
    "EvidenceVerificationChecklistExport",
    "build_evidence_verification_checklist_export_payload",
]
