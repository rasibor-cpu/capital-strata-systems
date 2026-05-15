from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


EVIDENCE_VERIFICATION_CHECKLIST_VERSION = "css.evidence_verification_checklist.v1"
CHECKLIST_STATUS_INCOMPLETE = "INCOMPLETE"
CHECKLIST_STATUS_REVIEW_READY = "REVIEW_READY"
CHECKLIST_STATUS_ELIGIBLE_FOR_MANUAL_REVIEW = "ELIGIBLE_FOR_MANUAL_REVIEW"

_SAFETY_DISCLAIMER = (
    "Evidence verification checklist is a read-only export surface. CSS does "
    "not read private external archive files, perform verification, verify "
    "signatures, verify notarization, perform signing, perform notarization, "
    "write archive files, approve trading, arm execution, place orders, mutate "
    "broker state, bypass governance, or enable runtime event persistence from "
    "this layer."
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
    "final_pcnrass_reference_captured",
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
class VerificationChecklistItem:
    item_id: str
    label: str
    completed: bool
    required: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceVerificationChecklist:
    verification_checklist_id: str
    generated_at_utc: str
    verification_readiness_id: str
    manifest_hash_id: str
    combined_manifest_hash: str
    signature_readiness_id: str
    notarization_readiness_id: str
    checklist_status: str
    manual_verification_required: bool
    manual_verification_recorded: bool
    archive_read_performed: bool
    external_file_read_performed: bool
    verification_performed: bool
    signature_verified: bool
    notarization_verified: bool
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    required_items: list[dict[str, Any]]
    completed_items: list[dict[str, Any]]
    missing_items: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    safety_disclaimer: str
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = EVIDENCE_VERIFICATION_CHECKLIST_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_verification_checklist_payload(
    verification_readiness_payload: Mapping[str, Any] | None = None,
    *,
    manual_verification_recorded: bool = False,
    final_pcnrass_reference_captured: bool = False,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    readiness = _mapping(verification_readiness_payload)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    verification_readiness_id = str(readiness.get("verification_readiness_id") or "")
    manifest_hash_id = str(readiness.get("manifest_hash_id") or "")
    combined_manifest_hash = str(readiness.get("combined_manifest_hash") or "")
    signature_readiness_id = str(readiness.get("signature_readiness_id") or "")
    notarization_readiness_id = str(readiness.get("notarization_readiness_id") or "")
    required_items = _checklist_items(
        verification_readiness=readiness,
        verification_readiness_id=verification_readiness_id,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        signature_readiness_id=signature_readiness_id,
        notarization_readiness_id=notarization_readiness_id,
        manual_verification_recorded=manual_verification_recorded,
        final_pcnrass_reference_captured=final_pcnrass_reference_captured,
    )
    completed_items = [item for item in required_items if item.completed]
    missing_items = [item for item in required_items if not item.completed]
    blockers = [
        f"{item.item_id}:{item.message}"
        for item in missing_items
        if item.severity in {"BLOCKER", "SAFETY"}
    ]
    checklist_status = _checklist_status(missing_items)
    warnings = _warnings(checklist_status, missing_items)
    checklist_id = _checklist_id(
        {
            "generated_at_utc": generated,
            "verification_readiness_id": verification_readiness_id,
            "manifest_hash_id": manifest_hash_id,
            "combined_manifest_hash": combined_manifest_hash,
            "missing_items": [item.item_id for item in missing_items],
            "status": checklist_status,
        }
    )
    checklist = EvidenceVerificationChecklist(
        verification_checklist_id=checklist_id,
        generated_at_utc=generated,
        verification_readiness_id=verification_readiness_id,
        manifest_hash_id=manifest_hash_id,
        combined_manifest_hash=combined_manifest_hash,
        signature_readiness_id=signature_readiness_id,
        notarization_readiness_id=notarization_readiness_id,
        checklist_status=checklist_status,
        manual_verification_required=True,
        manual_verification_recorded=False,
        archive_read_performed=False,
        external_file_read_performed=False,
        verification_performed=False,
        signature_verified=False,
        notarization_verified=False,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        required_items=[item.as_dict() for item in required_items],
        completed_items=[item.as_dict() for item in completed_items],
        missing_items=[item.as_dict() for item in missing_items],
        blockers=blockers,
        warnings=warnings,
        safety_disclaimer=_SAFETY_DISCLAIMER,
        audit_payload=_audit_payload(
            checklist_id=checklist_id,
            generated_at_utc=generated,
            verification_readiness_id=verification_readiness_id,
            checklist_status=checklist_status,
            blockers=blockers,
            warnings=warnings,
        ),
        source_metadata={
            "source": "dashboard.runtime.evidence_verification_checklist",
            "read_only": True,
            "checklist_only": True,
            "export_only": True,
            "verification_checklist_only": True,
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
    return _json_safe(checklist.as_dict())


def _checklist_items(
    *,
    verification_readiness: Mapping[str, Any],
    verification_readiness_id: str,
    manifest_hash_id: str,
    combined_manifest_hash: str,
    signature_readiness_id: str,
    notarization_readiness_id: str,
    manual_verification_recorded: bool,
    final_pcnrass_reference_captured: bool,
) -> list[VerificationChecklistItem]:
    return [
        _item(
            "verification_readiness_present",
            "Verification readiness evidence is present",
            bool(verification_readiness_id),
            "BLOCKER",
            "Verification readiness evidence must exist before manual readback review.",
        ),
        _item(
            "manifest_hash_copied",
            "Manifest hash copied",
            bool(manifest_hash_id),
            "BLOCKER",
            "Manifest hash reference must be present in the review package.",
        ),
        _item(
            "combined_manifest_hash_copied",
            "Combined manifest hash copied",
            bool(combined_manifest_hash),
            "BLOCKER",
            "Combined manifest hash must be present in the review package.",
        ),
        _item(
            "evidence_packet_source_identified",
            "Evidence packet source identified",
            bool(verification_readiness_id and manifest_hash_id),
            "BLOCKER",
            "Evidence packet source must be identifiable from readiness metadata.",
        ),
        _item(
            "signature_readiness_reviewed",
            "Signature readiness reviewed",
            bool(signature_readiness_id),
            "REVIEW",
            "Signature readiness reference should be reviewed manually.",
        ),
        _item(
            "notarization_readiness_reviewed",
            "Notarization readiness reviewed",
            bool(notarization_readiness_id),
            "REVIEW",
            "Notarization readiness reference should be reviewed manually.",
        ),
        _item(
            "no_external_file_read_by_css",
            "No external file read performed by CSS",
            verification_readiness.get("external_file_read_performed") is False,
            "SAFETY",
            "CSS must not read private external archive files in this checklist.",
        ),
        _item(
            "no_archive_read_by_css",
            "No archive read performed by CSS",
            verification_readiness.get("archive_read_performed") is False,
            "SAFETY",
            "CSS must not read archive files in this checklist.",
        ),
        _item(
            "no_verification_performed_by_css",
            "No verification performed by CSS",
            verification_readiness.get("verification_performed") is False,
            "SAFETY",
            "This checklist must not perform verification.",
        ),
        _item(
            "no_signature_verification_by_css",
            "No signature verification performed by CSS",
            verification_readiness.get("signature_verified") is False,
            "SAFETY",
            "This checklist must not verify signatures.",
        ),
        _item(
            "no_notarization_verification_by_css",
            "No notarization verification performed by CSS",
            verification_readiness.get("notarization_verified") is False,
            "SAFETY",
            "This checklist must not verify notarization.",
        ),
        _item(
            "operator_manual_review_required",
            "Operator manual review required",
            verification_readiness.get("manual_verification_review_required") is True,
            "REVIEW",
            "Manual verification review must remain required.",
        ),
        _item(
            "manual_verification_recorded",
            "Manual verification recorded outside CSS",
            manual_verification_recorded,
            "MANUAL",
            "Manual verification remains outstanding and is not recorded by this checklist.",
        ),
        _item(
            "final_pcnrass_reference_captured",
            "Final PCNRASS reference captured",
            final_pcnrass_reference_captured,
            "MANUAL",
            "Final PCNRASS reference must be captured outside this checklist.",
        ),
        _item(
            "trading_and_broker_safety_closed",
            "Trading, execution, broker mutation, and persistence remain closed",
            verification_readiness.get("trading_armed") is False
            and verification_readiness.get("execution_allowed") is False
            and verification_readiness.get("broker_mutation_allowed") is False
            and verification_readiness.get("persistence_enabled") is False,
            "SAFETY",
            "Readback checklist must not arm trading, allow execution, mutate broker state, or enable persistence.",
        ),
    ]


def _item(
    item_id: str,
    label: str,
    completed: bool,
    severity: str,
    message: str,
) -> VerificationChecklistItem:
    return VerificationChecklistItem(
        item_id=item_id,
        label=label,
        completed=bool(completed),
        required=True,
        severity=severity,
        message=message,
    )


def _checklist_status(missing_items: list[VerificationChecklistItem]) -> str:
    if any(item.severity in {"BLOCKER", "SAFETY"} for item in missing_items):
        return CHECKLIST_STATUS_INCOMPLETE
    if missing_items:
        return CHECKLIST_STATUS_REVIEW_READY
    return CHECKLIST_STATUS_ELIGIBLE_FOR_MANUAL_REVIEW


def _warnings(
    status: str,
    missing_items: list[VerificationChecklistItem],
) -> list[str]:
    warnings = [
        "MANUAL_VERIFICATION_REVIEW_REQUIRED",
        "NO_VERIFICATION_IS_PERFORMED_BY_THIS_CHECKLIST",
        "NO_EXTERNAL_FILE_READ_IS_PERFORMED_BY_THIS_CHECKLIST",
        "NO_SIGNATURE_OR_NOTARIZATION_VERIFICATION_IS_PERFORMED",
        "NO_TRADING_IS_ARMED_BY_THIS_CHECKLIST",
        "NO_BROKER_STATE_WILL_BE_MODIFIED",
        "PERSISTENCE_REMAINS_DISABLED",
    ]
    if status == CHECKLIST_STATUS_INCOMPLETE:
        warnings.append("SAFETY_OR_BLOCKER_ITEMS_REMAIN")
    if status == CHECKLIST_STATUS_REVIEW_READY:
        warnings.append("MANUAL_REVIEW_ITEMS_REMAIN")
    if any(item.item_id == "final_pcnrass_reference_captured" for item in missing_items):
        warnings.append("FINAL_PCNRASS_REFERENCE_STILL_REQUIRED")
    return list(dict.fromkeys(warnings))


def _audit_payload(
    *,
    checklist_id: str,
    generated_at_utc: str,
    verification_readiness_id: str,
    checklist_status: str,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "evidence_verification_checklist_created",
            "verification_checklist_id": checklist_id,
            "generated_at_utc": generated_at_utc,
            "verification_readiness_id": verification_readiness_id,
            "checklist_status": checklist_status,
            "manual_verification_required": True,
            "manual_verification_recorded": False,
            "archive_read_performed": False,
            "external_file_read_performed": False,
            "verification_performed": False,
            "signature_verified": False,
            "notarization_verified": False,
            "trading_armed": False,
            "execution_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "approval_granted": False,
            "order_placed": False,
            "broker_mutated": False,
            "blockers": blockers,
            "warnings": warnings,
            "review_only": True,
            "export_only": True,
            "audit_safe": True,
            "redaction_required": True,
            "no_external_archive_read": True,
            "no_external_file_read": True,
            "no_verification_performed": True,
            "no_signature_verification": True,
            "no_notarization_verification": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_runtime_event_persistence": True,
            "secrets_redacted": True,
        }
    )


def _checklist_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"VERIFYCHECK-{digest}"


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
    "CHECKLIST_STATUS_ELIGIBLE_FOR_MANUAL_REVIEW",
    "CHECKLIST_STATUS_INCOMPLETE",
    "CHECKLIST_STATUS_REVIEW_READY",
    "EVIDENCE_VERIFICATION_CHECKLIST_VERSION",
    "EvidenceVerificationChecklist",
    "VerificationChecklistItem",
    "build_evidence_verification_checklist_payload",
]
