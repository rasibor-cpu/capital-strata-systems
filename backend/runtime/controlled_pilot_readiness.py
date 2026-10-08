"""Read-only readiness aggregation for the governed controlled-live pilot.

This module never arms execution, never places an order, never mutates broker
state, and never changes safety flags. It only aggregates already-produced
evidence into a fail-closed GO/NO-GO decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.runtime.pilot_dual_control import production_enrollment_status


REQUIRED_SAFE_FLAGS = {
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
    "advisory_only": True,
}


@dataclass(frozen=True)
class ControlledPilotReadiness:
    ready: bool
    blockers: tuple[str, ...]
    checks: dict[str, bool]


def evaluate_controlled_pilot_readiness(
    *,
    safety_flags: Mapping[str, Any] | None,
    broker_reconciliation: Mapping[str, Any] | None,
    pcnrass_passed: bool,
    kill_switch_verified: bool,
    full_regression_reconciled: bool,
    security_review_passed: bool,
    endurance_review_passed: bool,
    release_candidate_frozen: bool,
    independent_readiness_review_passed: bool,
    enrollment_path: str | None = None,
) -> ControlledPilotReadiness:
    blockers: list[str] = []
    flags = safety_flags if isinstance(safety_flags, Mapping) else {}
    broker = broker_reconciliation if isinstance(broker_reconciliation, Mapping) else {}

    safe_flags_ok = (
        flags.get("verdict") == "SAFE"
        and all(type(flags.get(k)) is bool and flags.get(k) is v for k, v in REQUIRED_SAFE_FLAGS.items())
        and not list(flags.get("not_observed") or [])
        and not list(flags.get("unsafe") or [])
    )
    if not safe_flags_ok:
        blockers.append("safety_flags_not_fail_closed")

    broker_ok = (
        broker.get("status") == "BROKER_RECONCILED"
        and broker.get("safe_degradation_required") is False
    )
    if not broker_ok:
        blockers.append("broker_reconciliation_not_clean")

    if enrollment_path is None:
        enrollment = production_enrollment_status()
    else:
        enrollment = production_enrollment_status(enrollment_path)
    enrollment_ok = enrollment.get("ready") is True
    if not enrollment_ok:
        for reason in enrollment.get("blockers") or ["pilot_approver_enrollment_not_ready"]:
            blockers.append(f"enrollment:{reason}")

    boolean_checks = {
        "pcnrass_passed": pcnrass_passed is True,
        "kill_switch_verified": kill_switch_verified is True,
        "full_regression_reconciled": full_regression_reconciled is True,
        "security_review_passed": security_review_passed is True,
        "endurance_review_passed": endurance_review_passed is True,
        "release_candidate_frozen": release_candidate_frozen is True,
        "independent_readiness_review_passed": independent_readiness_review_passed is True,
    }
    for name, passed in boolean_checks.items():
        if not passed:
            blockers.append(name)

    checks = {
        "safety_flags_explicit_and_safe": safe_flags_ok,
        "broker_reconciliation_clean": broker_ok,
        "dual_control_enrollment_ready": enrollment_ok,
        **boolean_checks,
    }

    return ControlledPilotReadiness(
        ready=not blockers and all(checks.values()),
        blockers=tuple(blockers),
        checks=checks,
    )


__all__ = ["ControlledPilotReadiness", "evaluate_controlled_pilot_readiness"]
