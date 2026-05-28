from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


OPERATOR_ACTION_AUDIT_LEDGER_VERSION = "css.operator_action_audit_ledger.v1"

SUPPORTED_OPERATOR_ACTION_TYPES = (
    "READINESS_REVIEWED",
    "ORDER_INTENT_REVIEWED",
    "DRY_RUN_PROBE_REVIEWED",
    "APPROVAL_GATE_REVIEWED",
    "BROKER_READINESS_REVIEWED",
    "GO_NO_GO_REVIEWED",
    "MANUAL_CHECKLIST_REVIEWED",
    "EVIDENCE_HASH_REVIEWED",
    "NO_GO_LOG_REVIEWED",
    "INCIDENT_WORKSHEET_REVIEWED",
    "PACKET_EXPORTED",
)

DEFAULT_ACTION_SCOPE = "controlled_micro_live_pilot"

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
    "secrets_redacted",
    "trading_armed",
}
_SAFETY_DISCLAIMER = (
    "Operator action audit entries are review records only. They do not approve "
    "trading, arm execution, place orders, mutate broker state, bypass "
    "governance, or enable runtime event persistence."
)


@dataclass(frozen=True)
class OperatorActionAuditRecord:
    action_id: str
    generated_at_utc: str
    operator_id: str
    action_type: str
    action_scope: str
    source_page: str
    source_api: str
    related_evidence_id: str
    related_hash_chain_id: str
    notes: str
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    redaction_required: bool
    audit_payload: dict[str, Any]
    payload_version: str = OPERATOR_ACTION_AUDIT_LEDGER_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class OperatorActionAuditLedger:
    """Small in-memory review ledger for operator-action audit foundations."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def record_action(
        self,
        *,
        action_type: str,
        operator_id: str = "",
        action_scope: str = DEFAULT_ACTION_SCOPE,
        source_page: str = "",
        source_api: str = "",
        related_evidence_id: str = "",
        related_hash_chain_id: str = "",
        notes: str = "",
        generated_at_utc: str = "",
    ) -> dict[str, Any]:
        entry = build_operator_action_audit_record(
            action_type=action_type,
            operator_id=operator_id,
            action_scope=action_scope,
            source_page=source_page,
            source_api=source_api,
            related_evidence_id=related_evidence_id,
            related_hash_chain_id=related_hash_chain_id,
            notes=notes,
            generated_at_utc=generated_at_utc,
        )
        self._entries.append(entry)
        return entry

    def append(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        safe_entry = _normalize_entry(entry)
        self._entries.append(safe_entry)
        return safe_entry

    def get_recent(
        self,
        *,
        limit: int = 25,
        action_type: str = "",
        action_scope: str = "",
        operator_id: str = "",
        related_hash_chain_id: str = "",
    ) -> list[dict[str, Any]]:
        filtered = [
            entry
            for entry in self._entries
            if _matches(entry, action_type, action_scope, operator_id, related_hash_chain_id)
        ]
        capped = _safe_limit(limit)
        return list(reversed(filtered[-capped:]))

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


_DEFAULT_LEDGER = OperatorActionAuditLedger()


def get_default_operator_action_audit_ledger() -> OperatorActionAuditLedger:
    return _DEFAULT_LEDGER


def build_operator_action_audit_record(
    *,
    action_type: str,
    operator_id: str = "",
    action_scope: str = DEFAULT_ACTION_SCOPE,
    source_page: str = "",
    source_api: str = "",
    related_evidence_id: str = "",
    related_hash_chain_id: str = "",
    notes: str = "",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    normalized_action = _normalize_action_type(action_type)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    safe_core = _json_safe(
        {
            "generated_at_utc": generated,
            "operator_id": str(operator_id or ""),
            "action_type": normalized_action,
            "action_scope": str(action_scope or DEFAULT_ACTION_SCOPE),
            "source_page": str(source_page or ""),
            "source_api": str(source_api or ""),
            "related_evidence_id": str(related_evidence_id or ""),
            "related_hash_chain_id": str(related_hash_chain_id or ""),
            "notes": str(notes or ""),
        }
    )
    action_id = _action_id(safe_core)
    audit_payload = _audit_payload(
        action_id=action_id,
        generated_at_utc=generated,
        operator_id=str(safe_core["operator_id"]),
        action_type=normalized_action,
        action_scope=str(safe_core["action_scope"]),
        source_page=str(safe_core["source_page"]),
        source_api=str(safe_core["source_api"]),
        related_evidence_id=str(safe_core["related_evidence_id"]),
        related_hash_chain_id=str(safe_core["related_hash_chain_id"]),
    )
    record = OperatorActionAuditRecord(
        action_id=action_id,
        generated_at_utc=generated,
        operator_id=str(safe_core["operator_id"]),
        action_type=normalized_action,
        action_scope=str(safe_core["action_scope"]),
        source_page=str(safe_core["source_page"]),
        source_api=str(safe_core["source_api"]),
        related_evidence_id=str(safe_core["related_evidence_id"]),
        related_hash_chain_id=str(safe_core["related_hash_chain_id"]),
        notes=str(safe_core["notes"]),
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        redaction_required=True,
        audit_payload=audit_payload,
    )
    return _json_safe(record.as_dict())


def build_operator_action_audit_ledger_payload(
    ledger: OperatorActionAuditLedger | None = None,
    *,
    limit: int = 25,
    action_type: str = "",
    action_scope: str = "",
    operator_id: str = "",
    related_hash_chain_id: str = "",
    include_samples: bool = True,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    active_ledger = ledger or get_default_operator_action_audit_ledger()
    entries = active_ledger.get_recent(
        limit=limit,
        action_type=action_type,
        action_scope=action_scope,
        operator_id=operator_id,
        related_hash_chain_id=related_hash_chain_id,
    )
    sample_entries = (
        _sample_entries(
            generated_at_utc=generated,
            related_hash_chain_id=related_hash_chain_id,
        )
        if include_samples and not entries
        else []
    )
    payload = {
        "payload_version": OPERATOR_ACTION_AUDIT_LEDGER_VERSION,
        "generated_at_utc": generated,
        "read_only": True,
        "review_only": True,
        "foundation_only": True,
        "mutation_allowed": False,
        "trading_armed": False,
        "execution_allowed": False,
        "broker_mutation_allowed": False,
        "persistence_enabled": False,
        "redaction_required": True,
        "approval_grant_endpoint_exists": False,
        "writes_performed": False,
        "supported_action_types": list(SUPPORTED_OPERATOR_ACTION_TYPES),
        "entries": entries,
        "entry_count": len(entries),
        "sample_entries": sample_entries,
        "sample_entry_count": len(sample_entries),
        "summary": _summary(entries),
        "safety_disclaimer": _SAFETY_DISCLAIMER,
        "source_metadata": {
            "source": "dashboard.runtime.operator_action_audit_ledger",
            "read_only": True,
            "in_memory_only": True,
            "no_disk_writes": True,
            "no_runtime_event_persistence": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_approval_grant_endpoint": True,
            "no_trading_arm": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    }
    return _json_safe(payload)


def _sample_entries(
    *,
    generated_at_utc: str,
    related_hash_chain_id: str = "",
) -> list[dict[str, Any]]:
    samples = [
        build_operator_action_audit_record(
            action_type="READINESS_REVIEWED",
            action_scope=DEFAULT_ACTION_SCOPE,
            source_page="/micro-live-pilot-readiness",
            source_api="/api/v1/micro-live-pilot-readiness",
            related_hash_chain_id=related_hash_chain_id,
            notes="sample readiness review action; not an approval",
            generated_at_utc=generated_at_utc,
        ),
        build_operator_action_audit_record(
            action_type="EVIDENCE_HASH_REVIEWED",
            action_scope=DEFAULT_ACTION_SCOPE,
            source_page="/micro-live-pilot-readiness",
            source_api="/api/v1/evidence-hash-chain",
            related_hash_chain_id=related_hash_chain_id,
            notes="sample evidence hash review action; no trading armed",
            generated_at_utc=generated_at_utc,
        ),
    ]
    return [{**sample, "sample_only": True} for sample in samples]


def _summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "counts_by_action_type": _count_by(entries, "action_type"),
        "counts_by_action_scope": _count_by(entries, "action_scope"),
        "counts_by_source_page": _count_by(entries, "source_page"),
    }


def _count_by(entries: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry.get(key) or "UNKNOWN")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _normalize_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    action_type = _normalize_action_type(str(entry.get("action_type") or ""))
    safe = _json_safe(dict(entry))
    safe["action_type"] = action_type
    safe["trading_armed"] = False
    safe["execution_allowed"] = False
    safe["broker_mutation_allowed"] = False
    safe["persistence_enabled"] = False
    safe["redaction_required"] = True
    safe["payload_version"] = OPERATOR_ACTION_AUDIT_LEDGER_VERSION
    if not safe.get("action_id"):
        safe["action_id"] = _action_id(safe)
    if "audit_payload" not in safe:
        safe["audit_payload"] = _audit_payload(
            action_id=str(safe["action_id"]),
            generated_at_utc=str(safe.get("generated_at_utc") or ""),
            operator_id=str(safe.get("operator_id") or ""),
            action_type=action_type,
            action_scope=str(safe.get("action_scope") or DEFAULT_ACTION_SCOPE),
            source_page=str(safe.get("source_page") or ""),
            source_api=str(safe.get("source_api") or ""),
            related_evidence_id=str(safe.get("related_evidence_id") or ""),
            related_hash_chain_id=str(safe.get("related_hash_chain_id") or ""),
        )
    return safe


def _matches(
    entry: Mapping[str, Any],
    action_type: str,
    action_scope: str,
    operator_id: str,
    related_hash_chain_id: str,
) -> bool:
    filters = {
        "action_type": action_type,
        "action_scope": action_scope,
        "operator_id": operator_id,
        "related_hash_chain_id": related_hash_chain_id,
    }
    return all(
        not expected or str(entry.get(key) or "") == str(expected)
        for key, expected in filters.items()
    )


def _normalize_action_type(action_type: str) -> str:
    normalized = str(action_type or "").strip().upper()
    if normalized not in SUPPORTED_OPERATOR_ACTION_TYPES:
        raise ValueError(f"unsupported operator action type: {action_type!r}")
    return normalized


def _audit_payload(
    *,
    action_id: str,
    generated_at_utc: str,
    operator_id: str,
    action_type: str,
    action_scope: str,
    source_page: str,
    source_api: str,
    related_evidence_id: str,
    related_hash_chain_id: str,
) -> dict[str, Any]:
    return _json_safe(
        {
            "action_id": action_id,
            "generated_at_utc": generated_at_utc,
            "operator_id": operator_id,
            "action_type": action_type,
            "action_scope": action_scope,
            "source_page": source_page,
            "source_api": source_api,
            "related_evidence_id": related_evidence_id,
            "related_hash_chain_id": related_hash_chain_id,
            "review_only": True,
            "audit_safe": True,
            "redaction_required": True,
            "trading_armed": False,
            "execution_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "approval_grant_endpoint_exists": False,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_trading_arm": True,
            "no_runtime_event_persistence": True,
            "secrets_redacted": True,
        }
    )


def _safe_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 25
    return max(1, min(parsed, 100))


def _action_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"OPACT-{digest}"


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
    "DEFAULT_ACTION_SCOPE",
    "OPERATOR_ACTION_AUDIT_LEDGER_VERSION",
    "SUPPORTED_OPERATOR_ACTION_TYPES",
    "OperatorActionAuditLedger",
    "OperatorActionAuditRecord",
    "build_operator_action_audit_ledger_payload",
    "build_operator_action_audit_record",
    "get_default_operator_action_audit_ledger",
]
