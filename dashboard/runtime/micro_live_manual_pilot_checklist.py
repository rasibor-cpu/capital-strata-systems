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


MICRO_LIVE_MANUAL_PILOT_CHECKLIST_PAYLOAD_VERSION = (
    "css.micro_live_manual_pilot_checklist.v1"
)

CHECKLIST_INCOMPLETE = "INCOMPLETE"
CHECKLIST_REVIEW_READY = "REVIEW_READY"
CHECKLIST_ELIGIBLE_FOR_MANUAL_REVIEW = "ELIGIBLE_FOR_MANUAL_REVIEW"

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
    "final_pcnrass_recorded",
    "kill_switch_confirmation_recorded",
    "manual_operator_approval_recorded",
    "order_submit_allowed",
    "persistence_enabled",
    "secrets_redacted",
    "trading_armed",
}


@dataclass(frozen=True)
class ManualPilotChecklistItem:
    item_id: str
    label: str
    completed: bool
    required: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MicroLiveManualPilotChecklist:
    checklist_id: str
    generated_at_utc: str
    pilot_scope: dict[str, Any]
    broker: str
    symbol: str
    order_type: str
    max_pilot_capital_cad: str
    max_slippage_pct: str
    max_live_orders: int
    manual_operator_approval_required: bool
    manual_operator_approval_recorded: bool
    kill_switch_confirmation_required: bool
    kill_switch_confirmation_recorded: bool
    final_pcnrass_required: bool
    final_pcnrass_recorded: bool
    trading_armed: bool
    execution_allowed: bool
    order_submit_allowed: bool
    broker_mutation_allowed: bool
    persistence_enabled: bool
    checklist_status: str
    required_items: list[dict[str, Any]]
    completed_items: list[dict[str, Any]]
    missing_items: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    safety_disclaimer: str
    evidence_chain_summary: dict[str, Any]
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = MICRO_LIVE_MANUAL_PILOT_CHECKLIST_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_micro_live_manual_pilot_checklist_payload(
    *,
    pilot_readiness: Mapping[str, Any] | None = None,
    order_intent: Mapping[str, Any] | None = None,
    dry_run_probe: Mapping[str, Any] | None = None,
    operator_approval_gate: Mapping[str, Any] | None = None,
    broker_readiness_confirmation: Mapping[str, Any] | None = None,
    pre_pilot_go_no_go: Mapping[str, Any] | None = None,
    pcnrass_summary: Mapping[str, Any] | bool | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build a review/export-only manual pilot checklist.

    The checklist records no approvals, arms no trading, places no orders,
    mutates no broker state, activates no kill switch, and enables no
    persistence. It is an operator review package for evidence already created
    by earlier micro-live pilot safety phases.
    """

    readiness = _mapping(pilot_readiness)
    intent = _mapping(order_intent)
    probe = _mapping(dry_run_probe)
    approval_gate = _mapping(operator_approval_gate)
    broker_confirmation = _mapping(broker_readiness_confirmation)
    go_no_go = _mapping(pre_pilot_go_no_go)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    evidence_chain = _evidence_chain_summary(
        pilot_readiness=readiness,
        order_intent=intent,
        dry_run_probe=probe,
        operator_approval_gate=approval_gate,
        broker_readiness_confirmation=broker_confirmation,
        pre_pilot_go_no_go=go_no_go,
    )
    required_items = _checklist_items(
        pilot_readiness=readiness,
        order_intent=intent,
        dry_run_probe=probe,
        operator_approval_gate=approval_gate,
        broker_readiness_confirmation=broker_confirmation,
        pre_pilot_go_no_go=go_no_go,
        pcnrass_summary=pcnrass_summary,
    )
    completed_items = [item for item in required_items if item.completed]
    missing_items = [item for item in required_items if not item.completed]
    blockers = [
        f"{item.item_id}:{item.message}"
        for item in missing_items
        if item.severity in {"BLOCKER", "SAFETY"}
    ]
    status = _checklist_status(required_items)
    warnings = _warnings(status, missing_items)
    checklist_id = _checklist_id(
        {
            "generated_at_utc": generated,
            "status": status,
            "missing_items": [item.item_id for item in missing_items],
        }
    )

    checklist = MicroLiveManualPilotChecklist(
        checklist_id=checklist_id,
        generated_at_utc=generated,
        pilot_scope=_pilot_scope(),
        broker=CANONICAL_BROKER,
        symbol=CANONICAL_SYMBOL,
        order_type="limit",
        max_pilot_capital_cad=format(MAX_PILOT_CAPITAL_AMOUNT, "f"),
        max_slippage_pct=format(MAX_SLIPPAGE_PCT, "f"),
        max_live_orders=1,
        manual_operator_approval_required=True,
        manual_operator_approval_recorded=False,
        kill_switch_confirmation_required=True,
        kill_switch_confirmation_recorded=False,
        final_pcnrass_required=True,
        final_pcnrass_recorded=False,
        trading_armed=False,
        execution_allowed=False,
        order_submit_allowed=False,
        broker_mutation_allowed=False,
        persistence_enabled=False,
        checklist_status=status,
        required_items=[item.as_dict() for item in required_items],
        completed_items=[item.as_dict() for item in completed_items],
        missing_items=[item.as_dict() for item in missing_items],
        blockers=blockers,
        warnings=warnings,
        safety_disclaimer=(
            "No trading is armed by this checklist. Manual approval, immediate "
            "pre-pilot kill-switch confirmation, and final PCNRASS validation "
            "must be recorded outside this read-only export surface before any "
            "pilot decision."
        ),
        evidence_chain_summary=evidence_chain,
        audit_payload=_audit_payload(
            checklist_id=checklist_id,
            generated_at_utc=generated,
            checklist_status=status,
            blockers=blockers,
        ),
        source_metadata={
            "source": "dashboard.runtime.micro_live_manual_pilot_checklist",
            "read_only": True,
            "review_only": True,
            "export_only": True,
            "evidence_only": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_approval_grant_endpoint": True,
            "no_trading_arm": True,
            "no_kill_switch_activation": True,
            "no_persistence_activation": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(checklist.as_dict())


def _checklist_items(
    *,
    pilot_readiness: Mapping[str, Any],
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    operator_approval_gate: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
    pre_pilot_go_no_go: Mapping[str, Any],
    pcnrass_summary: Mapping[str, Any] | bool | None,
) -> list[ManualPilotChecklistItem]:
    return [
        _item(
            "pilot_readiness_present",
            "Pilot readiness evidence is present",
            bool(pilot_readiness),
            "BLOCKER",
            "Pilot readiness evidence must exist before manual review.",
        ),
        _item(
            "order_intent_present",
            "Non-executing order-intent package is present",
            bool(order_intent),
            "BLOCKER",
            "Order-intent evidence must exist before manual review.",
        ),
        _item(
            "coinbase_dry_run_probe_present",
            "Coinbase dry-run probe evidence is present",
            bool(dry_run_probe),
            "BLOCKER",
            "Coinbase dry-run probe evidence must exist before manual review.",
        ),
        _item(
            "operator_approval_gate_present",
            "Operator approval gate evidence is present",
            bool(operator_approval_gate),
            "BLOCKER",
            "Operator approval gate evidence must exist before manual review.",
        ),
        _item(
            "broker_readiness_confirmation_present",
            "Broker readiness confirmation evidence is present",
            bool(broker_readiness_confirmation),
            "BLOCKER",
            "Broker readiness confirmation must exist before manual review.",
        ),
        _item(
            "pre_pilot_go_no_go_present",
            "Final pre-pilot go/no-go evidence is present",
            bool(pre_pilot_go_no_go),
            "BLOCKER",
            "Pre-pilot go/no-go evidence must exist before manual review.",
        ),
        _item(
            "non_executing_controls_confirmed",
            "All evidence remains non-executing",
            _non_executing_controls_confirmed(
                order_intent,
                dry_run_probe,
                operator_approval_gate,
                broker_readiness_confirmation,
                pre_pilot_go_no_go,
            ),
            "SAFETY",
            "Evidence chain must not allow execution, submit, mutation, or arming.",
        ),
        _item(
            "approval_grant_endpoint_absent",
            "No approval-grant endpoint exists",
            operator_approval_gate.get("approval_grant_endpoint_exists") is False,
            "SAFETY",
            "CSS must not expose a route that grants approval or arms trading.",
        ),
        _item(
            "manual_operator_approval_not_recorded_by_system",
            "Manual approval is not recorded by this checklist",
            operator_approval_gate.get("operator_approval_granted") is False,
            "SAFETY",
            "This export must not grant or record operator approval.",
        ),
        _item(
            "kill_switch_confirmation_required",
            "Immediate kill-switch confirmation remains required",
            operator_approval_gate.get("requires_kill_switch_verification") is True
            and pre_pilot_go_no_go.get("kill_switch_confirmation_required") is True,
            "REVIEW",
            "Kill-switch confirmation must remain a pre-pilot manual step.",
        ),
        _item(
            "final_pcnrass_required",
            "Final PCNRASS validation remains required",
            operator_approval_gate.get("requires_final_pcnrass_check") is True
            and pre_pilot_go_no_go.get("final_pcnrass_required") is True,
            "REVIEW",
            "Final PCNRASS validation must remain a pre-pilot manual step.",
        ),
        _item(
            "evidence_chain_consistent",
            "Evidence chain agrees on Coinbase BTC-USD limit scope",
            _scope_consistent(
                order_intent,
                dry_run_probe,
                broker_readiness_confirmation,
                pre_pilot_go_no_go,
            ),
            "BLOCKER",
            "Evidence must consistently reference Coinbase Advanced, BTC-USD, and limit-order scope.",
        ),
        _item(
            "capital_and_risk_caps_consistent",
            "Evidence chain preserves pilot capital, slippage, and order caps",
            _caps_consistent(
                order_intent,
                dry_run_probe,
                broker_readiness_confirmation,
                pre_pilot_go_no_go,
            ),
            "BLOCKER",
            "Evidence must preserve CAD 15, 0.35%, and one-order caps.",
        ),
        _item(
            "dry_run_probe_passed",
            "Coinbase dry-run probe passed",
            str(dry_run_probe.get("validation_status") or "").upper() == "PASS",
            "BLOCKER",
            "Coinbase dry-run probe must pass before manual review.",
        ),
        _item(
            "broker_readiness_eligible",
            "Broker readiness is eligible for manual approval",
            str(broker_readiness_confirmation.get("readiness_status") or "")
            == "ELIGIBLE_FOR_MANUAL_APPROVAL",
            "BLOCKER",
            "Broker readiness confirmation must be eligible before manual review.",
        ),
        _item(
            "pre_pilot_go_no_go_eligible",
            "Pre-pilot go/no-go is eligible for manual go",
            str(pre_pilot_go_no_go.get("go_no_go_status") or "")
            == "ELIGIBLE_FOR_MANUAL_GO",
            "REVIEW",
            "Pre-pilot go/no-go should be eligible before final manual review.",
        ),
        _item(
            "persistence_disabled",
            "Persistence remains disabled",
            pilot_readiness.get("persistence_enabled") is False
            and _broker_confirmation_persistence_disabled(
                broker_readiness_confirmation
            )
            and pre_pilot_go_no_go.get("persistence_enabled") is False,
            "SAFETY",
            "Runtime event persistence must remain disabled.",
        ),
        _item(
            "pcnrass_currently_passed",
            "Current PCNRASS summary passes",
            _pcnrass_passed(pcnrass_summary),
            "REVIEW",
            "Current PCNRASS summary should pass before manual review.",
        ),
        _item(
            "manual_operator_approval_recorded",
            "Manual operator approval recorded outside this page",
            False,
            "MANUAL",
            "Manual approval remains outstanding and is never recorded by this checklist.",
        ),
        _item(
            "kill_switch_confirmation_recorded",
            "Immediate pre-pilot kill-switch confirmation recorded",
            False,
            "MANUAL",
            "Immediate kill-switch confirmation remains outstanding.",
        ),
        _item(
            "final_pcnrass_recorded",
            "Final pre-pilot PCNRASS release check recorded",
            False,
            "MANUAL",
            "Final PCNRASS release check remains outstanding.",
        ),
    ]


def _item(
    item_id: str,
    label: str,
    completed: bool,
    severity: str,
    message: str,
) -> ManualPilotChecklistItem:
    return ManualPilotChecklistItem(
        item_id=item_id,
        label=label,
        completed=bool(completed),
        required=True,
        severity=severity,
        message=message,
    )


def _checklist_status(items: list[ManualPilotChecklistItem]) -> str:
    missing = [item for item in items if not item.completed]
    if any(item.severity in {"BLOCKER", "SAFETY"} for item in missing):
        return CHECKLIST_INCOMPLETE
    if any(item.severity == "REVIEW" for item in missing):
        return CHECKLIST_REVIEW_READY
    return CHECKLIST_ELIGIBLE_FOR_MANUAL_REVIEW


def _warnings(
    status: str,
    missing_items: list[ManualPilotChecklistItem],
) -> list[str]:
    warnings = [
        "NO_TRADING_IS_ARMED_BY_THIS_CHECKLIST",
        "NO_APPROVAL_IS_GRANTED_BY_THIS_CHECKLIST",
        "NO_ORDER_WILL_BE_PLACED_FROM_THIS_PAGE",
        "NO_BROKER_STATE_WILL_BE_MODIFIED",
        "PERSISTENCE_REMAINS_DISABLED",
        "MANUAL_OPERATOR_APPROVAL_REQUIRED_OUTSIDE_EXPORT",
        "KILL_SWITCH_CONFIRMATION_REQUIRED_IMMEDIATELY_BEFORE_PILOT",
        "FINAL_PCNRASS_CHECK_REQUIRED_IMMEDIATELY_BEFORE_PILOT",
    ]
    if status == CHECKLIST_INCOMPLETE:
        warnings.append("SAFETY_OR_BLOCKER_ITEMS_REMAIN")
    if status == CHECKLIST_REVIEW_READY:
        warnings.append("REVIEW_ITEMS_REMAIN_BEFORE_MANUAL_APPROVAL")
    if any(item.severity == "MANUAL" for item in missing_items):
        warnings.append("MANUAL_RECORDING_ITEMS_REMAIN")
    return list(dict.fromkeys(warnings))


def _evidence_chain_summary(
    *,
    pilot_readiness: Mapping[str, Any],
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    operator_approval_gate: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
    pre_pilot_go_no_go: Mapping[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "pilot_readiness": {
                "present": bool(pilot_readiness),
                "status": pilot_readiness.get("overall_status"),
                "persistence_enabled": pilot_readiness.get("persistence_enabled"),
                "automatic_live_execution_enabled": pilot_readiness.get(
                    "automatic_live_execution_enabled"
                ),
            },
            "order_intent": {
                "present": bool(order_intent),
                "intent_id": order_intent.get("intent_id"),
                "execution_allowed": order_intent.get("execution_allowed"),
                "broker": order_intent.get("broker"),
                "symbol": order_intent.get("symbol"),
                "order_type": order_intent.get("order_type"),
            },
            "coinbase_dry_run_probe": {
                "present": bool(dry_run_probe),
                "probe_id": dry_run_probe.get("probe_id"),
                "validation_status": dry_run_probe.get("validation_status"),
                "order_submit_allowed": dry_run_probe.get("order_submit_allowed"),
                "broker_mutation_allowed": dry_run_probe.get(
                    "broker_mutation_allowed"
                ),
            },
            "operator_approval_gate": {
                "present": bool(operator_approval_gate),
                "approval_gate_id": operator_approval_gate.get("approval_gate_id"),
                "readiness_status": operator_approval_gate.get("readiness_status"),
                "operator_approval_granted": operator_approval_gate.get(
                    "operator_approval_granted"
                ),
                "trading_armed": operator_approval_gate.get("trading_armed"),
                "approval_grant_endpoint_exists": operator_approval_gate.get(
                    "approval_grant_endpoint_exists"
                ),
            },
            "broker_readiness_confirmation": {
                "present": bool(broker_readiness_confirmation),
                "confirmation_id": broker_readiness_confirmation.get(
                    "confirmation_id"
                ),
                "readiness_status": broker_readiness_confirmation.get(
                    "readiness_status"
                ),
                "order_submit_allowed": broker_readiness_confirmation.get(
                    "order_submit_allowed"
                ),
                "broker_mutation_allowed": broker_readiness_confirmation.get(
                    "broker_mutation_allowed"
                ),
            },
            "pre_pilot_go_no_go": {
                "present": bool(pre_pilot_go_no_go),
                "record_id": pre_pilot_go_no_go.get("record_id"),
                "go_no_go_status": pre_pilot_go_no_go.get("go_no_go_status"),
                "trading_armed": pre_pilot_go_no_go.get("trading_armed"),
                "execution_allowed": pre_pilot_go_no_go.get("execution_allowed"),
            },
        }
    )


def _non_executing_controls_confirmed(
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    operator_approval_gate: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
    pre_pilot_go_no_go: Mapping[str, Any],
) -> bool:
    return (
        order_intent.get("execution_allowed") is False
        and dry_run_probe.get("order_submit_allowed") is False
        and dry_run_probe.get("broker_mutation_allowed") is False
        and operator_approval_gate.get("trading_armed") is False
        and operator_approval_gate.get("broker_mutation_allowed") is False
        and broker_readiness_confirmation.get("order_submit_allowed") is False
        and broker_readiness_confirmation.get("broker_mutation_allowed") is False
        and pre_pilot_go_no_go.get("trading_armed") is False
        and pre_pilot_go_no_go.get("execution_allowed") is False
        and pre_pilot_go_no_go.get("order_submit_allowed") is False
        and pre_pilot_go_no_go.get("broker_mutation_allowed") is False
    )


def _scope_consistent(
    order_intent: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    broker_readiness_confirmation: Mapping[str, Any],
    pre_pilot_go_no_go: Mapping[str, Any],
) -> bool:
    brokers = [
        order_intent.get("broker"),
        dry_run_probe.get("broker"),
        broker_readiness_confirmation.get("broker"),
        pre_pilot_go_no_go.get("broker"),
    ]
    symbols = [
        order_intent.get("symbol"),
        dry_run_probe.get("symbol"),
        broker_readiness_confirmation.get("supported_symbol"),
        pre_pilot_go_no_go.get("symbol"),
    ]
    order_types = [
        order_intent.get("order_type"),
        dry_run_probe.get("order_type"),
        broker_readiness_confirmation.get("supported_order_type"),
        pre_pilot_go_no_go.get("order_type"),
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
    pre_pilot_go_no_go: Mapping[str, Any],
) -> bool:
    capital_values = [
        order_intent.get("max_pilot_capital_cad"),
        dry_run_probe.get("max_pilot_capital_cad"),
        broker_readiness_confirmation.get("max_pilot_capital_cad"),
        pre_pilot_go_no_go.get("max_pilot_capital_cad"),
    ]
    slippage_values = [
        order_intent.get("max_slippage_pct"),
        dry_run_probe.get("max_slippage_pct"),
        broker_readiness_confirmation.get("max_slippage_pct"),
        pre_pilot_go_no_go.get("max_slippage_pct"),
    ]
    order_counts = [
        order_intent.get("max_live_orders"),
        dry_run_probe.get("max_live_orders"),
        broker_readiness_confirmation.get("max_live_orders"),
        pre_pilot_go_no_go.get("max_live_orders"),
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
        "export_only": True,
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
    checklist_id: str,
    generated_at_utc: str,
    checklist_status: str,
    blockers: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "micro_live_manual_pilot_checklist_created",
            "checklist_id": checklist_id,
            "generated_at_utc": generated_at_utc,
            "checklist_status": checklist_status,
            "broker": CANONICAL_BROKER,
            "symbol": CANONICAL_SYMBOL,
            "order_type": "limit",
            "manual_operator_approval_recorded": False,
            "kill_switch_confirmation_recorded": False,
            "final_pcnrass_recorded": False,
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


def _checklist_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"MLCHECKLIST-{digest}"


__all__ = [
    "CHECKLIST_ELIGIBLE_FOR_MANUAL_REVIEW",
    "CHECKLIST_INCOMPLETE",
    "CHECKLIST_REVIEW_READY",
    "MICRO_LIVE_MANUAL_PILOT_CHECKLIST_PAYLOAD_VERSION",
    "ManualPilotChecklistItem",
    "MicroLiveManualPilotChecklist",
    "build_micro_live_manual_pilot_checklist_payload",
]
