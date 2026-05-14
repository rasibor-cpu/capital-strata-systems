from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from engine.execution.live_order_kill_switch import evaluate_live_order_kill_switch


MICRO_LIVE_OPERATOR_APPROVAL_GATE_PAYLOAD_VERSION = (
    "css.micro_live_operator_approval_gate.v1"
)

APPROVAL_GATE_NOT_READY = "NOT_READY"
APPROVAL_GATE_REVIEW_REQUIRED = "REVIEW_REQUIRED"
APPROVAL_GATE_ELIGIBLE = "ELIGIBLE_FOR_MANUAL_APPROVAL"

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
}


@dataclass(frozen=True)
class OperatorApprovalGateCheck:
    check_id: str
    label: str
    passed: bool
    severity: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MicroLiveOperatorApprovalGate:
    approval_gate_id: str
    generated_at_utc: str
    operator_approval_required: bool
    operator_approval_granted: bool
    approval_grant_endpoint_exists: bool
    trading_armed: bool
    broker_mutation_allowed: bool
    requires_final_pcnrass_check: bool
    requires_kill_switch_verification: bool
    requires_broker_readiness_confirmation: bool
    readiness_status: str
    passed_checks: list[dict[str, Any]]
    failed_checks: list[dict[str, Any]]
    blockers: list[str]
    warnings: list[str]
    kill_switch_evidence: dict[str, Any]
    audit_payload: dict[str, Any]
    source_metadata: dict[str, Any]
    payload_version: str = MICRO_LIVE_OPERATOR_APPROVAL_GATE_PAYLOAD_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_micro_live_operator_approval_gate_payload(
    *,
    pilot_readiness: Mapping[str, Any] | None = None,
    dry_run_probe: Mapping[str, Any] | None = None,
    pcnrass_summary: Mapping[str, Any] | bool | None = None,
    broker_readiness_confirmed: bool = False,
    kill_switch_confirmed: bool = False,
    kill_switch_controls: Mapping[str, Any] | None = None,
    kill_switch_env: Mapping[str, str] | None = None,
    generated_at_utc: str = "",
) -> dict[str, Any]:
    """
    Build a review-only operator approval and kill-switch evidence gate.

    This gate never grants approval, never arms trading, never calls a broker,
    never places orders, and never mutates kill-switch state.
    """

    readiness = _mapping(pilot_readiness)
    probe = _mapping(dry_run_probe)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    kill_switch = evaluate_live_order_kill_switch(
        kill_switch_controls or {},
        env=kill_switch_env or {},
    ).as_dict()
    kill_switch_evidence = _kill_switch_evidence(
        kill_switch,
        kill_switch_confirmed=kill_switch_confirmed,
    )
    checks = _approval_gate_checks(
        pilot_readiness=readiness,
        dry_run_probe=probe,
        pcnrass_summary=pcnrass_summary,
        broker_readiness_confirmed=broker_readiness_confirmed,
        kill_switch_evidence=kill_switch_evidence,
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
    gate_id = _approval_gate_id(
        {
            "generated_at_utc": generated,
            "status": status,
            "failed_checks": [check.check_id for check in failed],
        }
    )

    gate = MicroLiveOperatorApprovalGate(
        approval_gate_id=gate_id,
        generated_at_utc=generated,
        operator_approval_required=True,
        operator_approval_granted=False,
        approval_grant_endpoint_exists=False,
        trading_armed=False,
        broker_mutation_allowed=False,
        requires_final_pcnrass_check=True,
        requires_kill_switch_verification=True,
        requires_broker_readiness_confirmation=True,
        readiness_status=status,
        passed_checks=[check.as_dict() for check in passed],
        failed_checks=[check.as_dict() for check in failed],
        blockers=blockers,
        warnings=warnings,
        kill_switch_evidence=kill_switch_evidence,
        audit_payload=_audit_payload(
            approval_gate_id=gate_id,
            generated_at_utc=generated,
            readiness_status=status,
            blockers=blockers,
            kill_switch_evidence=kill_switch_evidence,
        ),
        source_metadata={
            "source": "dashboard.runtime.micro_live_operator_approval_gate",
            "read_only": True,
            "review_only": True,
            "evidence_only": True,
            "no_broker_calls": True,
            "no_order_placement": True,
            "no_account_mutation": True,
            "no_approval_grant_endpoint": True,
            "no_trading_arm": True,
            "frontend_safe": True,
            "secrets_redacted": True,
        },
    )
    return _json_safe(gate.as_dict())


def _approval_gate_checks(
    *,
    pilot_readiness: Mapping[str, Any],
    dry_run_probe: Mapping[str, Any],
    pcnrass_summary: Mapping[str, Any] | bool | None,
    broker_readiness_confirmed: bool,
    kill_switch_evidence: Mapping[str, Any],
) -> list[OperatorApprovalGateCheck]:
    return [
        _check(
            "operator_approval_required",
            "Operator approval is required",
            True,
            "REVIEW",
            "Manual operator approval is required before any pilot.",
        ),
        _check(
            "operator_approval_not_granted_by_gate",
            "Gate does not grant operator approval",
            True,
            "SAFETY",
            "This evidence gate must not grant approval.",
        ),
        _check(
            "approval_grant_endpoint_absent",
            "No approval-grant endpoint exists",
            True,
            "SAFETY",
            "No API route should arm trading or grant approval.",
        ),
        _check(
            "trading_not_armed",
            "Trading remains unarmed",
            True,
            "SAFETY",
            "Trading must remain unarmed at the evidence-gate stage.",
        ),
        _check(
            "broker_mutation_disallowed",
            "Broker mutation is disallowed",
            True,
            "SAFETY",
            "The approval gate must not mutate broker/account state.",
        ),
        _check(
            "pilot_readiness_payload_present",
            "Pilot readiness evidence is present",
            bool(pilot_readiness),
            "REVIEW",
            "Pilot readiness payload is required for manual approval review.",
        ),
        _check(
            "pilot_readiness_not_unrestricted",
            "Pilot readiness does not arm unrestricted live trading",
            not _bool(pilot_readiness.get("unrestricted_live_trading_enabled"))
            and not _bool(pilot_readiness.get("automatic_live_execution_enabled")),
            "SAFETY",
            "Pilot readiness must not enable unrestricted or automatic live trading.",
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
            bool(dry_run_probe)
            and dry_run_probe.get("order_submit_allowed") is False
            and dry_run_probe.get("broker_mutation_allowed") is False
            and str(dry_run_probe.get("probe_mode") or "") == "non_executing",
            "SAFETY",
            "Dry-run probe must prove no submit and no broker mutation.",
        ),
        _check(
            "dry_run_probe_passed",
            "Dry-run probe validation passed",
            str(dry_run_probe.get("validation_status") or "").upper() == "PASS",
            "BLOCKER",
            "Coinbase dry-run probe must pass before approval review.",
        ),
        _check(
            "kill_switch_reference_available",
            "Kill switch reference is available",
            bool(kill_switch_evidence.get("kill_switch_reference_available")),
            "SAFETY",
            "Live-order kill switch evaluator must remain available.",
        ),
        _check(
            "kill_switch_not_bypassed",
            "Kill switch has not been bypassed",
            not _bool(kill_switch_evidence.get("kill_switch_bypassed")),
            "SAFETY",
            "No live order path may bypass kill-switch verification.",
        ),
        _check(
            "kill_switch_verification_required",
            "Kill-switch verification is required",
            _bool(kill_switch_evidence.get("verification_required")),
            "SAFETY",
            "Kill-switch verification is mandatory before any pilot.",
        ),
        _check(
            "kill_switch_pre_pilot_confirmation_present",
            "Immediate pre-pilot kill-switch confirmation present",
            _bool(kill_switch_evidence.get("pre_pilot_confirmation_present")),
            "REVIEW",
            "Kill switch must be confirmed immediately before a pilot.",
        ),
        _check(
            "broker_readiness_confirmation_required",
            "Broker readiness confirmation is required",
            True,
            "REVIEW",
            "Final broker readiness confirmation is mandatory before any pilot.",
        ),
        _check(
            "broker_readiness_confirmation_present",
            "Final broker readiness confirmation present",
            broker_readiness_confirmed,
            "REVIEW",
            "Broker readiness must be confirmed immediately before pilot.",
        ),
        _check(
            "final_pcnrass_check_required",
            "Final PCNRASS check is required",
            True,
            "REVIEW",
            "Final PCNRASS release check is mandatory before any pilot.",
        ),
        _check(
            "final_pcnrass_check_passed",
            "Final PCNRASS check passed",
            _pcnrass_passed(pcnrass_summary),
            "REVIEW",
            "Final PCNRASS release check must pass immediately before pilot.",
        ),
        _check(
            "no_live_order_without_kill_switch_confirmation",
            "No live order may proceed without kill-switch confirmation",
            True,
            "SAFETY",
            "Live order path remains blocked without explicit kill-switch evidence.",
        ),
    ]


def _check(
    check_id: str,
    label: str,
    passed: bool,
    severity: str,
    message: str,
) -> OperatorApprovalGateCheck:
    return OperatorApprovalGateCheck(
        check_id=check_id,
        label=label,
        passed=bool(passed),
        severity=severity,
        message=message,
    )


def _readiness_status(failed: list[OperatorApprovalGateCheck]) -> str:
    if any(check.severity in {"BLOCKER", "SAFETY"} for check in failed):
        return APPROVAL_GATE_NOT_READY
    if failed:
        return APPROVAL_GATE_REVIEW_REQUIRED
    return APPROVAL_GATE_ELIGIBLE


def _warnings(status: str, failed: list[OperatorApprovalGateCheck]) -> list[str]:
    warnings = [
        "MANUAL_APPROVAL_STILL_REQUIRED_NO_TRADING_ARMED",
        "OPERATOR_APPROVAL_GRANTED_FALSE",
        "APPROVAL_GRANT_ENDPOINT_ABSENT",
        "KILL_SWITCH_MUST_BE_CONFIRMED_IMMEDIATELY_BEFORE_PILOT",
        "BROKER_READINESS_MUST_BE_CONFIRMED_IMMEDIATELY_BEFORE_PILOT",
        "FINAL_PCNRASS_CHECK_REQUIRED_IMMEDIATELY_BEFORE_PILOT",
        "NO_ORDER_PLACEMENT_FROM_APPROVAL_GATE",
    ]
    if status != APPROVAL_GATE_ELIGIBLE:
        warnings.append("APPROVAL_GATE_NOT_READY_FOR_MANUAL_APPROVAL")
    if any(check.severity == "REVIEW" for check in failed):
        warnings.append("REVIEW_ITEMS_REMAIN")
    if any(check.severity in {"BLOCKER", "SAFETY"} for check in failed):
        warnings.append("SAFETY_BLOCKERS_REMAIN")
    return list(dict.fromkeys(warnings))


def _kill_switch_evidence(
    kill_switch: Mapping[str, Any],
    *,
    kill_switch_confirmed: bool,
) -> dict[str, Any]:
    return _json_safe(
        {
            "kill_switch_reference_available": True,
            "verification_required": True,
            "pre_pilot_confirmation_present": bool(kill_switch_confirmed),
            "kill_switch_bypassed": False,
            "activation_performed": False,
            "live_order_path_blocked_without_confirmation": True,
            "current_decision": {
                "blocked": bool(kill_switch.get("blocked")),
                "reason": str(kill_switch.get("reason") or ""),
                "source": str(kill_switch.get("source") or ""),
            },
            "confirmation_window": "immediate_pre_pilot_only",
        }
    )


def _audit_payload(
    *,
    approval_gate_id: str,
    generated_at_utc: str,
    readiness_status: str,
    blockers: list[str],
    kill_switch_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "event_type": "micro_live_operator_approval_gate_created",
            "approval_gate_id": approval_gate_id,
            "generated_at_utc": generated_at_utc,
            "readiness_status": readiness_status,
            "operator_approval_required": True,
            "operator_approval_granted": False,
            "approval_grant_endpoint_exists": False,
            "trading_armed": False,
            "broker_mutation_allowed": False,
            "order_placed": False,
            "broker_mutated": False,
            "kill_switch_evidence": kill_switch_evidence,
            "blockers": blockers,
        }
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _approval_gate_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:20].upper()
    return f"MLAPPROVAL-{digest}"


__all__ = [
    "APPROVAL_GATE_ELIGIBLE",
    "APPROVAL_GATE_NOT_READY",
    "APPROVAL_GATE_REVIEW_REQUIRED",
    "MICRO_LIVE_OPERATOR_APPROVAL_GATE_PAYLOAD_VERSION",
    "MicroLiveOperatorApprovalGate",
    "OperatorApprovalGateCheck",
    "build_micro_live_operator_approval_gate_payload",
]
