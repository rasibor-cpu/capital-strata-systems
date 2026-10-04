from __future__ import annotations

import tempfile
from pathlib import Path

from dashboard.mobile.mobile_app import (
    app,
    _audit_page,
    _broker_page,
    _controls_page,
    _dashboard_page,
    _governance_page,
    _history_page,
    _login_page,
    _market_page,
    _opportunities_page,
    _positions_page,
    _risk_page,
    _trade_ticket_page,
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
        "/positions",
        "/history",
        "/risk",
        "/governance",
        "/opportunities",
        "/market",
        "/broker",
        "/audit",
        "/trade",
        "/users",
        "/api/status",
        "/api/audit/export",
        "/api/audit/replay",
        "/manifest.webmanifest",
        "/service-worker.js",
        "/icon.svg",
    }

    missing = required - routes
    if missing:
        raise AssertionError(f"Missing mobile routes: {sorted(missing)}")

    import dashboard.mobile.mobile_app as mobile_app

    class _NoCanonicalSession:
        """No canonical runtime session: paper tickets must fail closed."""

        def get_active_sessions(self):
            return []

    trader_ctx = {"user_id": "00017", "display_name": "CSS Trader", "role": "TRADER"}
    admin_ctx = {"user_id": "00000", "display_name": "CSS Administrator", "role": "SUPER_USER"}
    viewer_ctx = {"user_id": "00018", "display_name": "CSS Viewer", "role": "VIEWER"}
    session = {"created": 1.0}
    paper_ticket = {
        "broker": "CSS_PAPER", "asset_class": "CRYPTO", "symbol": "BTC-USD",
        "side": "BUY", "amount": "1.00", "qty": "1",
    }

    # Isolated from the operator's real artifacts/ and runtime databases, so
    # the result depends only on the code under test.
    originals = (mobile_app.MOBILE_EVENTS_FILE, mobile_app.MOBILE_CONTROL_FILE, mobile_app.SessionRuntimeService)
    with tempfile.TemporaryDirectory() as tmp:
        mobile_app.MOBILE_EVENTS_FILE = Path(tmp) / "mobile_events.jsonl"
        mobile_app.MOBILE_CONTROL_FILE = Path(tmp) / "mobile_controls.json"
        mobile_app.SessionRuntimeService = _NoCanonicalSession
        try:
            # -- Governed default: MOBILE_READ_ONLY, orders disabled (4b1288f).
            login = _login_page()
            if "Capital Strata Systems" not in login or "manifest.webmanifest" not in login:
                raise AssertionError("Login page is missing expected mobile shell content")
            if 'value="00000"' in login:
                raise AssertionError("Login user ID must not default to the super-user ID")
            for marker in ("Engine SAFE", "System READ ONLY", "Orders DISABLED"):
                if marker not in login:
                    raise AssertionError(f"Login status strip must show the governed default: {marker}")

            dashboard = _dashboard_page(user_ctx=trader_ctx, session=session)
            for marker in ("Mobile Role Access", "Engine SAFE", "Orders DISABLED", "Recent Mobile Tickets",
                           "Account Summary", "Command Center"):
                if marker not in dashboard:
                    raise AssertionError(f"Dashboard is missing {marker}")

            trade_page = _trade_ticket_page(user_ctx=trader_ctx)
            if "Trade Activation Status" not in trade_page:
                raise AssertionError("Trade page must show activation readiness")
            if "Submit Trade Ticket" in trade_page:
                raise AssertionError("Trade submission must not be offered while mobile orders are disabled")
            if mobile_app.execute_mobile_trade_ticket(trader_ctx, paper_ticket).get("status") != "MOBILE_ORDERS_DISABLED":
                raise AssertionError("READ ONLY mode must block tickets")

            # -- Paper trading mode: submission offered, but every ticket goes
            #    through the canonical pipeline and fails closed without it.
            mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_PAPER_TRADING", "engine_mode": "SAFE"})
            if "System PAPER" not in _login_page() or "Orders ENABLED" not in _login_page():
                raise AssertionError("Login status strip must reflect PAPER mode")
            trade_page = _trade_ticket_page(user_ctx=trader_ctx)
            if "Submit Trade Ticket" not in trade_page or "System mode is PAPER" not in trade_page:
                raise AssertionError("Paper mode must offer ticket submission and say it is PAPER")
            paper_result = mobile_app.execute_mobile_trade_ticket(trader_ctx, paper_ticket)
            if paper_result.get("ok") is not False or paper_result.get("status") != "NO_ACTIVE_SESSION":
                raise AssertionError(f"Paper ticket without a canonical session must fail closed: {paper_result.get('status')}")
            if mobile_app.execute_mobile_trade_ticket(viewer_ctx, paper_ticket).get("status") != "MOBILE_AUTHORITY_DENIED":
                raise AssertionError("Viewer role must not submit mobile trade tickets")

            # -- Live: the legacy armed mode is downgraded; live is never executable from mobile.
            saved = mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})
            if saved["mobile_trading_mode"] != "MOBILE_LIVE_READ_ONLY" or saved["orders_enabled"] is not False:
                raise AssertionError("Legacy live-armed control must be downgraded to LIVE READ ONLY")
            live_result = mobile_app.execute_mobile_trade_ticket(
                admin_ctx, {**paper_ticket, "broker": "COINBASE", "confirm": "MOBILE LIVE"}
            )
            if live_result.get("status") != "MOBILE_LIVE_EXECUTION_NOT_AUTHORIZED":
                raise AssertionError("Live mobile execution must not be authorized")
            if live_result.get("broker_response", {}).get("live_order_sent") is not False:
                raise AssertionError("A live mobile ticket must state that no live order was sent")

            positions_page = _positions_page(trader_ctx, session)
            # Inventory comes from the runtime (no fabricated demo rows), so an
            # empty runtime renders the table with its empty-state row.
            if "Positions Screen" not in positions_page or "Position Inventory" not in positions_page:
                raise AssertionError("Positions screen must show mobile position inventory")
            if "Trade / Execution History" not in _history_page(trader_ctx, session):
                raise AssertionError("History screen must render the execution history shell")
            risk_page = _risk_page(trader_ctx, session)
            if "Risk Control Center" not in risk_page or "Risk Limit Breaches" not in risk_page:
                raise AssertionError("Risk screen must show risk control center content")
            governance_page = _governance_page(trader_ctx, session)
            if "Governance Center" not in governance_page or "Submit Trades" not in governance_page:
                raise AssertionError("Governance screen must show authority state")
            opportunities_page = _opportunities_page(trader_ctx, session)
            if "Opportunity Monitor" not in opportunities_page or "Monitor Only" not in opportunities_page:
                raise AssertionError("Opportunity monitor must be observational")
            market_page = _market_page(trader_ctx, session)
            if "Market Regime Panel" not in market_page or "Signal Context" not in market_page:
                raise AssertionError("Market screen must show regime and signal context")
            broker_page = _broker_page(trader_ctx, session)
            if "Broker Control Panel" not in broker_page or "Broker secrets are never displayed" not in broker_page:
                raise AssertionError("Broker screen must show safe broker readiness content")
            if "Reconciliation" not in broker_page or "Safe Downgrade" not in broker_page:
                raise AssertionError("Broker screen must show reconciliation posture")
            controls_page = _controls_page(user_ctx=admin_ctx)
            if "System Controls" not in controls_page or "Runtime Controls" not in controls_page:
                raise AssertionError("Controls page is missing mode/order controls")
            users_page = _users_page(user_ctx=admin_ctx)
            if "Create User" not in users_page or "Require password change" not in users_page:
                raise AssertionError("Users page is missing super-user user creation controls")

            audit_page = _audit_page(admin_ctx)
            if "Audit Trail Viewer" not in audit_page or "NO_ACTIVE_SESSION" not in audit_page:
                raise AssertionError("Audit viewer must expose recent mobile ticket outcomes")
            if "/api/audit/export" not in audit_page or "/api/audit/replay" not in audit_page:
                raise AssertionError("Audit viewer must expose redacted export and deterministic replay")
        finally:
            mobile_app.MOBILE_EVENTS_FILE, mobile_app.MOBILE_CONTROL_FILE, mobile_app.SessionRuntimeService = originals

    print("CSS mobile web smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
