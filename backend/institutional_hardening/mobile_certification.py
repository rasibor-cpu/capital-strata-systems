from __future__ import annotations

REQUIRED_MOBILE_FLOWS = (
    "sign_on",
    "mode_visibility",
    "broker_status_visibility",
    "kill_switch_visibility",
    "audit_readonly",
    "replay_readonly",
    "no_frontend_broker_calls",
)


def certify_mobile_flows(results: dict[str, bool]) -> dict:
    normalized = {key: bool(results.get(key, False)) for key in REQUIRED_MOBILE_FLOWS}
    passed = all(normalized.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "checks": normalized,
        "execution_allowed": False,
        "frontend_broker_calls_allowed": False,
    }
