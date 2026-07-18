"""Phase 176C — complete dashboard functional certification tests."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.pages import render_page
from dashboard.ui_function.browser_harness import playwright_available, run_live_browser_smoke
from dashboard.ui_function.certify import (
    certify_mc_nav,
    certify_mobile_reports_apis_mounted,
    certify_reports_workflow,
    certify_web_nav,
    certify_web_refresh_apis,
    run_phase176c_certification,
)
from dashboard.ui_function.registry import (
    all_controls,
    assert_registry_complete,
    control_to_route_matrix,
    registry_summary,
)
from dashboard.web.web_app import create_app as create_web_app


def test_registry_complete_no_unverified_no_broken() -> None:
    assert_registry_complete()
    summary = registry_summary()
    assert summary["total_controls"] >= 100
    assert summary["pages_audited"] >= 20
    assert summary["subtabs_audited"] >= 5
    assert summary["by_status"].get("UNVERIFIED", 0) == 0
    assert summary["by_status"].get("BROKEN", 0) == 0


def test_control_to_route_matrix_populated() -> None:
    matrix = control_to_route_matrix()
    assert len(matrix) == len(all_controls())
    assert any(r["expected_api"] for r in matrix)


def test_mc_nav_functional_not_http_only() -> None:
    result = certify_mc_nav()
    assert result["ok"], result["failures"]


def test_web_nav_and_refresh_apis() -> None:
    assert certify_web_nav()["ok"]
    assert certify_web_refresh_apis()["ok"]


def test_reports_workflow_canonical_service(tmp_path: Path) -> None:
    result = certify_reports_workflow(tmp_path)
    assert result["ok"], result
    assert result["report_id"]
    assert result["print_endpoint"]


def test_reports_subtabs_and_deeplink_markup() -> None:
    from dashboard.mission_control.layout import render_mission_control_shell
    from dashboard.ui_interaction import DISCLOSURE_JS

    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "a"}})
    soup = BeautifulSoup(html, "html.parser")
    tabs = soup.select("[data-css-subtab]")
    assert len(tabs) == 5
    assert soup.select_one("#cat-trading_transactions")
    assert soup.select_one("#cat-panel-trading_transactions")
    assert soup.select_one('[data-css-disclosure-expand-all="true"]')
    assert "openDisclosureForTarget" in DISCLOSURE_JS
    shell = render_mission_control_shell(
        {
            "schema_version": "t",
            "generated_at": "t",
            "platform": {},
            "safety": {"live_trading_blocked": True},
            "runtime": {},
            "governance": {"role": "ADMIN", "current_user": "a"},
        },
        active_section="reports_center",
    )
    assert "openDisclosureForTarget" in shell
    assert "CSSUIInteraction" in shell


def test_reports_generate_disabled_for_viewer() -> None:
    html = render_page("reports_center", {"governance": {"role": "VIEWER", "current_user": "v"}})
    assert "disabled" in html


def test_mc_readonly_pages_ssr() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    for path in (
        "/mission-control/executive-overview",
        "/mission-control/runtime-operations",
        "/mission-control/trade-operations",
        "/mission-control/portfolio",
        "/mission-control/market-intelligence",
        "/mission-control/risk-command",
        "/mission-control/options-income",
        "/mission-control/broker-management",
        "/mission-control/alerts-incidents",
        "/mission-control/certification-readiness",
        "/mission-control/audit-explainability",
        "/mission-control/learning-performance",
        "/mission-control/users-governance",
        "/mission-control/system-configuration",
        "/mission-control/documentation-runbooks",
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        assert "READ ONLY" in res.text
        # No writable forms on these pages
        soup = BeautifulSoup(res.text, "html.parser")
        assert soup.select("form") == []


def test_web_scc_nav_links_clickable() -> None:
    html = create_web_app()  # ensure import
    from dashboard.web import web_app

    page = web_app._session_command_centre_page()
    assert "scc-nav-link" in page
    assert "scc-nav-disabled" in page
    assert "session-command-centre load failed" in page
    assert "DATA UNAVAILABLE" in page


def test_mobile_reports_print_mounted() -> None:
    result = certify_mobile_reports_apis_mounted()
    assert result["ok"], result


def test_mobile_reports_library_latest(tmp_path: Path, monkeypatch) -> None:
    from dashboard.mobile import mobile_reports
    from backend.reports_center.service import ReportsCenterService

    class _Svc(ReportsCenterService):
        def __init__(self, *a, **k):
            super().__init__(repo_root=tmp_path, archive_root=tmp_path / "r", audit_root=tmp_path / "a")

    monkeypatch.setattr(mobile_reports, "_svc", lambda: _Svc())
    svc = _Svc()
    gen = svc.generate("safety_lock_report", filters={}, role="ADMIN", user_id="a", persist=True)
    assert gen.get("status") == "OK"
    listing = svc.list_library(filters={"view": "latest"}, role="ADMIN")
    assert listing.get("status") == "OK"
    assert listing.get("view") == "latest"
    html = mobile_reports.render_library(
        {"role": "ADMIN", "user_id": "a"},
        header_fn=lambda *a, **k: "",
        page_fn=lambda t, b: b,
        identity_fn=lambda *a, **k: "",
        filters={"view": "latest"},
    )
    assert "Latest" in html


def test_phase176c_certification_bundle(tmp_path: Path) -> None:
    result = run_phase176c_certification(tmp_path)
    assert result["ok"], result


def test_safety_locks_unchanged_in_generate(tmp_path: Path) -> None:
    from backend.reports_center.service import ReportsCenterService

    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "r", audit_root=tmp_path / "a")
    gen = svc.generate("safety_lock_report", filters={}, role="ADMIN", user_id="a", persist=True)
    assert gen.get("advisory_only") is True
    assert gen.get("execution_allowed") is False
    assert gen.get("live_trading_blocked") is True
    assert gen.get("broker_execution_armed") is False


def test_reports_catalog_json_is_browser_parseable() -> None:
    import json

    from dashboard.mission_control.layout import render_mission_control_shell

    shell = render_mission_control_shell(
        {
            "schema_version": "t",
            "generated_at": "t",
            "platform": {},
            "safety": {"live_trading_blocked": True},
            "runtime": {},
            "governance": {"role": "ADMIN", "current_user": "a"},
        },
        active_section="reports_center",
    )
    soup = BeautifulSoup(shell, "html.parser")
    catalog = soup.select_one("#rc-catalog-data")
    auth = soup.select_one("#rc-auth-data")
    assert catalog and auth
    assert "&quot;" not in catalog.get_text()
    payload = json.loads(catalog.get_text())
    assert "categories" in payload and "generatable" in payload
    assert json.loads(auth.get_text()).get("role") == "ADMIN"


def test_secret_tokens_not_in_mc_reports_html() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "a"}})
    lowered = html.lower()
    for token in ("api_key", "private_key", "password=", "bearer "):
        assert token not in lowered


@pytest.mark.browser
def test_live_browser_optional() -> None:
    import os

    if not playwright_available():
        pytest.skip("Playwright not installed — see requirements-browser.txt")
    base = os.environ.get("CSS_LIVE_BROWSER_BASE_URL", "").strip()
    if not base:
        pytest.skip("Set CSS_LIVE_BROWSER_BASE_URL to a running CSS host for live browser tests")
    result = run_live_browser_smoke(base)
    assert result.get("ok"), result
