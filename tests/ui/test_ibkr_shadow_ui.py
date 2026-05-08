from __future__ import annotations

from pathlib import Path

from ui.backend.app.dashboard_state_router import dashboard_state


ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = ROOT / "ui" / "ibkr"


def test_web_console_contains_required_panels() -> None:
    html = (UI_ROOT / "index.html").read_text(encoding="utf-8")

    for panel in [
        "Account Overview",
        "Live Positions",
        "Risk Control Center",
        "Governance Center",
        "Market Regime Panel",
        "Execution Center",
        "Opportunity Monitor",
        "Broker Control Panel",
    ]:
        assert panel in html


def test_mobile_console_contains_required_screens() -> None:
    html = (UI_ROOT / "mobile.html").read_text(encoding="utf-8")

    for screen in [
        "Home",
        "Positions",
        "Execution",
        "Risk",
        "Alerts",
    ]:
        assert screen in html


def test_ui_uses_dashboard_state_bridge_without_direct_broker_calls() -> None:
    app_js = (UI_ROOT / "app.js").read_text(encoding="utf-8")
    router_py = (
        ROOT / "ui" / "backend" / "app" / "dashboard_state_router.py"
    ).read_text(encoding="utf-8")

    assert "/api/v1/dashboard-state" in app_js
    assert "DashboardState" in router_py
    assert ".to_dict()" in router_py

    forbidden_fragments = [
        "api.coinbase.com",
        "api-fxtrade.oanda.com",
        "ibapi",
        "place_order",
        "create_order",
    ]
    combined = (app_js + "\n" + router_py).lower()
    for fragment in forbidden_fragments:
        assert fragment not in combined


def test_dashboard_state_bridge_payload_is_shadow_and_paper_safe() -> None:
    payload = dashboard_state()

    assert payload["shadow_mode"] is True
    assert payload["resolved_mode"] == "paper"
    assert payload["broker_mode"] == "paper"
    assert payload["broker_summary"]["live_trading_enabled"] is False
    assert payload["positions"]
    assert payload["alerts"]
