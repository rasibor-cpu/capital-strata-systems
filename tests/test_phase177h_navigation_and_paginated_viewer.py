"""Phase 177H — enterprise navigation shell and paginated report viewer tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.enterprise_shell.reports_hub import build_reports_hub_payload
from dashboard.enterprise_shell.routes import (
    breadcrumbs_for,
    cross_surface_href,
    mobile_home_href,
    mission_control_home_href,
)
from dashboard.enterprise_shell.shell import (
    render_brand_home_link,
    render_breadcrumbs,
    render_mobile_enterprise_nav,
    render_mobile_footer_nav,
)
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.reports_viewer import render_paginated_viewer


def test_canonical_mobile_home_is_basic_landing():
    assert mobile_home_href(for_surface="mobile") == "/mobile-launcher"


def test_mission_control_home_uses_env_base(monkeypatch):
    monkeypatch.setenv("CSS_MISSION_CONTROL_BASE_URL", "https://example.test")
    href = mission_control_home_href(for_surface="mobile")
    assert href == "https://example.test/mission-control/executive-overview"
    monkeypatch.delenv("CSS_MISSION_CONTROL_BASE_URL", raising=False)


def test_cross_surface_rejects_open_redirect_schemes(monkeypatch):
    monkeypatch.setenv("CSS_MISSION_CONTROL_BASE_URL", "javascript:alert(1)")
    href = cross_surface_href("/mission-control/reports", target="mission_control")
    assert href == "/mission-control/reports"


def test_breadcrumbs_mark_current_and_are_navigable():
    items = breadcrumbs_for([("Home", "/dashboard"), ("Reports", "/reports"), ("Detail", None)])
    assert items[0]["href"] == "/dashboard"
    assert items[-1]["current"] is True
    assert items[-1]["href"] is None
    html = render_breadcrumbs([("Home", "/dashboard"), ("Reports", None)])
    assert 'aria-current="page"' in html
    assert "Home" in html


def test_brand_and_home_links_point_to_landing():
    brand = render_brand_home_link(for_surface="mobile")
    assert 'href="/mobile-launcher"' in brand
    assert "aria-label" in brand
    nav = render_mobile_enterprise_nav({"role": "VIEWER"}, "risk", can_view_reports=True)
    assert ">Home<" in nav
    assert "Reports" in nav
    assert "More modules" in nav
    footer = render_mobile_footer_nav("dashboard", can_view_reports=True)
    assert 'aria-label="Mobile primary navigation"' in footer
    assert "Home" in footer


def test_reports_hub_groups_and_honest_coming_soon():
    hub = build_reports_hub_payload(role="VIEWER", surface="mobile")
    assert hub["ok"] is True
    assert hub["write_routes"] is False
    keys = {g["key"] for g in hub["groups"]}
    assert {"executive", "financial", "risk_operations", "governance"} <= keys
    statuses = {r.get("status") for g in hub["groups"] for r in g["reports"]}
    assert "COMING_SOON" in statuses or any(
        r.get("readiness") == "not_yet_implemented" for g in hub["groups"] for r in g["reports"]
    )


def test_paginated_viewer_is_one_page_default_not_continuous_scroll():
    doc = {
        "title": "Sample",
        "report_id": "rpt-1",
        "css_version": "test",
        "commit_reference": "abc",
        "generated_at": "2026-07-20T00:00:00Z",
        "page_count": 2,
        "presentation": {
            "page_size": "A4",
            "viewer_hints": {"continuous_scroll_default": False},
        },
        "pages": [
            {"page_number": 1, "page_type": "cover", "title": "Cover", "lines": ["A"]},
            {"page_number": 2, "page_type": "content", "title": "Body", "lines": ["B"]},
        ],
    }
    html = render_paginated_viewer(doc, reports_href="/reports", home_href="/dashboard")
    assert 'data-continuous-default="false"' in html
    assert "css-rv-prev" in html and "css-rv-next" in html
    assert "css-rv-selector" in html
    assert "Table of Contents" in html
    assert "Back to Reports" in html
    assert 'href="/dashboard"' in html
    assert "Page 1 of 2" in html or "1 / 2" in html
    assert 'width:min(210mm' in html or "210mm" in html
    # Only one page visible initially (others hidden)
    assert html.count("css-rv-page") >= 2
    assert 'hidden' in html


def test_mission_control_shell_has_home_and_navigable_breadcrumbs():
    html = render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-07-20T00:00:00Z",
            "platform": {"product": "CSS", "runtime_mode": "DISABLED", "platform_status": "OK"},
            "safety": {"live_trading_blocked": True, "safety_status": "BLOCKED"},
            "runtime": {"heartbeat_status": "OK"},
            "authorization": {"role": "VIEWER", "permissions": []},
        },
        active_section="options_income",
    )
    assert 'data-css-home="1"' in html
    assert "Home" in html
    assert "css-breadcrumbs" in html
    assert "Options Income" in html
    assert "Runtime" in html and "DISABLED" in html
    assert "Execution" in html and "BLOCKED" in html


def test_mobile_app_nav_uses_enterprise_shell():
    from dashboard.mobile import mobile_app as ma

    html = ma._top_nav({"role": "VIEWER", "user_id": "t"}, "dashboard")
    assert "Home" in html
    assert "Mission Control" in html
    assert "css-brand-home" in html


def test_reports_discovery_get_only_on_mobile_app():
    from dashboard.mobile.mobile_app import app

    client = TestClient(app)
    r = client.get("/api/reports")
    assert r.status_code == 200
    body = r.json()
    assert body.get("write_routes") is False
    assert "groups" in body
    # No write methods
    assert client.post("/api/reports").status_code in {405, 404, 401, 403}
    assert client.delete("/api/reports/x").status_code in {405, 404, 401, 403}


def test_options_income_viewer_route_on_launcher():
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    r = client.get("/api/options-income/report.viewer")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "css-rv-prev" in r.text
    assert "Previous" in r.text
    meta = client.get("/api/reports/options_income_executive/metadata")
    assert meta.status_code == 200
    assert meta.json().get("advisory_only") is True


def test_safety_invariants_unchanged_by_shell():
    from backend.runtime.platform_status import build_platform_status
    from backend.runtime.runtime_mode import resolve_runtime_mode

    resolved = resolve_runtime_mode()
    assert resolved.runtime_mode.value == "DISABLED" or str(resolved.runtime_mode) == "DISABLED"
    assert resolved.fail_closed is True
    status = build_platform_status()
    assert status["runtime_mode"] == "DISABLED"
    assert status["execution_authority"] is False or str(status["execution_authority"]).upper() == "BLOCKED"
    assert status["execution_state"] == "BLOCKED"
