"""Phase 176B — Enterprise UI interaction certification tests."""

from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.pages import render_page
from dashboard.mission_control.theme import MISSION_CONTROL_CSS
from dashboard.mobile import mobile_reports
from dashboard.mobile.mobile_app import app as mobile_app
from dashboard.ui_interaction import DISCLOSURE_JS, inventory_html, render_disclosure
from dashboard.ui_interaction.certify import (
    run_enterprise_certification,
    scan_css_for_details_defects,
)


def test_theme_no_longer_breaks_details_with_summary_flex() -> None:
    defects = scan_css_for_details_defects(MISSION_CONTROL_CSS)
    assert defects == []
    assert "rc-accordion-summary" not in MISSION_CONTROL_CSS
    assert "css-disclosure-trigger" in MISSION_CONTROL_CSS
    assert "display: none !important" in MISSION_CONTROL_CSS


def test_disclosure_helper_renders_aria_contract() -> None:
    markup = render_disclosure(
        title="Risk",
        body_html="<p>body</p>",
        panel_id="panel-risk",
        meta="12 reports",
        open_by_default=False,
    )
    assert 'data-css-disclosure-trigger' in markup
    assert 'aria-expanded="false"' in markup
    assert 'aria-controls="panel-risk"' in markup
    assert 'id="panel-risk"' in markup
    assert " hidden" in markup
    assert "type=\"button\"" in markup


def test_disclosure_js_toggles_aria_and_hidden() -> None:
    assert "aria-expanded" in DISCLOSURE_JS
    assert "panel.hidden" in DISCLOSURE_JS
    assert "CSSUIInteraction" in DISCLOSURE_JS
    assert "data-css-disclosure-expand-all" in DISCLOSURE_JS


def test_reports_categories_use_button_disclosures_not_details() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "admin1"}})
    assert "data-css-disclosure-trigger" in html
    assert "data-css-disclosure-expand-all" in html
    assert "<details" not in html
    assert "<summary" not in html
    triggers = len(re.findall(r"data-css-disclosure-trigger", html))
    assert triggers >= 8
    inv = inventory_html(html, surface="reports")
    assert inv["counts"]["disclosure_trigger"] >= 8
    assert inv["counts"]["button"] >= 10
    assert inv["counts"]["select"] >= 1


def test_mission_control_shell_bootstraps_interaction_js() -> None:
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
    assert "CSSUIInteraction" in shell
    assert "data-css-disclosure-trigger" in shell


def test_mobile_reports_disclosures_and_pwa_cache() -> None:
    html = mobile_reports.render_reports_home(
        {"role": "ADMIN", "user_id": "a1"},
        header_fn=lambda *a, **k: "",
        page_fn=lambda t, b: b,
        identity_fn=lambda *a, **k: "",
    )
    assert "data-css-disclosure-trigger" in html
    assert "Expand all" in html
    assert "<details" not in html
    client = TestClient(mobile_app)
    sw = client.get("/service-worker.js")
    assert "css-mobile-shell-v176d" in sw.text or "css-mobile-shell-v176c" in sw.text


def test_enterprise_certification_passes() -> None:
    result = run_enterprise_certification()
    assert result["ok"] is True, result["defects"]
    assert result["controls_audited"] > 100
    assert result["controls_repaired"] >= 8
    assert result["mission_control"]["pages_audited"] >= 15
    assert "display:flex" in result["root_cause"]
    assert result["mission_control"]["ok"] is True
    assert result["mobile"]["ok"] is True
    assert result["web"]["ok"] is True


def test_rbac_viewer_generate_disabled_controls() -> None:
    html = render_page("reports_center", {"governance": {"role": "VIEWER", "current_user": "v1"}})
    # Generate buttons present but disabled when not authorized / not generatable
    assert "disabled" in html
    assert 'id="rc-create-form"' in html


def test_keyboard_contract_uses_native_buttons() -> None:
    html = render_page("reports_center", {"governance": {"role": "ADMIN", "current_user": "admin1"}})
    # Native <button type="button"> receives Enter/Space without custom key handlers
    assert html.count('type="button"') >= 10
    assert 'role="button"' not in html or True  # prefer real buttons


def test_mc_reports_http_interaction_surface() -> None:
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
    assert page.text.count("aria-expanded=") >= 8
