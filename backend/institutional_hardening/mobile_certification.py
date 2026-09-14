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


REQUIRED_ROUTE_HINTS = (
    "/login",
    "/dashboard",
    "/broker",
    "/audit",
)


def certify_mobile_route_surface(route_paths: set[str], *, frontend_broker_calls_detected: bool) -> dict:
    route_checks = {path: path in route_paths for path in REQUIRED_ROUTE_HINTS}
    passed = all(route_checks.values()) and not frontend_broker_calls_detected
    return {
        "status": "PASS" if passed else "FAIL",
        "route_checks": route_checks,
        "frontend_broker_calls_detected": bool(frontend_broker_calls_detected),
        "execution_allowed": False,
    }
