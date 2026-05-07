from __future__ import annotations

from dashboard.mobile.mobile_app import app, _dashboard_page, _login_page


def main() -> int:
    routes = {getattr(route, "path", "") for route in app.routes}
    required = {
        "/",
        "/login",
        "/password-change",
        "/dashboard",
        "/api/status",
        "/manifest.webmanifest",
        "/service-worker.js",
        "/icon.svg",
    }

    missing = required - routes
    if missing:
        raise AssertionError(f"Missing mobile routes: {sorted(missing)}")

    login = _login_page()
    if "Capital Strata Systems" not in login or "manifest.webmanifest" not in login:
        raise AssertionError("Login page is missing expected mobile shell content")

    dashboard = _dashboard_page(
        user_ctx={
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
        },
        session={"created": 1.0},
    )
    if "Mobile Read Only" not in dashboard or "PHONE_EXECUTION_DISABLED" not in dashboard:
        raise AssertionError("Dashboard page is missing mobile read-only guardrails")

    print("CSS mobile web smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
