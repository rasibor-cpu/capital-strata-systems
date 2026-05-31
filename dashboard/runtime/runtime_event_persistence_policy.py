from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


RUNTIME_EVENT_PERSISTENCE_POLICY_VERSION = "css.runtime_event_persistence_policy.v1"
RUNTIME_EVENT_PERSISTENCE_APPROVAL_VERSION = "css.runtime_event_persistence_approval.v1"
DEFAULT_APPROVED_EVENT_SUBSYSTEMS = (
    "alerting",
    "broker",
    "execution",
    "governance",
    "pnl_summary",
    "positions",
    "replay",
    "risk",
    "trade_lifecycle",
    "websocket",
)


@dataclass(frozen=True)
class RuntimeEventPersistencePolicy:
    persistence_enabled: bool = False
    operator_approval_required: bool = True
    approval_token_required: bool = True
    approved_subsystems: tuple[str, ...] = DEFAULT_APPROVED_EVENT_SUBSYSTEMS
    max_persistence_window_minutes: int = 60
    allowed_export_formats: tuple[str, ...] = ("json",)
    redaction_required: bool = True
    audit_logging_required: bool = True
    policy_version: str = RUNTIME_EVENT_PERSISTENCE_POLICY_VERSION

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["approved_subsystems"] = list(self.approved_subsystems)
        payload["allowed_export_formats"] = list(self.allowed_export_formats)
        return payload


@dataclass(frozen=True)
class RuntimeEventPersistenceApprovalRequest:
    request_id: str
    operator_id: str
    requested_subsystems: tuple[str, ...]
    requested_window_minutes: int
    reason: str
    timestamp_utc: str
    approval_token_present: bool = False
    requested_export_format: str = "json"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["requested_subsystems"] = list(self.requested_subsystems)
        return payload


@dataclass(frozen=True)
class RuntimeEventPersistenceApprovalResult:
    request_id: str
    status: str
    operator_id: str
    requested_subsystems: tuple[str, ...]
    requested_window_minutes: int
    reason: str
    timestamp_utc: str
    blocking_reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    audit_payload: dict[str, Any] = field(default_factory=dict)
    persistence_activation_performed: bool = False
    payload_version: str = RUNTIME_EVENT_PERSISTENCE_APPROVAL_VERSION

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["requested_subsystems"] = list(self.requested_subsystems)
        payload["blocking_reasons"] = list(self.blocking_reasons)
        payload["warnings"] = list(self.warnings)
        return payload


DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY = RuntimeEventPersistencePolicy()


def get_runtime_event_persistence_policy_payload(
    policy: RuntimeEventPersistencePolicy = DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
) -> dict[str, Any]:
    return {
        "payload_version": RUNTIME_EVENT_PERSISTENCE_POLICY_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "mutation_endpoint_available": False,
        "approval_grant_endpoint_available": False,
        "persistence_activation_available": False,
        "persistence_enabled": bool(policy.persistence_enabled),
        "policy": policy.as_dict(),
    }


def validate_persistence_request(
    *,
    requested_subsystems: Iterable[str],
    requested_window_minutes: int,
    reason: str,
    operator_id: str = "",
    approval_token: str = "",
    requested_export_format: str = "json",
    policy: RuntimeEventPersistencePolicy = DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY,
    request_id: str = "",
    timestamp_utc: str = "",
) -> dict[str, Any]:
    timestamp = timestamp_utc or datetime.now(timezone.utc).isoformat()
    normalized_subsystems = _normalize_subsystems(requested_subsystems)
    normalized_format = str(requested_export_format or "").strip().lower()
    request = RuntimeEventPersistenceApprovalRequest(
        request_id=request_id or _request_id(
            {
                "operator_id": operator_id,
                "requested_subsystems": normalized_subsystems,
                "requested_window_minutes": requested_window_minutes,
                "timestamp_utc": timestamp,
            }
        ),
        operator_id=str(operator_id or ""),
        requested_subsystems=normalized_subsystems,
        requested_window_minutes=_safe_int(requested_window_minutes),
        reason=str(reason or ""),
        timestamp_utc=timestamp,
        approval_token_present=bool(str(approval_token or "").strip()),
        requested_export_format=normalized_format,
    )

    blocking_reasons = _blocking_reasons(request, policy)
    warnings = _warnings(policy)
    status = "PASS" if not blocking_reasons else "FAIL"
    audit_payload = _audit_payload(
        request,
        policy,
        status=status,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
    )

    return RuntimeEventPersistenceApprovalResult(
        request_id=request.request_id,
        status=status,
        operator_id=request.operator_id,
        requested_subsystems=request.requested_subsystems,
        requested_window_minutes=request.requested_window_minutes,
        reason=request.reason,
        timestamp_utc=request.timestamp_utc,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        audit_payload=audit_payload,
        persistence_activation_performed=False,
    ).as_dict()


