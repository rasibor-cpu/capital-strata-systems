from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryScenario:
    scenario_id: str
    description: str
    requires_restart: bool = True


RECOVERY_SCENARIOS = {
    "clean-restart": RecoveryScenario("clean-restart", "Graceful restart with persisted state"),
    "corrupt-artifact": RecoveryScenario("corrupt-artifact", "Corrupt local continuity artifact must fail closed"),
    "stale-reload": RecoveryScenario("stale-reload", "Reloaded persisted state must remain explicitly stale"),
    "provider-unavailable": RecoveryScenario("provider-unavailable", "Provider unavailable after restart must not create fresh state"),
}


def evaluate_recovery_drill(*, restart_ok: bool, session_restored: bool, artifact_integrity_ok: bool, stale_state_explicit: bool) -> dict:
    checks = {
        "restart_ok": restart_ok,
        "session_restored": session_restored,
        "artifact_integrity_ok": artifact_integrity_ok,
        "stale_state_explicit": stale_state_explicit,
    }
    passed = all(checks.values())
    return {
        "status": "PASS" if passed else "FAIL_CLOSED",
        "checks": checks,
        "execution_allowed": False,
        "resume_allowed": passed,
    }


def build_recovery_report(scenario_id: str, **checks: bool) -> dict:
    if scenario_id not in RECOVERY_SCENARIOS:
        raise ValueError("unknown recovery scenario")
    scenario = RECOVERY_SCENARIOS[scenario_id]
    result = evaluate_recovery_drill(
        restart_ok=bool(checks.get("restart_ok", False)),
        session_restored=bool(checks.get("session_restored", False)),
        artifact_integrity_ok=bool(checks.get("artifact_integrity_ok", False)),
        stale_state_explicit=bool(checks.get("stale_state_explicit", False)),
    )
    return {
        "schema_version": "css.recovery_drill.v1",
        "scenario_id": scenario.scenario_id,
        "description": scenario.description,
        **result,
        "pcnrass_review_required": True,
    }
