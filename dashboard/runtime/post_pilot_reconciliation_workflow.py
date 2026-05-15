from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from dashboard.runtime.micro_live_pilot_order_intent import (
    CANONICAL_BROKER,
    CANONICAL_SYMBOL,
)
from dashboard.runtime.micro_live_pilot_readiness import (
    MAX_PILOT_CAPITAL_AMOUNT,
    MAX_SLIPPAGE_PCT,
)


POST_PILOT_RECONCILIATION_PAYLOAD_VERSION = (
    "css.post_pilot_reconciliation_workflow.v1"
)

RECONCILIATION_MATCH = "MATCH"
RECONCILIATION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
RECONCILIATION_MISMATCH = "MISMATCH"
RECONCILIATION_INCOMPLETE = "INCOMPLETE"

EXPECTED_POSITION_STATE = "FLAT_OR_CLOSED"

_BALANCE_TOLERANCE = Decimal("0.01")
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
    "persistence_enabled",
    "redaction_required",
    "secrets_redacted",
    "trading_armed",
}
_BALANCE_KEYS = (
    "total_equity",
    "equity",
    "cash_balance",
    "cash",
    "balance",
    "account_equity",
    "net_liquidation",
)


@dataclass(frozen=True)
class PostPilotReconciliationEvidence:
    reconciliation_id: str
    generated_at_utc: str
    broker: str
    symbol: str
    pilot_scope: dict[str, Any]
    broker_balance_before: Any
    broker_balance_after: Any
    css_balance_before: Any
    css_balance_after: Any
    expected_order_count: int
    observed_order_count: int | None
    expected_position_state: str
    observed_position_state: str
    replay_correlation_ids: list[str]
    audit_action_ids: list[str]
    evidence_hash_chain_id: str
    reconciliation_status: str
    mismatch_flags: list[str]
    warnings: list[str]
    notes: str
    trading_armed: bool
    execution_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    redaction_required: bool
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = POST_PILOT_RECONCILIATION_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_post_pilot_reconciliation_payload(
    *,
    broker_balance_before: Mapping[str, Any] | int | float | str | Decimal | None = None,
    broker_balance_after: Mapping[str, Any] | int | float | str | Decimal | None = None,
    css_balance_before: Mapping[str, Any] | int | float | str | Decimal | None = None,
    css_balance_after: Mapping[str, Any] | int | float | str | Decimal | None = None,
    expected_order_count: int = 1,
    observed_order_count: int | None = None,
    expected_position_state: str = EXPECTED_POSITION_STATE,
    observed_position_state: str = "",
    replay_correlation_ids: Sequence[str] | None = None,
    audit_action_ids: Sequence[str] | None = None,
    evidence_hash_chain_id: str = "",
    broker: str = CANONICAL_BROKER,
    symbol: str = CANONICAL_SYMBOL,
    notes: str = "",
    generated_at_utc: str = "",
) -> dict[str, Any]:
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    replay_ids = _string_list(replay_correlation_ids)
    audit_ids = _string_list(audit_action_ids)
    mismatch_flags: list[str] = []
    warnings: list[str] = []

    mismatch_flags.extend(
        compare_balance_deltas(
            broker_balance_before=broker_balance_before,
            broker_balance_after=broker_balance_after,
            css_balance_before=css_balance_before,
            css_balance_after=css_balance_after,
        )
    )
    mismatch_flags.extend(
        compare_order_counts(
            expected_order_count=expected_order_count,
            observed_order_count=observed_order_count,
        )
    )
    mismatch_flags.extend(
        compare_position_state(
            expected_position_state=expected_position_state,
            observed_position_state=observed_position_state,
        )
    )

    replay_flags = check_replay_evidence_presence(replay_ids)
    audit_flags = check_audit_evidence_presence(audit_ids)
    warnings.extend(replay_flags)
    warnings.extend(audit_flags)
    if not evidence_hash_chain_id:
        warnings.append("EVIDENCE_HASH_CHAIN_ID_MISSING")

    status = _reconciliation_status(mismatch_flags, warnings)
    reconciliation_id = _reconciliation_id(
        {
            "generated_at_utc": generated,
            "broker": broker,
            "symbol": symbol,
            "status": status,
            "mismatch_flags": mismatch_flags,
            "warnings": warnings,
        }
    )
    evidence = PostPilotReconciliationEvidence(
        reconciliation_id=reconciliation_id,
        generated_at_utc=generated,
        broker=str(broker or CANONICAL_BROKER),
        symbol=str(symbol or CANONICAL_SYMBOL),
        pilot_scope=_pilot_scope(),
        broker_balance_before=_safe_balance(broker_balance_before),
        broker_balance_after=_safe_balance(broker_balance_after),
        css_balance_before=_safe_balance(css_balance_before),
        css_balance_after=_safe_balance(css_balance_after),
        expected_order_count=int(expected_order_count),
        observed_order_count=(
            int(observed_order_count) if observed_order_count is not None else None
        ),
        expected_position_state=str(expected_position_state or EXPECTED_POSITION_STATE),
        observed_position_state=str(observed_position_state or "UNKNOWN"),
        replay_correlation_ids=replay_ids,
        audit_action_ids=audit_ids,
        evidence_hash_chain_id=str(evidence_hash_chain_id or ""),
        reconciliation_status=status,
        mismatch_flags=list(dict.fromkeys(mismatch_flags)),
        warnings=list(dict.fromkeys(warnings)),
        notes=str(_json_safe(notes or "")),
        trading_armed=False,
        execution_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        redaction_required=True,
        audit_payload=_audit_payload(
            reconciliation_id=reconciliation_id,
            generated_at_utc=generated,
            broker=str(broker or CANONICAL_BROKER),
            symbol=str(symbol or CANONICAL_SYMBOL),
            status=status,
            mismatch_flags=mismatch_flags,
            warnings=warnings,
            replay_correlation_ids=replay_ids,
            audit_action_ids=audit_ids,
            evidence_hash_chain_id=str(evidence_hash_chain_id or ""),
        ),
        source_metadata={
            "source": "dashboard.runtime.post_pilot_reconciliation_workflow",
            "read_only": True,
            "evidence_only": True,
            "review_only": True,
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
    return _json_safe(evidence.as_dict())


def compare_balance_deltas(
    *,
    broker_balance_before: Mapping[str, Any] | int | float | str | Decimal | None,
    broker_balance_after: Mapping[str, Any] | int | float | str | Decimal | None,
    css_balance_before: Mapping[str, Any] | int | float | str | Decimal | None,
    css_balance_after: Mapping[str, Any] | int | float | str | Decimal | None,
    tolerance: Decimal | str | int | float = _BALANCE_TOLERANCE,
) -> list[str]:
    broker_before = _balance_value(broker_balance_before)
    broker_after = _balance_value(broker_balance_after)
    css_before = _balance_value(css_balance_before)
    css_after = _balance_value(css_balance_after)
    flags: list[str] = []

    if broker_before is None or broker_after is None:
        flags.append("BROKER_BALANCE_EVIDENCE_INCOMPLETE")
    if css_before is None or css_after is None:
        flags.append("CSS_BALANCE_EVIDENCE_INCOMPLETE")
    if flags:
        return flags

    broker_delta = broker_after - broker_before
    css_delta = css_after - css_before
    if abs(broker_delta - css_delta) > _decimal(tolerance):
        flags.append("BALANCE_DELTA_MISMATCH")
    return flags


def compare_order_counts(
    *,
    expected_order_count: int,
    observed_order_count: int | None,
) -> list[str]:
    if observed_order_count is None:
        return ["ORDER_COUNT_EVIDENCE_INCOMPLETE"]
    if int(expected_order_count) != int(observed_order_count):
        return ["ORDER_COUNT_MISMATCH"]
    return []


def compare_position_state(
    *,
    expected_position_state: str,
    observed_position_state: str,
) -> list[str]:
    expected = _normalize_position_state(expected_position_state)
    observed = _normalize_position_state(observed_position_state)
    if not observed:
        return ["POSITION_STATE_EVIDENCE_INCOMPLETE"]
    if expected != observed:
        return ["POSITION_STATE_MISMATCH"]
    return []


def check_replay_evidence_presence(replay_correlation_ids: Sequence[str] | None) -> list[str]:
    return [] if _string_list(replay_correlation_ids) else ["REPLAY_EVIDENCE_MISSING"]


def check_audit_evidence_presence(audit_action_ids: Sequence[str] | None) -> list[str]:
    return [] if _string_list(audit_action_ids) else ["AUDIT_ACTION_EVIDENCE_MISSING"]


def _reconciliation_status(
    mismatch_flags: Sequence[str],
    warnings: Sequence[str],
) -> str:
    if any(flag.endswith("_MISMATCH") for flag in mismatch_flags):
        return RECONCILIATION_MISMATCH
    if any(flag.endswith("_INCOMPLETE") for flag in mismatch_flags):
        return RECONCILIATION_INCOMPLETE
    if warnings:
        return RECONCILIATION_REVIEW_REQUIRED
    return RECONCILIATION_MATCH


def _pilot_scope() -> dict[str, Any]:
    return {
        "broker": CANONICAL_BROKER,
        "symbol": CANONICAL_SYMBOL,
        "order_type": "limit",
        "max_pilot_capital_cad": format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        "max_slippage_pct": format(MAX_SLIPPAGE_PCT, "f"),
        "max_live_orders": 1,
        "review_only": True,
        "post_pilot_only": True,
    }


def _safe_balance(
    value: Mapping[str, Any] | int | float | str | Decimal | None,
) -> Any:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return _json_safe(value)
    parsed = _balance_value(value)
    return format(parsed, "f") if parsed is not None else _json_safe(value)


def _balance_value(
    value: Mapping[str, Any] | int | float | str | Decimal | None,
) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in _BALANCE_KEYS:
            if key in value:
                return _decimal(value.get(key))
        return None
    return _decimal(value)


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _normalize_position_state(value: str) -> str:
    text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if text in {"FLAT", "CLOSED", "FLAT_OR_CLOSED", "NO_POSITION"}:
        return EXPECTED_POSITION_STATE
    return text


def _string_list(values: Sequence[str] | None) -> list[str]:
    return [
        str(item)
        for item in values or []
        if str(item or "").strip()
    ]


def _audit_payload(
    *,
    reconciliation_id: str,
    generated_at_utc: str,
    broker: str,
    symbol: str,
    status: str,
    mismatch_flags: Sequence[str],
    warnings: Sequence[str],
    replay_correlation_ids: Sequence[str],
    audit_action_ids: Sequence[str],
    evidence_hash_chain_id: str,
) -> dict[str, Any]:
    return _json_safe(
        {
            "reconciliation_id": reconciliation_id,
            "generated_at_utc": generated_at_utc,
            "broker": broker,
            "symbol": symbol,
            "reconciliation_status": status,
            "mismatch_flags": list(mismatch_flags),
            "warnings": list(warnings),
            "replay_correlation_ids": list(replay_correlation_ids),
            "audit_action_ids": list(audit_action_ids),
            "evidence_hash_chain_id": evidence_hash_chain_id,
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


def _reconciliation_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"POSTREC-{digest}"


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
    "EXPECTED_POSITION_STATE",
    "POST_PILOT_RECONCILIATION_PAYLOAD_VERSION",
    "RECONCILIATION_INCOMPLETE",
    "RECONCILIATION_MATCH",
    "RECONCILIATION_MISMATCH",
    "RECONCILIATION_REVIEW_REQUIRED",
    "PostPilotReconciliationEvidence",
    "build_post_pilot_reconciliation_payload",
    "check_audit_evidence_presence",
    "check_replay_evidence_presence",
    "compare_balance_deltas",
    "compare_order_counts",
    "compare_position_state",
]