def _blocking_reasons(
    request: RuntimeEventPersistenceApprovalRequest,
    policy: RuntimeEventPersistencePolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if not policy.persistence_enabled:
        reasons.append("PERSISTENCE_DISABLED_BY_POLICY")
    if policy.operator_approval_required and not request.operator_id.strip():
        reasons.append("OPERATOR_APPROVAL_REQUIRED")
    if policy.approval_token_required and not request.approval_token_present:
        reasons.append("APPROVAL_TOKEN_REQUIRED")
    if not request.requested_subsystems:
        reasons.append("NO_SUBSYSTEMS_REQUESTED")

    allowed = {subsystem.lower() for subsystem in policy.approved_subsystems}
    for subsystem in request.requested_subsystems:
        if subsystem.lower() not in allowed:
            reasons.append(f"UNAPPROVED_SUBSYSTEM:{subsystem}")

    if request.requested_window_minutes <= 0:
        reasons.append("INVALID_PERSISTENCE_WINDOW")
    elif request.requested_window_minutes > int(policy.max_persistence_window_minutes):
        reasons.append("PERSISTENCE_WINDOW_EXCEEDS_POLICY")

    allowed_formats = {fmt.lower() for fmt in policy.allowed_export_formats}
    if request.requested_export_format not in allowed_formats:
        reasons.append("UNAPPROVED_EXPORT_FORMAT")

    return tuple(reasons)


def _warnings(policy: RuntimeEventPersistencePolicy) -> tuple[str, ...]:
    warnings: list[str] = [
        "VALIDATION_ONLY_NO_PERSISTENCE_ACTIVATION",
    ]
    if not policy.redaction_required:
        warnings.append("REDACTION_NOT_REQUIRED_BY_POLICY")
    if not policy.audit_logging_required:
        warnings.append("AUDIT_LOGGING_NOT_REQUIRED_BY_POLICY")
    return tuple(warnings)


def _audit_payload(
    request: RuntimeEventPersistenceApprovalRequest,
    policy: RuntimeEventPersistencePolicy,
    *,
    status: str,
    blocking_reasons: tuple[str, ...],
    warnings: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "payload_version": RUNTIME_EVENT_PERSISTENCE_APPROVAL_VERSION,
        "audit_safe": True,
        "secrets_redacted": True,
        "approval_token": "REDACTED" if request.approval_token_present else "",
        "approval_token_present": request.approval_token_present,
        "request": request.as_dict(),
        "status": status,
        "blocking_reasons": list(blocking_reasons),
        "warnings": list(warnings),
        "policy": policy.as_dict(),
        "persistence_activation_performed": False,
    }


def _normalize_subsystems(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values or ():
        text = str(value or "").strip()
        if text:
            normalized.append(text)
    return tuple(dict.fromkeys(normalized))


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _request_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"EVP-{digest}"


__all__ = [
    "DEFAULT_APPROVED_EVENT_SUBSYSTEMS",
    "DEFAULT_RUNTIME_EVENT_PERSISTENCE_POLICY",
    "RUNTIME_EVENT_PERSISTENCE_APPROVAL_VERSION",
    "RUNTIME_EVENT_PERSISTENCE_POLICY_VERSION",
    "RuntimeEventPersistenceApprovalRequest",
    "RuntimeEventPersistenceApprovalResult",
    "RuntimeEventPersistencePolicy",
    "get_runtime_event_persistence_policy_payload",
    "validate_persistence_request",
]
