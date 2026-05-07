from __future__ import annotations

import tempfile
from pathlib import Path

from dashboard.mobile.mobile_app import (
    app,
    _controls_page,
    _dashboard_page,
    _login_page,
    _users_page,
)


def main() -> int:
    routes = {getattr(route, "path", "") for route in app.routes}
    required = {
        "/",
        "/login",
        "/password-change",
        "/controls",
        "/dashboard",
        "/trade",
        "/users",
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
    if 'value="00000"' in login:
        raise AssertionError("Login user ID must not default to the super-user ID")
    if "Engine SAFE" not in login or "System PAPER" not in login:
        raise AssertionError("Login page must show system status and engine mode")

    dashboard = _dashboard_page(
        user_ctx={
            "user_id": "00017",
            "display_name": "CSS Trader",
            "role": "TRADER",
        },
        session={"created": 1.0},
    )
    if "Mobile Role Access" not in dashboard or "MOBILE_PAPER_ACCESS" not in dashboard:
        raise AssertionError("Dashboard page is missing mobile full-access guardrails")
    if "Engine SAFE" not in dashboard or "Orders ENABLED" not in dashboard:
        raise AssertionError("Dashboard must show system status and engine mode")

    controls_page = _controls_page(
        user_ctx={
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
        }
    )
    if "System Controls" not in controls_page or "Runtime Controls" not in controls_page:
        raise AssertionError("Controls page is missing mode/order controls")

    users_page = _users_page(
        user_ctx={
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
        }
    )
    if "Create User" not in users_page or "Require password change" not in users_page:
        raise AssertionError("Users page is missing super-user user creation controls")

    from dashboard.mobile.mobile_app import _trade_ticket_page

    trade_page = _trade_ticket_page(
        user_ctx={
            "user_id": "00017",
            "display_name": "CSS Trader",
            "role": "TRADER",
        }
    )
    if "Submit Trade Ticket" not in trade_page or "Type EXECUTE" not in trade_page:
        raise AssertionError("Trade ticket page is missing execution controls")

    import dashboard.mobile.mobile_app as mobile_app

    with tempfile.TemporaryDirectory() as tmp:
        mobile_app.MOBILE_EVENTS_FILE = Path(tmp) / "mobile_events.jsonl"
        mobile_app.MOBILE_CONTROL_FILE = Path(tmp) / "mobile_controls.json"
        user_ctx = {
            "user_id": "00017",
            "display_name": "CSS Trader",
            "role": "TRADER",
        }

        paper_result = mobile_app.execute_mobile_trade_ticket(
            user_ctx,
            {
                "mode": "paper",
                "broker": "CSS_PAPER",
                "asset_class": "CRYPTO",
                "symbol": "BTC-USD",
                "side": "BUY",
                "amount": "1.00",
                "qty": "1",
            },
        )
        if paper_result.get("status") != "PAPER_TICKET_RECORDED":
            raise AssertionError("Paper mobile trade ticket was not recorded")

        mobile_app.save_mobile_controls(
            {"runtime_mode": "paper", "orders_enabled": False, "engine_mode": "SAFE"}
        )
        disabled_result = mobile_app.execute_mobile_trade_ticket(
            user_ctx,
            {
                "mode": "paper",
                "broker": "CSS_PAPER",
                "asset_class": "CRYPTO",
                "symbol": "BTC-USD",
                "side": "BUY",
                "amount": "1.00",
                "qty": "1",
            },
        )
        if disabled_result.get("status") != "MOBILE_ORDERS_DISABLED":
            raise AssertionError("Disabled mobile orders must block tickets")

        viewer_result = mobile_app.execute_mobile_trade_ticket(
            {
                "user_id": "00018",
                "display_name": "CSS Viewer",
                "role": "VIEWER",
            },
            {
                "mode": "paper",
                "broker": "CSS_PAPER",
                "asset_class": "CRYPTO",
                "symbol": "BTC-USD",
                "side": "BUY",
                "amount": "1.00",
                "qty": "1",
            },
        )
        if viewer_result.get("status") != "MOBILE_AUTHORITY_DENIED":
            raise AssertionError("Viewer role must not submit mobile trade tickets")

        mobile_app.save_mobile_controls(
            {"runtime_mode": "live", "orders_enabled": True, "engine_mode": "BALANCED"}
        )

        live_result = mobile_app.execute_mobile_trade_ticket(
            user_ctx,
            {
                "mode": "live",
                "broker": "COINBASE",
                "asset_class": "CRYPTO",
                "symbol": "BTC-USD",
                "side": "BUY",
                "amount": "1.00",
                "qty": "1",
                "confirm": "",
            },
        )
        if live_result.get("status") != "LIVE_CONFIRMATION_REQUIRED":
            raise AssertionError("Live mobile ticket must require explicit confirmation")

    print("CSS mobile web smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
