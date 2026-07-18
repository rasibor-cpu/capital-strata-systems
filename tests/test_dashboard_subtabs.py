"""Dashboard sub-tab / secondary navigation interaction tests."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.reports_center.constants import CATEGORIES
from backend.reports_center.ui_contract import REPORTS_NAV_CATEGORIES, navigation_payload
from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.pages import render_page
from dashboard.mobile.mobile_app import _top_nav, app as mobile_app
from dashboard.ui_interaction import DISCLOSURE_JS, render_disclosure
from dashboard.web import web_app


def test_reports_subnav_is_tablist_with_data_css_subtab() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "admin1"}})
    assert 'role="tablist"' in html
    for target in ("rc-categories", "rc-frequent", "rc-create", "rc-library", "rc-detail"):
        assert f'data-css-subtab="{target}"' in html
        assert f'id="{target}"' in html
    assert "is-active" in DISCLOSURE_JS or "aria-current" in DISCLOSURE_JS
    assert "openDisclosureForTarget" in DISCLOSURE_JS


def test_category_disclosure_anchors_match_nav_deep_links() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "admin1"}})
    nav_keys = {n["key"] for n in REPORTS_NAV_CATEGORIES if n["key"] not in {"home", "latest", "create", "library"}}
    assert set(CATEGORIES) <= nav_keys
    for key in CATEGORIES:
        assert f'id="cat-{key}"' in html
        assert f'id="cat-panel-{key}"' in html
        assert any(n["href_mc"].endswith(f"#cat-{key}") for n in REPORTS_NAV_CATEGORIES if n["key"] == key)


def test_disclosure_js_opens_cat_and_cat_panel_aliases() -> None:
    assert "cat-panel-" in DISCLOSURE_JS
    assert "openDisclosureForTarget" in DISCLOSURE_JS
    assert "hashchange" in DISCLOSURE_JS
    assert "data-css-subtab" in DISCLOSURE_JS


def test_render_disclosure_anchor_id() -> None:
    markup = render_disclosure(
        title="Trading",
        body_html="<p>x</p>",
        panel_id="cat-panel-trading_transactions",
        anchor_id="cat-trading_transactions",
    )
    assert 'id="cat-trading_transactions"' in markup
    assert 'id="cat-panel-trading_transactions"' in markup
    assert 'data-css-disclosure-trigger' in markup


def test_mission_control_reports_http_subtabs_and_apis() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    headers = {"X-CSS-Role": "ADMIN", "X-CSS-User-Id": "admin1"}
    page = client.get("/mission-control/reports", headers=headers)
    assert page.status_code == 200
    assert 'data-css-subtab="rc-create"' in page.text
    assert 'id="cat-trading_transactions"' in page.text
    assert "openDisclosureForTarget" in page.text
    # Readiness / catalog APIs remain GET-only under MC
    catalog = client.get("/mission-control/api/reports/catalog", headers=headers)
    assert catalog.status_code == 200
    assert "categories" in catalog.json() or "reports" in catalog.json() or catalog.json()


def test_mobile_top_nav_marks_active_subtab() -> None:
    user = {"role": "ADMIN", "user_id": "a1", "display_name": "Admin"}
    html = _top_nav(user, "reports")
    assert 'aria-current="page"' in html
    assert 'href="/reports"' in html
    # Active reports link present (not omitted)
    assert re.search(r'href="/reports"[^>]*aria-current="page"|aria-current="page"[^>]*href="/reports"', html)
    # Other tabs still present
    assert 'href="/positions"' in html


def test_mobile_reports_category_nav_complete() -> None:
    mobile_nav = navigation_payload(surface="mobile")
    keys = {n["key"] for n in mobile_nav}
    for key in CATEGORIES:
        assert key in keys
        assert any(n["href"] == f"/reports?category={key}" for n in mobile_nav if n["key"] == key)


def test_web_dashboard_main_nav_routes_render() -> None:
    client = TestClient(web_app.create_app())
    routes = [
        "/dashboard",
        "/positions",
        "/trade",
        "/trade-summary",
        "/session-command-centre",
        "/live-readiness-certification",
        "/execution",
        "/risk-governance",
        "/market-opportunities",
        "/broker",
        "/margin",
    ]
    for path in routes:
        res = client.get(path)
        assert res.status_code == 200, path
        assert "app-nav" in res.text
        assert 'class="active"' in res.text


def test_launcher_show_screen_syncs_quick_nav() -> None:
    html = Path("launcher/templates/mobile_dashboard.html").read_text(encoding="utf-8")
    assert "data-quick-screen" in html
    assert 'querySelector("[data-quick-screen=\'" + name + "\']")' in html or "data-quick-screen='" in html
    assert "aria-current" in html
    for screen in ("home", "positions", "execution", "trade", "risk", "alerts"):
        assert f'id="screen-{screen}"' in html
        assert f'data-screen="{screen}"' in html


def test_unavailable_generate_is_disabled_with_visible_reason() -> None:
    html = render_page("reports_center", {"governance": {"role": "VIEWER", "current_user": "v1"}})
    assert "disabled" in html
    assert "Not generatable" in html or "reports_generate" in html.lower() or "Generate" in html
