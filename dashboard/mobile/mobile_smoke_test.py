from __future__ import annotations

import tempfile
from pathlib import Path

from dashboard.mobile.mobile_app import app, _dashboard_page, _login_page


def main() -> int:
    routes = {getattr(route, "path", "") for route in app.routes}
    required = {
        "/",
        "/login",
        "/password-change",
        "/dashboard",
        "/trade",
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
    if "Mobile Full Access" not in dashboard or "MOBILE_GOVERNED_ACCESS" not in dashboard:
        raise AssertionError("Dashboard page is missing mobile full-access guardrails")

    from dashboard.mobile.mobile_app import _trade_ticket_page

    trade_page = _trade_ticket_page(
        user_ctx={
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
        }
    )
    if "Submit Trade Ticket" not in trade_page or "Type EXECUTE" not in trade_page:
        raise AssertionError("Trade ticket page is missing execution controls")

    import dashboard.mobile.mobile_app as mobile_app

    with tempfile.TemporaryDirectory() as tmp:
        mobile_app.MOBILE_EVENTS_FILE = Path(tmp) / "mobile_events.jsonl"
        user_ctx = {
            "user_id": "00000",
            "display_name": "CSS Administrator",
            "role": "SUPER_USER",
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
