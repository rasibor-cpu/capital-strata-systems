from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .operator_approval import OperatorApproval, validate_operator_approval


@dataclass(frozen=True)
class LiveModeGuardrailInput:
    operator_approval: OperatorApproval | None
    dry_run_certification_passed: bool
    reconciliation_confirmed: bool
    kill_switch_available: bool
    release_check_passed: bool
    broker_readiness_passed: bool


def evaluate_live_mode_guardrail(
    data: LiveModeGuardrailInput,
    *,
    now_utc: datetime,
) -> dict[str, Any]:
    approval_ok, approval_reason = validate_operator_approval(
        data.operator_approval,
        required_scope="RESTRICTED_LIVE_REVIEW",
        now_utc=now_utc,
    )
    checks = {
        "operator_approval": approval_ok,
        "dry_run_certification": data.dry_run_certification_passed,
        "reconciliation": data.reconciliation_confirmed,
        "kill_switch_available": data.kill_switch_available,
        "release_check": data.release_check_passed,
        "broker_readiness": data.broker_readiness_passed,
    }
    passed = all(checks.values())
    return {
        "status": "READY_FOR_HUMAN_REVIEW" if passed else "BLOCKED",
        "checks": checks,
        "approval_reason": approval_reason,
        "execution_allowed": False,
        "broker_execution_armed": False,
        "live_trading_authorized": False,
    }
