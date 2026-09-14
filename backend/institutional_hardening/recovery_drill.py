from __future__ import annotations


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
