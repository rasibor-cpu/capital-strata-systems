"""Phase 177H.1 — launcher SPA enterprise navigation unification tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.enterprise_shell.nav_contract import (
    SPA_SHELL_CACHE,
    build_enterprise_navigation_contract,
    match_active_destination,
)
from dashboard.enterprise_shell.routes import mobile_home_href


def test_nav_contract_primary_destinations():
    contract = build_enterprise_navigation_contract(surface="launcher_spa")
    ids = [d["id"] for d in contract["primary"]]
    assert ids == ["home", "mission_control", "trade", "reports", "more"]
    assert contract["write_routes"] is False
    assert contract["execution_allowed"] is False
    assert contract["canonical_home"] == mobile_home_href(for_surface="mission_control")
    assert contract["reports"]["continuous_scroll_default"] is False
    assert contract["reports"]["default_viewer"] == "paginated"
    assert contract["shell_cache"] == SPA_SHELL_CACHE
    assert contract["pwa_start_url"] == "/mobile-launcher"
    more_ids = {d["id"] for d in contract["more"]}
    assert {"positions", "execution", "risk", "alerts", "options_income", "options_income_report"} <= more_ids
    blob = str(contract).lower()
    assert "ibkr" not in blob or "roadmap-excluded" in blob


def test_nav_contract_rejects_unsafe_bases(monkeypatch):
    monkeypatch.setenv("CSS_MOBILE_DASHBOARD_BASE_URL", "javascript:alert(1)")
    href = mobile_home_href(for_surface="mission_control")
    assert href == "/dashboard"
    assert "javascript:" not in href
    assert "localhost" not in href


def test_active_route_matching_exact_only():
    contract = build_enterprise_navigation_contract(surface="launcher_spa")
    assert match_active_destination(contract, path="/mission-control/executive-overview") == "mission_control"
    assert match_active_destination(contract, spa_screen="trade") == "trade"
    assert match_active_destination(contract, path="/mission-control/reports") == "reports"
    # Broad substring must not falsely activate Reports for unrelated paths
    assert match_active_destination(contract, path="/mission-control/reporting-orphan") is None


def test_launcher_spa_consumes_enterprise_nav():
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    page = client.get("/mobile")
    assert page.status_code == 200
    text = page.text
    assert "CSS enterprise primary navigation" in text
    assert 'data-shell-cache="css-launcher-spa-shell-v177h1"' in text
    assert "CSS Home — return to Mobile Dashboard landing" in text
    assert "Runtime" in text and "DISABLED" in text
    assert "Execution" in text and "BLOCKED" in text
    assert "READ_ONLY" in text
    assert "ADVISORY_ONLY" in text
    assert 'href="/mission-control/executive-overview"' in text or "Mission Control" in text
    assert 'href="/mission-control/reports"' in text or ">Reports<" in text
    assert "css-spa-more-panel" in text
    assert "Positions" in text
    assert "/api/options-income/report.viewer" in text
    assert "enterpriseNav" in text or "enterprise_nav" in text
    assert "localhost" not in text.lower() or "127.0.0.1" not in text  # no phone-inaccessible hard-codes in nav
    assert "ibkr" not in text.lower()


def test_enterprise_navigation_api_get_only():
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    r = client.get("/api/navigation/enterprise")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"].startswith("css.enterprise_navigation")
    assert body["write_routes"] is False
    assert len(body["primary"]) == 5
    assert client.post("/api/navigation/enterprise").status_code in {405, 404, 401, 403}
    assert client.delete("/api/navigation/enterprise").status_code in {405, 404, 401, 403}


def test_pwa_manifest_start_and_cache():
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    man = client.get("/manifest.json")
    assert man.status_code == 200
    data = man.json()
    assert data.get("start_url") == "/mobile-launcher"
    assert data.get("css_shell_cache") == SPA_SHELL_CACHE


def test_reports_paginated_viewer_still_default():
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    r = client.get("/api/options-income/report.viewer")
    assert r.status_code == 200
    assert "css-rv-prev" in r.text
    assert 'data-continuous-default="false"' in r.text
