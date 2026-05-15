from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.micro_live_pilot_order_intent import (
    CANONICAL_BROKER,
    CANONICAL_SYMBOL,
)
from dashboard.runtime.post_pilot_reconciliation_workflow import (
    RECONCILIATION_INCOMPLETE,
)


POST_PILOT_ARCHIVE_EXPORT_PAYLOAD_VERSION = (
    "css.post_pilot_evidence_archive_export.v1"
)

_SAFETY_DISCLAIMER = (
    "This post-pilot evidence archive export is JSON-safe review metadata only. "
    "It does not write archive files, approve trading, arm execution, place "
    "orders, mutate broker state, bypass governance, or enable runtime event "
    "persistence."
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
class PostPilotEvidenceArchiveExport:
    archive_export_id: str
    generated_at_utc: str
    broker: str
    symbol: str
    pilot_scope: dict[str, Any]
    reconciliation_id: str
    reconciliation_status: str
    evidence_hash_chain_id: str
    replay_correlation_ids: list[str]
    audit_action_ids: list[str]
    incident_ids: list[str]
    no_go_decision_ids: list[str]
    broker_balance_summary: dict[str, Any]
    css_ledger_summary: dict[str, Any]
    fee_slippage_summary: dict[str, Any]
    fill_summary: dict[str, Any]
    operator_conclusion: str
    safety_disclaimer: str
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    archive_write_performed: bool
    redaction_required: bool
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = POST_PILOT_ARCHIVE_EXPORT_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_post_pilot_evidence_archive_export_payload(
    *,
    reconciliation: Mapping[str, Any] | None = None,
    incident_ids: Sequence[str] | None = None,
    no_go_decision_ids: Sequence[str] | None = None,
    broker_balance_summary: Mapping[str, Any] | None = None,
    css_ledger_summary: Mapping[str, Any] | None = None,
    fee_slippage_summary: Mapping[str, Any] | None = None,
    fill_summary: Mapping[str, Any] | None = None,
    operator_conclusion: str = "",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    reconciliation_payload = _mapping(reconciliation)
    broker = str(reconciliation_payload.get("broker") or CANONICAL_BROKER)
    symbol = str(reconciliation_payload.get("symbol") or CANONICAL_SYMBOL)
    reconciliation_id = str(reconciliation_payload.get("reconciliation_id") or "")
    reconciliation_status = str(
        reconciliation_payload.get("reconciliation_status")
        or RECONCILIATION_INCOMPLETE
    )
    evidence_hash_chain_id = str(
        reconciliation_payload.get("evidence_hash_chain_id") or ""
    )
    replay_ids = _string_list(reconciliation_payload.get("replay_correlation_ids"))
    audit_ids = _string_list(reconciliation_payload.get("audit_action_ids"))
    incidents = _string_list(incident_ids)
    no_go_ids = _string_list(no_go_decision_ids)
    archive_export_id = _archive_export_id(
        {
            "generated_at_utc": generated,
            "reconciliation_id": reconciliation_id,
            "reconciliation_status": reconciliation_status,
            "evidence_hash_chain_id": evidence_hash_chain_id,
            "incident_ids": incidents,
            "no_go_decision_ids": no_go_ids,
        }
    )
    export = PostPilotEvidenceArchiveExport(
        archive_export_id=archive_export_id,
        generated_at_utc=generated,
        broker=broker,
        symbol=symbol,
        pilot_scope=_mapping(reconciliation_payload.get("pilot_scope")),
        reconciliation_id=reconciliation_id,
        reconciliation_status=reconciliation_status,
        evidence_hash_chain_id=evidence_hash_chain_id,
        replay_correlation_ids=replay_ids,
        audit_action_ids=audit_ids,
        incident_ids=incidents,
        no_go_decision_ids=no_go_ids,
        broker_balance_summary=_broker_balance_summary(
            reconciliation_payload,
            broker_balance_summary,
        ),
        css_ledger_summary=_css_ledger_summary(
            reconciliation_payload,
            css_ledger_summary,
        ),
        fee_slippage_summary=_summary_or_default(
            fee_slippage_summary,
            {
                "fees_recorded": False,
                "slippage_recorded": False,
                "review_required": True,
            },
        ),
        fill_summary=_summary_or_default(
            fill_summary,
            {
                "fill_status": "PENDING_REVIEW",
                "expected_order_count": reconciliation_payload.get(
                    "expected_order_count",
                    1,
                ),
                "observed_order_count": reconciliation_payload.get(
                    "observed_order_count",
                ),
                "review_required": True,
            },
        ),
        operator_conclusion=str(_json_safe(operator_conclusion or "")),
        safety_disclaimer=_SAFETY_DISCLAIMER,
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        archive_write_performed=False,
        redaction_required=True,
        audit_payload=_audit_payload(
            archive_export_id=archive_export_id,
            generated_at_utc=generated,
            reconciliation_id=reconciliation_id,
            reconciliation_status=reconciliation_status,
            evidence_hash_chain_id=evidence_hash_chain_id,
            replay_correlation_ids=replay_ids,
            audit_action_ids=audit_ids,
            incident_ids=incidents,
            no_go_decision_ids=no_go_ids,
        ),
        source_metadata={
            "source": "dashboard.runtime.post_pilot_evidence_archive_export",
            "read_only": True,
            "export_only": True,
            "evidence_only": True,
            "json_safe": True,
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
    return _json_safe(export.as_dict())


def _broker_balance_summary(
    reconciliation: Mapping[str, Any],
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if override:
        return _json_safe(dict(override))
    return {
        "before": reconciliation.get("broker_balance_before"),
        "after": reconciliation.get("broker_balance_after"),
        "review_required": reconciliation.get("broker_balance_before") is None
        or reconciliation.get("broker_balance_after") is None,
    }


def _css_ledger_summary(
    reconciliation: Mapping[str, Any],
    override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if override:
        return _json_safe(dict(override))
    return {
        "before": reconciliation.get("css_balance_before"),
        "after": reconciliation.get("css_balance_after"),
        "review_required": reconciliation.get("css_balance_before") is None
        or reconciliation.get("css_balance_after") is None,
    }


def _summary_or_default(
    summary: Mapping[str, Any] | None,
    default: Mapping[str, Any],
) -> dict[str, Any]:
    if summary:
        return _json_safe(dict(summary))
    return _json_safe(dict(default))


def _audit_payload(
    *,
    archive_export_id: str,
    generated_at_utc: str,
    reconciliation_id: str,
    reconciliation_status: str,
    evidence_hash_chain_id: str,
    replay_correlation_ids: Sequence[str],
    audit_action_ids: Sequence[str],
    incident_ids: Sequence[str],
    no_go_decision_ids: Sequence[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "archive_export_id": archive_export_id,
            "generated_at_utc": generated_at_utc,
            "reconciliation_id": reconciliation_id,
            "reconciliation_status": reconciliation_status,
            "evidence_hash_chain_id": evidence_hash_chain_id,
            "replay_correlation_ids": list(replay_correlation_ids),
            "audit_action_ids": list(audit_action_ids),
            "incident_ids": list(incident_ids),
            "no_go_decision_ids": list(no_go_decision_ids),
            "review_only": True,
            "export_only": True,
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


def _archive_export_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"POSTARCH-{digest}"


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
    "POST_PILOT_ARCHIVE_EXPORT_PAYLOAD_VERSION",
    "PostPilotEvidenceArchiveExport",
    "build_post_pilot_evidence_archive_export_payload",
]
