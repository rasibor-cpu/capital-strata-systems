from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dashboard.runtime.micro_live_pilot_order_intent import (
    CANONICAL_BROKER,
    CANONICAL_SYMBOL,
)
from dashboard.runtime.micro_live_pilot_readiness import (
    APPROVED_BROKER_KEYS,
    APPROVED_ORDER_TYPES,
    APPROVED_SYMBOLS,
    MAX_PILOT_CAPITAL_AMOUNT,
    MAX_SLIPPAGE_PCT,
)


MICRO_LIVE_BROKER_READINESS_CONFIRMATION_PAYLOAD_VERSION = (
    "css.micro_live_broker_readiness_confirmation.v1"
)

BROKER_CONFIRMATION_NOT_READY = "NOT_READY"
BROKER_CONFIRMATION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
BROKER_CONFIRMATION_ELIGIBLE = "ELIGIBLE_FOR_MANUAL_APPROVAL"

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
    "credential_presence_expected",
    "credential_secret_exposed",
    "order_submit_allowed",
}


@dataclass(frozen=True)
class BrokerReadinessConfirmationCheck:
    check_id: str
    label: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MicroLiveBrokerReadinessConfirmation:
    confirmation_id: str
    generated_at_utc: str
    broker: str
    broker_connection_expected: bool
    broker_mutation_allowed: bool
    order_submit_allowed: bool
    credential_presence_expected: bool
    credential_secret_exposed: bool
    supported_symbol: str
    supported_order_type: str
    max_pilot_capital_cad: str
    max_slippage_pct: str
    max_live_orders: int
    readiness_status: str
    passed_checks: list[dict[str, Any]]
    failed_checks: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = MICRO_LIVE_BROKER_READINESS_CONFIRMATION_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_micro_live_broker_readiness_confirmation_payload(
    *,
    dashboard_payload: Mapping[str, Any] | None = None,
    dry_run_probe: Mapping[str, Any] | None = None,
    operator_approval_gate: Mapping[str, Any] | None = None,
    persistence_checklist: Mapping[str, Any] | None = None,
    pcnrass_summary: Mapping[str, Any] | bool | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build non-executing broker-readiness evidence for micro-live review.

    This function does not call Coinbase, does not submit an order, does not
    mutate broker/account state, and does not arm live trading.
    """

    dashboard = _mapping(dashboard_payload)
    probe = _mapping(dry_run_probe)
    approval_gate = _mapping(operator_approval_gate)
    persistence = _mapping(persistence_checklist)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    credential_secret_exposed = _contains_secret_values(
        {
            "dashboard_payload": dashboard,
            "dry_run_probe": probe,
            "operator_approval_gate": approval_gate,
            "persistence_checklist": persistence,
        }
    )
    checks = _confirmation_checks(
        dashboard_payload=dashboard,
        dry_run_probe=probe,
        operator_approval_gate=approval_gate,
        persistence_checklist=persistence,
        pcnrass_summary=pcnrass_summary,
        credential_secret_exposed=credential_secret_exposed,
    )
    failed = [check for check in checks if not check.passed]
    passed = [check for check in checks if check.passed]
    blockers = [
        f"{check.check_id}:{check.message}"
        for check in failed
        if check.severity in {"BLOCKER", "SAFETY"}
    ]
    status = _readiness_status(failed)
    warnings = _warnings(status, failed)
    confirmation_id = _confirmation_id(
        {
            "generated_at_utc": generated,
            "status": status,
            "failed_checks": [check.check_id for check in failed],
        }
    )

    confirmation = MicroLiveBrokerReadinessConfirmation(
        confirmation_id=confirmation_id,
        generated_at_utc=generated,
        broker=CANONICAL_BROKER,
        broker_connection_expected=True,
        broker_mutation_allowed=False,
        order_submit_allowed=False,
        credential_presence_expected=True,
        credential_secret_exposed=credential_secret_exposed,
        supported_symbol=CANONICAL_SYMBOL,
        supported_order_type="limit",
        max_pilot_capital_cad=format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        max_slippage_pct=format(MAX_SLIPPAGE_PCT, "f"),
        max_live_orders=1,
        readiness_status=status,
        passed_checks=[check.as_dict() for check in passed],
        failed_checks=[check.as_dict() for check in failed],
        blockers=blockers,
        warnings=warnings,
        audit_payload=_audit_payload(
            confirmation_id=confirmation_id,
            generated_at_utc=generated,
            readiness_status=status,
            blockers=blockers,
        ),
        source_metadata={
            "source": "dashboard.runtime.micro_live_broker_readiness_confirmation",
            "read_only": True,
            "review_only": True,
            "evidence_only": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_trading_arm": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(confirmation.as_dict())


def _confirmation_checks(
    *,
    dashboard_payload: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    operator_approval_gate: Mapping[str, Any],
    persistence_checklist: Mapping[str, Any],
    pcnrass_summary: Mapping[str, Any] | bool | None,
    credential_secret_exposed: bool,
) -> list[BrokerReadinessConfirmationCheck]:
    broker_summary = _mapping(dashboard_payload.get("broker_summary"))
    selected_broker = broker_summary.get("selected_broker")
    selected_broker_ok = _broker_is_coinbase(selected_broker)
    if not str(selected_broker or "").strip():
        selected_broker_ok = _broker_is_coinbase(dry_run_probe.get("broker"))

    broker_connection_confirmed = (
        _bool(broker_summary.get("connected"))
        and not _bool(broker_summary.get("missing_credentials"))
        and str(broker_summary.get("readiness_status") or "").strip().upper()
        == "BROKER_READY"
    )
    credentials_present_confirmed = (
        bool(broker_summary) and not _bool(broker_summary.get("missing_credentials"))
    )
    persistence_disabled = _persistence_disabled(
        dashboard_payload,
        operator_approval_gate,
        persistence_checklist,
    )

    return [
        _check(
            "coinbase_advanced_selected",
            "Coinbase Advanced selected",
            selected_broker_ok,
            "BLOCKER",
            "Final broker readiness confirmation is restricted to Coinbase Advanced.",
        ),
        _check(
            "broker_connection_expected",
            "Broker connection is expected",
            True,
            "REVIEW",
            "Coinbase broker connection is expected before any pilot.",
        ),
        _check(
            "broker_connection_confirmed",
            "Broker connection readiness confirmed",
            broker_connection_confirmed,
            "REVIEW",
            "Broker must report connected, credentialed, and BROKER_READY immediately before pilot.",
        ),
        _check(
            "credential_presence_expected",
            "Credential presence is expected",
            True,
            "REVIEW",
            "Credential presence is expected, without exposing secrets.",
        ),
        _check(
            "credential_presence_confirmed",
            "Credential presence confirmed without exposure",
            credentials_present_confirmed,
            "REVIEW",
            "Credentials must be present immediately before pilot and must not be exposed.",
        ),
        _check(
            "credential_secret_not_exposed",
            "Credential secret is not exposed",
            not credential_secret_exposed,
            "SAFETY",
            "Broker readiness payload must not expose credential-shaped values.",
        ),
        _check(
            "btc_usd_pilot_scope",
            "BTC-USD pilot scope",
            str(dry_run_probe.get("symbol") or "").strip().upper()
            in APPROVED_SYMBOLS,
            "BLOCKER",
            "Pilot broker readiness is restricted to BTC-USD.",
        ),
        _check(
            "limit_order_only_scope",
            "Limit-order-only scope",
            str(dry_run_probe.get("order_type") or "").strip().lower()
            in APPROVED_ORDER_TYPES,
            "BLOCKER",
            "Pilot broker readiness is restricted to limit orders.",
        ),
        _check(
            "capital_cap_locked",
            "Pilot capital cap remains CAD 15",
            _decimal(dry_run_probe.get("max_pilot_capital_cad"))
            <= MAX_PILOT_CAPITAL_AMOUNT,
            "BLOCKER",
            "Pilot capital cap must not exceed CAD 15.",
        ),
        _check(
            "slippage_cap_locked",
            "Pilot slippage cap remains 0.35%",
            _decimal(dry_run_probe.get("max_slippage_pct")) <= MAX_SLIPPAGE_PCT,
            "BLOCKER",
            "Pilot slippage cap must not exceed 0.35%.",
        ),
        _check(
            "max_live_orders_one",
            "Max one live order",
            _safe_int(dry_run_probe.get("max_live_orders")) <= 1,
            "BLOCKER",
            "Pilot cannot exceed one live order.",
        ),
        _check(
            "no_order_submit_path_allowed",
            "No order-submit path allowed",
            dry_run_probe.get("order_submit_allowed") is False,
            "SAFETY",
            "Broker readiness confirmation must not allow order submission.",
        ),
        _check(
            "no_broker_mutation_allowed",
            "No broker mutation allowed",
            dry_run_probe.get("broker_mutation_allowed") is False,
            "SAFETY",
            "Broker readiness confirmation must not mutate broker state.",
        ),
        _check(
            "kill_switch_verification_still_required",
            "Kill-switch verification remains required",
            operator_approval_gate.get("requires_kill_switch_verification") is True,
            "REVIEW",
            "Kill-switch verification is still required before any pilot.",
        ),
        _check(
            "manual_operator_approval_still_required",
            "Manual operator approval remains required",
            operator_approval_gate.get("operator_approval_required") is True
            and operator_approval_gate.get("operator_approval_granted") is False,
            "REVIEW",
            "Manual operator approval is still required and is not granted here.",
        ),
        _check(
            "trading_not_armed",
            "Trading remains unarmed",
            operator_approval_gate.get("trading_armed") is False,
            "SAFETY",
            "Broker readiness confirmation must not arm trading.",
        ),
        _check(
            "final_pcnrass_check_still_required",
            "Final PCNRASS release check remains required",
            operator_approval_gate.get("requires_final_pcnrass_check") is True,
            "REVIEW",
            "Final PCNRASS release check is still required before pilot.",
        ),
        _check(
            "final_pcnrass_check_passed",
            "Final PCNRASS check currently passes",
            _pcnrass_passed(pcnrass_summary),
            "REVIEW",
            "Current PCNRASS release check must pass before broker confirmation.",
        ),
        _check(
            "persistence_disabled",
            "Persistence remains disabled",
            persistence_disabled,
            "SAFETY",
            "Runtime event persistence must remain disabled for this evidence package.",
        ),
    ]


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str,
    message: str,
) -> BrokerReadinessConfirmationCheck:
    return BrokerReadinessConfirmationCheck(
        check_id=check_id,
        label=label,
        passed=bool(passed),
        severity=severity,
        message=message,
    )


def _readiness_status(failed: list[BrokerReadinessConfirmationCheck]) -> str:
    if any(check.severity in {"BLOCKER", "SAFETY"} for check in failed):
        return BROKER_CONFIRMATION_NOT_READY
    if failed:
        return BROKER_CONFIRMATION_REVIEW_REQUIRED
    return BROKER_CONFIRMATION_ELIGIBLE


def _warnings(
    status: str,
    failed: list[BrokerReadinessConfirmationCheck],
) -> list[str]:
    warnings = [
        "NO_BROKER_STATE_WAS_MODIFIED",
        "NO_ORDER_WAS_SUBMITTED",
        "BROKER_READINESS_EVIDENCE_ONLY",
        "MANUAL_OPERATOR_APPROVAL_STILL_REQUIRED",
        "KILL_SWITCH_VERIFICATION_STILL_REQUIRED",
        "FINAL_PCNRASS_CHECK_REQUIRED_IMMEDIATELY_BEFORE_PILOT",
        "PERSISTENCE_REMAINS_DISABLED",
    ]
    if status != BROKER_CONFIRMATION_ELIGIBLE:
        warnings.append("BROKER_CONFIRMATION_NOT_READY_FOR_MANUAL_APPROVAL")
    if any(check.severity == "REVIEW" for check in failed):
        warnings.append("REVIEW_ITEMS_REMAIN")
    if any(check.severity in {"BLOCKER", "SAFETY"} for check in failed):
        warnings.append("SAFETY_BLOCKERS_REMAIN")
    return list(dict.fromkeys(warnings))


def _audit_payload(
    *,
    confirmation_id: str,
    generated_at_utc: str,
    readiness_status: str,
    blockers: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "micro_live_broker_readiness_confirmation_created",
            "confirmation_id": confirmation_id,
            "generated_at_utc": generated_at_utc,
            "broker": CANONICAL_BROKER,
            "supported_symbol": CANONICAL_SYMBOL,
            "supported_order_type": "limit",
            "readiness_status": readiness_status,
            "broker_connection_expected": True,
            "credential_presence_expected": True,
            "order_submit_allowed": False,
            "broker_mutation_allowed": False,
            "order_placed": False,
            "broker_mutated": False,
            "persistence_enabled": False,
            "blockers": blockers,
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _persistence_disabled(*payloads: Mapping[str, Any]) -> bool:
    flags = [
        payload.get("persistence_enabled")
        for payload in payloads
        if "persistence_enabled" in payload
    ]
    writes_performed = any(_bool(payload.get("writes_performed")) for payload in payloads)
    return bool(flags) and all(flag is False for flag in flags) and not writes_performed


def _broker_is_coinbase(value: Any) -> bool:
    return _normalize_broker(value) in APPROVED_BROKER_KEYS


def _normalize_broker(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"coinbaseadvanced", "coinbase_advanced", "coinbase_advanced_trade"}:
        return "coinbase_advanced"
    return text


def _pcnrass_passed(summary: Mapping[str, Any] | bool | None) -> bool:
    if isinstance(summary, bool):
        return summary
    if isinstance(summary, Mapping):
        return bool(summary.get("passed"))
    return False


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "ready"}
    return bool(value)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


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


def _contains_secret_values(value: Any) -> bool:
    serialized = json.dumps(value, sort_keys=True, default=str).lower()
    return any(marker in serialized for marker in _SENSITIVE_VALUE_MARKERS)


def _confirmation_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"MLBROKER-{digest}"


__all__ = [
    "BROKER_CONFIRMATION_ELIGIBLE",
    "BROKER_CONFIRMATION_NOT_READY",
    "BROKER_CONFIRMATION_REVIEW_REQUIRED",
    "MICRO_LIVE_BROKER_READINESS_CONFIRMATION_PAYLOAD_VERSION",
    "BrokerReadinessConfirmationCheck",
    "MicroLiveBrokerReadinessConfirmation",
    "build_micro_live_broker_readiness_confirmation_payload",
]
