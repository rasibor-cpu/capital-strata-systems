from __future__ import annotations

import re

from fastapi.testclient import TestClient

from backend.brokers.account_balance_contract import build_broker_balance_summary
from backend.reports_center.registry import all_definitions
from backend.reports_center.viewer_audit import AUDIT_CHECKS, audit_report_catalogue
from dashboard.mission_control.layout import render_mission_control_shell


def test_launcher_phone_and_pwa_open_basic_html_landing() -> None:
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    response = client.get("/mobile-launcher")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.url.path == "/mobile-launcher"
    assert "/api/" not in response.text
    for label in (
        "Mission Control",
        "Trade Operations",
        "Reports",
        "Portfolio",
        "Market Intelligence",
        "Risk Command",
        "Options Income",
        "Broker Management",
        "Runtime Operations",
        "Certification and Readiness",
        "Alerts and Incidents",
        "Users and Governance",
        "System Configuration",
        "Documentation and Runbooks",
    ):
        assert label in response.text
    manifest = client.get("/manifest.json").json()
    assert manifest["start_url"] == "/mobile-launcher"
    assert not manifest["start_url"].startswith("/api/")


def test_mobile_pwa_landing_and_login_focus_contract() -> None:
    from dashboard.mobile.mobile_app import app

    client = TestClient(app)
    manifest = client.get("/manifest.webmanifest").json()
    assert manifest["start_url"] == "/dashboard"
    landing = client.get("/mobile-launcher")
    assert landing.status_code == 200
    assert landing.headers["content-type"].startswith("text/html")
    assert "Mission Control" in landing.text
    login = client.get("/login")
    assert login.text.count("autofocus") == 1
    assert re.search(r'<input[^>]+id="user_id"[^>]+tabindex="1"[^>]+autofocus', login.text)
    assert re.search(r'<input[^>]+id="password"[^>]+tabindex="2"', login.text)
    password_tag = re.search(r'<input[^>]+id="password"[^>]*>', login.text)
    assert password_tag and "autofocus" not in password_tag.group(0)
    assert re.search(r'<button[^>]+tabindex="3"[^>]*>Sign On</button>', login.text)


def test_mission_control_navigation_does_not_render_icon_registry_names() -> None:
    html = render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-07-21T00:00:00Z",
            "navigation": {"active": "executive_overview"},
            "platform": {},
            "safety": {},
        }
    )
    sidebar = re.search(r'<aside class="mc-sidebar">(.*?)</aside>', html, re.S)
    assert sidebar
    visible = re.sub(r"<[^>]+>", " ", sidebar.group(1))
    for token in (
        "Grid",
        "File",
        "Activity",
        "Route",
        "Briefcase",
        "Waves",
        "Shield",
        "Layers",
        "Plug",
        "Bell",
        "Badge",
        "Chart",
        "Sliders",
        "Book",
    ):
        assert token not in visible
    assert 'aria-hidden="true"><svg' in sidebar.group(1)


def test_human_report_routes_are_html_and_api_routes_are_json() -> None:
    from dashboard.mobile.mobile_app import app

    client = TestClient(app)
    human = client.get(
        "/reports/viewer",
        params={"source": "reports_center", "report_code": "daily_executive_brief"},
    )
    assert human.status_code == 200
    assert human.headers["content-type"].startswith("text/html")
    assert "css-rv-prev" in human.text
    assert 'href="/mobile-launcher"' in human.text
    unknown = client.get("/reports/viewer", params={"report_code": "not-a-report"})
    assert unknown.status_code == 200
    assert unknown.headers["content-type"].startswith("text/html")
    assert "Reason unavailable" in unknown.text
    api = client.get("/api/reports/options_income_executive/view")
    assert api.status_code == 200
    assert api.headers["content-type"].startswith("application/json")
    assert api.json()["viewer_href"].startswith("/reports/viewer")


def test_full_catalogue_has_explicit_twenty_five_check_audit_matrix(tmp_path) -> None:
    matrix = audit_report_catalogue(repo_root=tmp_path)
    assert len(AUDIT_CHECKS) == 25
    assert len(matrix["rows"]) == len(all_definitions())
    assert all(row["outcome"] in {"PASS", "CONDITIONAL PASS", "BLOCKED"} for row in matrix["rows"])
    assert all(set(row["checks"]) == set(AUDIT_CHECKS) for row in matrix["rows"])


def test_balance_contract_maps_providers_and_preserves_unavailable_values() -> None:
    coinbase = build_broker_balance_summary(
        {
            "currency": "USD",
            "assets": [
                {
                    "asset": "BTC",
                    "total": "1.2",
                    "available": "1.0",
                    "held": "0.2",
                    "fiat_equivalent": "60000",
                }
            ],
        },
        broker="COINBASE",
    )
    assert coinbase["asset_breakdown"][0]["held_reserved"] == 0.2
    assert coinbase["account_summary"]["cash"]["availability_state"] == "UNAVAILABLE"
    binance = build_broker_balance_summary(
        {
            "currency": "USDT",
            "portfolio_balance": "900",
            "assets": [
                {"asset": "ETH", "total": 2, "available": 0, "locked": 2, "pending": 0}
            ],
        },
        broker="BINANCE",
    )
    assert binance["account_summary"]["total_account_value"]["value"] == 900
    assert binance["asset_breakdown"][0]["available"] == 0
    assert binance["asset_breakdown"][0]["held_reserved"] == 2

    questrade = build_broker_balance_summary(
        {
            "currency": "CAD",
            "total_equity": 1500,
            "cash": 300,
            "market_value": 1200,
            "buying_power": 600,
            "maintenance_excess": 500,
            "balances": [
                {"currency": "CAD", "total": 250, "available": 200},
                {"currency": "USD", "total": 50, "available": 50},
            ],
        },
        broker="QUESTRADE",
    )
    assert {row["asset_currency"] for row in questrade["asset_breakdown"]} == {"CAD", "USD"}
    assert questrade["account_summary"]["total_equity"]["value"] == 1500

    oanda = build_broker_balance_summary(
        {
            "currency": "USD",
            "balance": "1000",
            "NAV": "1100",
            "unrealizedPL": "100",
            "realizedPL": "20",
            "marginUsed": "50",
            "marginAvailable": "1050",
        },
        broker="OANDA",
    )
    assert oanda["account_summary"]["total_account_value"]["value"] == 1100
    assert oanda["account_summary"]["margin_available"]["value"] == 1050
    assert oanda["execution_allowed"] is False


def test_paper_balance_uses_capital_policy_not_fixed_ten_thousand() -> None:
    summary = build_broker_balance_summary(
        {
            "paper_capital": 200,
            "currency": "USD",
            "paper_collateral_ratio": 0.5,
            "simulation_collateral_ceiling": 10000,
            "simulation_collateral_ceiling_source": "test.explicit_ceiling",
        },
        broker="PAPER",
        mode="PAPER",
    )
    assert summary["paper_account"] is True
    assert summary["account_context"]["authority_label"] == "SIMULATED"
    assert summary["account_summary"]["margin_available"]["value"] == 100
    assert summary["account_summary"]["margin_available"]["value"] != 10000
    assert summary["collateral_margin"]["simulation_collateral_ceiling"]["value"] == 10000
    assert summary["collateral_margin"]["simulation_collateral_ceiling"]["provenance"] == "SEPARATE_SIMULATION_LIMIT"
