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
    APPROVED_ORDER_TYPES,
    APPROVED_SYMBOLS,
    MAX_PILOT_CAPITAL_AMOUNT,
    MAX_SLIPPAGE_PCT,
)


MICRO_LIVE_PRE_PILOT_GO_NO_GO_PAYLOAD_VERSION = (
    "css.micro_live_pre_pilot_go_no_go.v1"
)

GO_NO_GO_NO_GO = "NO_GO"
GO_NO_GO_REVIEW_REQUIRED = "REVIEW_REQUIRED"
GO_NO_GO_ELIGIBLE = "ELIGIBLE_FOR_MANUAL_GO"

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
    "order_submit_allowed",
    "persistence_enabled",
    "trading_armed",
}


@dataclass(frozen=True)
class PrePilotGoNoGoCheck:
    check_id: str
    label: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MicroLivePrePilotGoNoGoRecord:
    record_id: str
    generated_at_utc: str
    pilot_scope: dict[str, Any]
    broker: str
    symbol: str
    order_type: str
    max_pilot_capital_cad: str
    max_slippage_pct: str
    max_live_orders: int
    go_no_go_status: str
    trading_armed: bool
    execution_allowed: bool
    order_submit_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    final_pcnrass_required: bool
    manual_operator_approval_required: bool
    kill_switch_confirmation_required: bool
    passed_checks: list[dict[str, Any]]
    failed_checks: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = MICRO_LIVE_PRE_PILOT_GO_NO_GO_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_micro_live_pre_pilot_go_no_go_payload(
    *,
    pilot_readiness: Mapping[str, Any] | None = None,
    order_intent: Mapping[str, Any] | None = None,
    dry_run_probe: Mapping[str, Any] | None = None,
    operator_approval_gate: Mapping[str, Any] | None = None,
    broker_readiness_confirmation: Mapping[str, Any] | None = None,
    pcnrass_summary: Mapping[str, Any] | bool | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build the final review-only pre-pilot go/no-go evidence record.

    This record does not grant approval, arm trading, submit orders, mutate a
    broker account, activate kill switches, or enable persistence.
    """

    readiness = _mapping(pilot_readiness)
    intent = _mapping(order_intent)
    probe = _mapping(dry_run_probe)
    approval_gate = _mapping(operator_approval_gate)
    broker_confirmation = _mapping(broker_readiness_confirmation)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    checks = _go_no_go_checks(
        pilot_readiness=readiness,
        order_intent=intent,
        dry_run_probe=probe,
        operator_approval_gate=approval_gate,
        broker_readiness_confirmation=broker_confirmation,
        pcnrass_summary=pcnrass_summary,
    )
    failed = [check for check in checks if not check.passed]
    passed = [check for check in checks if check.passed]
    blockers = [
        f"{check.check_id}:{check.message}"
        for check in failed
        if check.severity in {"BLOCKER", "SAFETY"}
    ]
    status = _go_no_go_status(failed)
    warnings = _warnings(status, failed)
    record_id = _record_id(
        {
            "generated_at_utc": generated,
            "status": status,
            "failed_checks": [check.check_id for check in failed],
        }
    )

    record = MicroLivePrePilotGoNoGoRecord(
        record_id=record_id,
        generated_at_utc=generated,
        pilot_scope=_pilot_scope(),
        broker=CANONICAL_BROKER,
        symbol=CANONICAL_SYMBOL,
        order_type="limit",
        max_pilot_capital_cad=format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        max_slippage_pct=format(MAX_SLIPPAGE_PCT, "f"),
        max_live_orders=1,
        go_no_go_status=status,
        trading_armed=False,
        execution_allowed=False,
        order_submit_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        final_pcnrass_required=True,
        manual_operator_approval_required=True,
        kill_switch_confirmation_required=True,
        passed_checks=[check.as_dict() for check in passed],
        failed_checks=[check.as_dict() for check in failed],
        blockers=blockers,
        warnings=warnings,
        audit_payload=_audit_payload(
            record_id=record_id,
            generated_at_utc=generated,
            go_no_go_status=status,
            blockers=blockers,
        ),
        source_metadata={
            "source": "dashboard.runtime.micro_live_pre_pilot_go_no_go",
            "read_only": True,
            "review_only": True,
            "evidence_only": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_approval_grant_endpoint": True,
            "no_trading_arm": True,
            "no_kill_switch_activation": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(record.as_dict())


def _go_no_go_checks(
    *,
    pilot_readiness: Mapping[str, Any],
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    operator_approval_gate: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
    pcnrass_summary: Mapping[str, Any] | bool | None,
) -> list[PrePilotGoNoGoCheck]:
    return [
        _check(
            "pilot_readiness_present",
            "Pilot readiness evidence is present",
            bool(pilot_readiness),
            "REVIEW",
            "Pilot readiness evidence is required for final go/no-go review.",
        ),
        _check(
            "pilot_readiness_review_only",
            "Pilot readiness remains review-only",
            not _bool(pilot_readiness.get("unrestricted_live_trading_enabled"))
            and not _bool(pilot_readiness.get("automatic_live_execution_enabled")),
            "SAFETY",
            "Pilot readiness must not enable unrestricted or automatic live trading.",
        ),
        _check(
            "order_intent_present",
            "Order intent evidence is present",
            bool(order_intent),
            "REVIEW",
            "Order intent evidence is required for final go/no-go review.",
        ),
        _check(
            "order_intent_non_executing",
            "Order intent is non-executing",
            order_intent.get("execution_allowed") is False
            and order_intent.get("source_metadata", {}).get("no_order_placement")
            is True,
            "SAFETY",
            "Order intent must not allow execution or order placement.",
        ),
        _check(
            "dry_run_probe_present",
            "Coinbase dry-run probe evidence is present",
            bool(dry_run_probe),
            "BLOCKER",
            "Coinbase non-executing dry-run probe is required.",
        ),
        _check(
            "dry_run_probe_non_executing",
            "Dry-run probe is non-executing",
            dry_run_probe.get("order_submit_allowed") is False
            and dry_run_probe.get("broker_mutation_allowed") is False
            and str(dry_run_probe.get("probe_mode") or "") == "non_executing",
            "SAFETY",
            "Dry-run probe must prove no submit and no broker mutation.",
        ),
        _check(
            "dry_run_probe_passed",
            "Dry-run probe passed",
            str(dry_run_probe.get("validation_status") or "").upper() == "PASS",
            "BLOCKER",
            "Dry-run probe must pass before final go/no-go review.",
        ),
        _check(
            "operator_approval_gate_present",
            "Operator approval gate evidence is present",
            bool(operator_approval_gate),
            "REVIEW",
            "Operator approval gate evidence is required.",
        ),
        _check(
            "operator_approval_not_granted_by_system",
            "Operator approval is still manual and not granted by system",
            operator_approval_gate.get("operator_approval_required") is True
            and operator_approval_gate.get("operator_approval_granted") is False,
            "SAFETY",
            "System must not grant operator approval.",
        ),
        _check(
            "approval_grant_endpoint_absent",
            "Approval-grant endpoint is absent",
            operator_approval_gate.get("approval_grant_endpoint_exists") is False,
            "SAFETY",
            "No endpoint may grant approval or arm trading.",
        ),
        _check(
            "kill_switch_confirmation_required",
            "Kill-switch confirmation remains required",
            operator_approval_gate.get("requires_kill_switch_verification") is True,
            "REVIEW",
            "Immediate pre-pilot kill-switch confirmation remains required.",
        ),
        _check(
            "kill_switch_pre_pilot_confirmation_present",
            "Immediate pre-pilot kill-switch confirmation present",
            _mapping(operator_approval_gate.get("kill_switch_evidence")).get(
                "pre_pilot_confirmation_present"
            )
            is True,
            "REVIEW",
            "Kill switch must be confirmed immediately before manual go.",
        ),
        _check(
            "trading_not_armed",
            "Trading remains unarmed",
            operator_approval_gate.get("trading_armed") is False,
            "SAFETY",
            "Trading must not be armed by go/no-go evidence.",
        ),
        _check(
            "broker_readiness_confirmation_present",
            "Broker readiness confirmation is present",
            bool(broker_readiness_confirmation),
            "BLOCKER",
            "Broker readiness confirmation evidence is required.",
        ),
        _check(
            "broker_readiness_confirmation_eligible",
            "Broker readiness confirmation is eligible",
            str(broker_readiness_confirmation.get("readiness_status") or "")
            == "ELIGIBLE_FOR_MANUAL_APPROVAL",
            "BLOCKER",
            "Broker readiness confirmation must be eligible for manual approval.",
        ),
        _check(
            "broker_confirmation_non_executing",
            "Broker confirmation is non-executing",
            broker_readiness_confirmation.get("order_submit_allowed") is False
            and broker_readiness_confirmation.get("broker_mutation_allowed") is False,
            "SAFETY",
            "Broker confirmation must not allow submit or mutation.",
        ),
        _check(
            "persistence_disabled",
            "Persistence remains disabled",
            pilot_readiness.get("persistence_enabled") is False
            and _broker_confirmation_persistence_disabled(
                broker_readiness_confirmation
            ),
            "SAFETY",
            "Persistence must remain disabled for final go/no-go evidence.",
        ),
        _check(
            "scope_consistent",
            "All evidence agrees on Coinbase BTC-USD limit pilot scope",
            _scope_consistent(order_intent, dry_run_probe, broker_readiness_confirmation),
            "BLOCKER",
            "Pilot evidence must consistently reference Coinbase Advanced, BTC-USD, and limit order scope.",
        ),
        _check(
            "capital_and_risk_caps_consistent",
            "All evidence agrees on capital, slippage, and order caps",
            _caps_consistent(order_intent, dry_run_probe, broker_readiness_confirmation),
            "BLOCKER",
            "Pilot evidence must consistently preserve CAD 15, 0.35%, and one-order caps.",
        ),
        _check(
            "final_pcnrass_required",
            "Final PCNRASS release check remains required",
            operator_approval_gate.get("requires_final_pcnrass_check") is True,
            "REVIEW",
            "Final PCNRASS release check remains required immediately before pilot.",
        ),
        _check(
            "final_pcnrass_passed",
            "Final PCNRASS release check currently passes",
            _pcnrass_passed(pcnrass_summary),
            "REVIEW",
            "Current PCNRASS release check must pass before manual go.",
        ),
    ]


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str,
    message: str,
) -> PrePilotGoNoGoCheck:
    return PrePilotGoNoGoCheck(
        check_id=check_id,
        label=label,
        passed=bool(passed),
        severity=severity,
        message=message,
    )


def _go_no_go_status(failed: list[PrePilotGoNoGoCheck]) -> str:
    if any(check.severity in {"BLOCKER", "SAFETY"} for check in failed):
        return GO_NO_GO_NO_GO
    if failed:
        return GO_NO_GO_REVIEW_REQUIRED
    return GO_NO_GO_ELIGIBLE


def _warnings(status: str, failed: list[PrePilotGoNoGoCheck]) -> list[str]:
    warnings = [
        "NO_TRADING_IS_ARMED_FROM_THIS_PAGE",
        "NO_APPROVAL_GRANTED_BY_GO_NO_GO_RECORD",
        "NO_ORDER_WAS_SUBMITTED",
        "NO_BROKER_STATE_WAS_MODIFIED",
        "PERSISTENCE_REMAINS_DISABLED",
        "MANUAL_OPERATOR_APPROVAL_REQUIRED",
        "KILL_SWITCH_CONFIRMATION_REQUIRED_IMMEDIATELY_BEFORE_PILOT",
        "FINAL_PCNRASS_CHECK_REQUIRED_IMMEDIATELY_BEFORE_PILOT",
    ]
    if status != GO_NO_GO_ELIGIBLE:
        warnings.append("PRE_PILOT_GO_NO_GO_NOT_ELIGIBLE")
    if any(check.severity == "REVIEW" for check in failed):
        warnings.append("REVIEW_ITEMS_REMAIN")
    if any(check.severity in {"BLOCKER", "SAFETY"} for check in failed):
        warnings.append("SAFETY_BLOCKERS_REMAIN")
    return list(dict.fromkeys(warnings))


def _scope_consistent(
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
) -> bool:
    brokers = [
        order_intent.get("broker"),
        dry_run_probe.get("broker"),
        broker_readiness_confirmation.get("broker"),
    ]
    symbols = [
        order_intent.get("symbol"),
        dry_run_probe.get("symbol"),
        broker_readiness_confirmation.get("supported_symbol"),
    ]
    order_types = [
        order_intent.get("order_type"),
        dry_run_probe.get("order_type"),
        broker_readiness_confirmation.get("supported_order_type"),
    ]
    return all(_broker_is_coinbase(value) for value in brokers) and all(
        str(value or "").strip().upper() in APPROVED_SYMBOLS for value in symbols
    ) and all(
        str(value or "").strip().lower() in APPROVED_ORDER_TYPES
        for value in order_types
    )


def _caps_consistent(
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
) -> bool:
    capital_values = [
        order_intent.get("max_pilot_capital_cad"),
        dry_run_probe.get("max_pilot_capital_cad"),
        broker_readiness_confirmation.get("max_pilot_capital_cad"),
    ]
    slippage_values = [
        order_intent.get("max_slippage_pct"),
        dry_run_probe.get("max_slippage_pct"),
        broker_readiness_confirmation.get("max_slippage_pct"),
    ]
    order_counts = [
        order_intent.get("max_live_orders"),
        dry_run_probe.get("max_live_orders"),
        broker_readiness_confirmation.get("max_live_orders"),
    ]
    return all(
        _decimal(value) <= MAX_PILOT_CAPITAL_AMOUNT for value in capital_values
    ) and all(
        _decimal(value) <= MAX_SLIPPAGE_PCT for value in slippage_values
    ) and all(_safe_int(value) <= 1 for value in order_counts)


def _pilot_scope() -> dict[str, Any]:
    return {
        "broker": CANONICAL_BROKER,
        "symbol": CANONICAL_SYMBOL,
        "order_type": "limit",
        "max_pilot_capital_cad": format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        "max_slippage_pct": format(MAX_SLIPPAGE_PCT, "f"),
        "max_live_orders": 1,
        "review_only": True,
    }


def _broker_confirmation_persistence_disabled(
    broker_readiness_confirmation: Mapping[str, Any],
) -> bool:
    audit_payload = _mapping(broker_readiness_confirmation.get("audit_payload"))
    return broker_readiness_confirmation.get("persistence_enabled") is False or (
        audit_payload.get("persistence_enabled") is False
    )


def _audit_payload(
    *,
    record_id: str,
    generated_at_utc: str,
    go_no_go_status: str,
    blockers: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "micro_live_pre_pilot_go_no_go_created",
            "record_id": record_id,
            "generated_at_utc": generated_at_utc,
            "go_no_go_status": go_no_go_status,
            "broker": CANONICAL_BROKER,
            "symbol": CANONICAL_SYMBOL,
            "order_type": "limit",
            "trading_armed": False,
            "execution_allowed": False,
            "order_submit_allowed": False,
            "broker_mutation_allowed": False,
            "persistence_enabled": False,
            "approval_granted": False,
            "order_placed": False,
            "broker_mutated": False,
            "blockers": blockers,
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _broker_is_coinbase(value: Any) -> bool:
    return _normalize_broker(value) in {"coinbase", "coinbase_advanced"}


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


def _record_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"MLGONOGO-{digest}"


__all__ = [
    "GO_NO_GO_ELIGIBLE",
    "GO_NO_GO_NO_GO",
    "GO_NO_GO_REVIEW_REQUIRED",
    "MICRO_LIVE_PRE_PILOT_GO_NO_GO_PAYLOAD_VERSION",
    "MicroLivePrePilotGoNoGoRecord",
    "PrePilotGoNoGoCheck",
    "build_micro_live_pre_pilot_go_no_go_payload",
]
