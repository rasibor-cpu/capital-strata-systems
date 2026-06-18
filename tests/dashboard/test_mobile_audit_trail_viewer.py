from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app


SUPER_USER = {
    "user_id": "00000",
    "display_name": "CSS Administrator",
    "role": "SUPER_USER",
}


TRADER = {
    "user_id": "00017",
    "display_name": "CSS Trader",
    "role": "TRADER",
}


def test_mobile_audit_routes_are_registered() -> None:
    routes = {getattr(route, "path", "") for route in mobile_app.app.routes}

    assert "/audit" in routes
    assert "/api/audit/export" in routes
    assert "/api/audit/replay" in routes


def test_mobile_audit_view_requires_audit_authority() -> None:
    assert mobile_app._can_view_audit_logs(SUPER_USER) is True
    assert mobile_app._can_view_audit_logs({"role": "AUDIT"}) is True
    assert mobile_app._can_view_audit_logs({"role": "HEAD_AUDIT"}) is True
    assert mobile_app._can_view_audit_logs(TRADER) is False


def test_mobile_audit_page_renders_filtered_redacted_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {
            "mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED",
            "engine_mode": "BALANCED",
            "live_order_kill_switch": True,
        }
    )

    result = mobile_app.execute_mobile_trade_ticket(
        TRADER,
        {
            "broker": "COINBASE",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
            "confirm": "MOBILE LIVE",
        },
    )
    page = mobile_app._audit_page(
        SUPER_USER,
        category="kill_switch",
        status="KILL_SWITCH",
        actor="00017",
    )

    assert result["status"] == "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED"
    assert "Audit Trail Viewer" in page
    assert "Kill Switch" in page
    assert "GLOBAL_LIVE_ORDER_KILL_SWITCH_ENGAGED" in page
    assert "/api/audit/export?category=kill_switch" in page
    assert "/api/audit/replay" in page
    assert "api_secret" not in page.lower()


def test_mobile_command_center_exposes_audit_only_to_audit_roles(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {"runtime_mode": "paper", "orders_enabled": True, "engine_mode": "SAFE"}
    )

    super_dashboard = mobile_app._dashboard_page(SUPER_USER, {"created": 1.0})
    trader_dashboard = mobile_app._dashboard_page(TRADER, {"created": 1.0})

    assert 'href="/audit"' in super_dashboard
    assert 'href="/audit"' not in trader_dashboard
