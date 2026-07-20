"""Phase 176A — Reports Center interaction and mobile integration tests."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.reports_center.ui_contract import category_sections, generatable_selector_options, navigation_payload
from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.pages import render_page
from dashboard.mobile import mobile_reports
from dashboard.mobile.mobile_app import app as mobile_app


def test_desktop_reports_page_has_interactive_controls() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "admin1"}})
    assert 'id="rc-categories"' in html
    assert "data-css-disclosure-trigger" in html
    assert "aria-expanded=" in html
    assert "aria-controls=" in html
    assert 'data-rc-action="view"' in html
    assert 'data-rc-action="generate-open"' in html
    assert 'id="rc-create-form"' in html
    assert 'id="rc-report-code"' in html
    assert "/api/v1/reports/generate" in html
    assert "POST /api/v1/reports/generate" in html or "reports/generate" in html
    assert 'id="rc-library"' in html
    assert 'id="rc-detail"' in html
    # No SQL/path filter controls
    assert 'name="sql"' not in html
    assert 'name="path"' not in html
    # Phase 176B: no broken native details accordion
    assert 'class="rc-accordion"' not in html
    assert "<summary" not in html


def test_desktop_unavailable_reports_have_disabled_generate() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "admin1"}})
    assert "Not generatable" in html
    assert 'data-generatable="false"' in html


def test_ui_contract_parity() -> None:
    cats = category_sections(role="ADMIN")
    assert len(cats) >= 8
    assert all("reports" in c for c in cats)
    gens = generatable_selector_options(role="ADMIN")
    assert len(gens) >= 10
    assert all(g.get("filter_fields") is not None for g in gens)
    assert all(g.get("required_view_permission") for g in gens)
    assert all(g.get("can_generate") for g in gens)
    mobile_nav = navigation_payload(surface="mobile")
    mc_nav = navigation_payload(surface="desktop")
    assert [n["key"] for n in mobile_nav] == [n["key"] for n in mc_nav]
    assert any(n["href"].startswith("/reports") for n in mobile_nav)


def test_mobile_reports_nav_authorized() -> None:
    assert mobile_reports.can_view_reports({"role": "ADMIN"})
    assert mobile_reports.can_view_reports({"role": "VIEWER"})
    assert mobile_reports.can_generate_reports({"role": "ADMIN"})
    assert not mobile_reports.can_generate_reports({"role": "VIEWER"})


def test_mobile_reports_home_contains_menu_and_categories() -> None:
    html = mobile_reports.render_reports_home(
        {"role": "ADMIN", "user_id": "a1", "display_name": "Admin"},
        header_fn=lambda title, user, active: f"<header>{title}</header>",
        page_fn=lambda title, body: body,
        identity_fn=lambda user, extra="": "<div>id</div>",
    )
    assert "Reports menu" in html
    assert "Create Report" in html
    assert "data-css-disclosure-trigger" in html
    assert "ADVISORY ONLY" in html
    assert "EXECUTION BLOCKED" in html
    assert "rc-m-acc" not in html
    assert "<summary" not in html


def test_mobile_reports_hidden_logic_for_unauthorized_role() -> None:
    # TECH without view_reports
    assert not mobile_reports.can_view_reports({"role": "TECH"})


def test_mobile_create_and_generate_wiring(tmp_path: Path, monkeypatch) -> None:
    from backend.reports_center import service as svc_mod

    # Point service archives into tmp via monkeypatch of ReportsCenterService default paths
    original = svc_mod.ReportsCenterService

    class _Svc(original):
        def __init__(self, *a, **k):
            super().__init__(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")

    monkeypatch.setattr(mobile_reports, "_svc", lambda: _Svc())
    html = mobile_reports.render_create(
        {"role": "ADMIN", "user_id": "a1"},
        header_fn=lambda *a, **k: "",
        page_fn=lambda t, b: b,
        identity_fn=lambda *a, **k: "",
        preselect="safety_lock_report",
    )
    assert 'action="/reports/generate"' in html
    assert "safety_lock_report" in html
    result = mobile_reports.generate_from_form(
        {"role": "ADMIN", "user_id": "a1"},
        {"report_code": "safety_lock_report"},
    )
    assert result["status"] == "OK"
    assert result["report"]["advisory_only"] is True
    assert result["report"]["live_trading_blocked"] is True


def test_mobile_generate_denied_for_viewer(tmp_path: Path, monkeypatch) -> None:
    from backend.reports_center.service import ReportsCenterService

    monkeypatch.setattr(
        mobile_reports,
        "_svc",
        lambda: ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "r", audit_root=tmp_path / "a"),
    )
    result = mobile_reports.generate_from_form(
        {"role": "VIEWER", "user_id": "v1"},
        {"report_code": "safety_lock_report"},
    )
    assert result["status"] == "DENIED"


def test_mobile_app_routes_and_nav() -> None:
    client = TestClient(mobile_app)
    # Unauthenticated redirects
    assert client.get("/reports", follow_redirects=False).status_code in {303, 307, 302}
    sw = client.get("/service-worker.js")
    assert sw.status_code == 200
    assert (
        "css-mobile-shell-v177h" in sw.text
        or "css-mobile-shell-v176h1" in sw.text
        or "css-mobile-shell-v176d" in sw.text
        or "css-mobile-shell-v176c" in sw.text
    )
    man = client.get("/manifest.webmanifest")
    assert man.status_code == 200
    assert man.json().get("css_shell_cache") in {
        "css-mobile-shell-v177h",
        "css-mobile-shell-v176h1",
        "css-mobile-shell-v176d",
        "css-mobile-shell-v176c",
    }


def test_mission_control_reports_still_get_only() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    page = client.get(
        "/mission-control/reports",
        headers={"X-CSS-Role": "ADMIN", "X-CSS-User-Id": "admin1"},
    )
    assert page.status_code == 200
    assert "data-css-disclosure-trigger" in page.text
    assert "CSSUIInteraction" in page.text
    assert client.post("/mission-control/api/reports/catalog").status_code in {405, 404, 400}


def test_coming_soon_not_in_generatable_selector() -> None:
    codes = {g["report_code"] for g in generatable_selector_options(role="ADMIN")}
    assert "cash_forecast" not in codes
    assert "live_execution_activity" not in codes
    assert "safety_lock_report" in codes
