"""Phase 176H.3 — Android pointercancel remediation (scroll isolation)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.mission_control.theme import MISSION_CONTROL_CSS

AUTH = {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}


def _mobile_css() -> str:
    idx = MISSION_CONTROL_CSS.index("@media (max-width: 1100px)")
    end = MISSION_CONTROL_CSS.find("@media (max-width: 680px)", idx)
    return MISSION_CONTROL_CSS[idx:end]


def _desktop_prefix() -> str:
    return MISSION_CONTROL_CSS[: MISSION_CONTROL_CSS.index("@media (max-width: 1100px)")]


def test_mobile_css_isolates_document_scroll() -> None:
    mobile = _mobile_css()
    assert "height: 100%" in mobile
    assert "max-height: 100dvh" in mobile
    assert "overflow: hidden" in mobile
    assert "display: flex" in mobile
    assert "flex-direction: column" in mobile
    assert "height: 100dvh" in mobile
    assert "flex: 0 0 auto" in mobile
    assert ".mc-main" in mobile
    assert "flex: 1" in mobile
    assert "min-height: 0" in mobile
    # Sidebar and main scroll internally (not the HTML document).
    assert mobile.count("overflow: auto") >= 2


def test_desktop_grid_sidebar_sticky_unchanged() -> None:
    desktop = _desktop_prefix()
    assert "grid-template-columns: 288px 1fr" in desktop
    assert "position: sticky" in desktop
    assert "height: 100vh" in desktop
    assert "overflow-y: auto" in desktop
    # Desktop must not get the mobile flex shell rules outside the media query.
    assert "flex-direction: column" not in desktop
    assert "height: 100dvh" not in desktop


def test_no_javascript_navigation_helpers() -> None:
    html = render_mission_control_shell(
        {
            "schema_version": "t",
            "generated_at": "2026-07-19T00:00:00Z",
            "platform": {},
            "safety": {
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
            },
            "runtime": {},
            "reports_authorization": {
                "authenticated": True,
                "user_id": "00000",
                "role": "SUPER_USER",
                "reports_view": True,
                "reports_generate": True,
            },
        },
        active_section="executive_overview",
    )
    assert "location.assign" not in html
    assert "Force navigation when the browser suppresses" not in html
    for section in MISSION_CONTROL_SECTIONS:
        assert f'href="{section.route}"' in html


def test_safety_locks_unchanged_on_mc_html() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    res = client.get("/mission-control/executive-overview", headers=AUTH)
    assert res.status_code == 200
    assert "location.assign" not in res.text
    assert "BLOCKED" in res.text


def test_playwright_mobile_document_is_not_scroll_owner_and_nav_hit_target() -> None:
    import pytest

    playwright = pytest.importorskip("playwright.sync_api")
    sync_playwright = playwright.sync_playwright

    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    html = client.get("/mission-control/executive-overview", headers=AUTH).text
    assert "height: 100dvh" in html
    assert "location.assign" not in html

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 412, "height": 915},
            device_scale_factor=2.625,
            is_mobile=True,
            has_touch=True,
            user_agent=(
                "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        geom = page.evaluate(
            """() => {
              const csHtml = getComputedStyle(document.documentElement);
              const csBody = getComputedStyle(document.body);
              const shell = document.querySelector('.mc-shell');
              const aside = document.querySelector('.mc-sidebar');
              const main = document.querySelector('.mc-main');
              const toggle = document.querySelector('.mc-nav-toggle-btn');
              if (toggle) toggle.click();
              const a = document.querySelector('.mc-nav a[href="/mission-control/reports"]');
              const r = a.getBoundingClientRect();
              const top = document.elementFromPoint(r.left + r.width/2, r.top + r.height/2);
              return {
                htmlOverflow: csHtml.overflow,
                bodyOverflow: csBody.overflow,
                docCanScroll: document.documentElement.scrollHeight > document.documentElement.clientHeight + 1,
                shellDisplay: getComputedStyle(shell).display,
                shellFlexDir: getComputedStyle(shell).flexDirection,
                asideOverflow: getComputedStyle(aside).overflowY || getComputedStyle(aside).overflow,
                mainOverflow: getComputedStyle(main).overflowY || getComputedStyle(main).overflow,
                mainFlex: getComputedStyle(main).flexGrow,
                mainMinHeight: getComputedStyle(main).minHeight,
                topTag: top && top.tagName,
                topHref: top && top.getAttribute('href'),
                href: a.getAttribute('href'),
              };
            }"""
        )
        assert geom["htmlOverflow"] == "hidden"
        assert geom["bodyOverflow"] == "hidden"
        assert geom["docCanScroll"] is False
        assert geom["shellDisplay"] == "flex"
        assert geom["shellFlexDir"] == "column"
        assert "auto" in str(geom["asideOverflow"])
        assert "auto" in str(geom["mainOverflow"])
        assert geom["mainFlex"] == "1"
        assert geom["mainMinHeight"] == "0px"
        assert geom["topTag"] == "A"
        assert geom["topHref"] == "/mission-control/reports"
        assert geom["href"] == "/mission-control/reports"
        browser.close()


def test_playwright_desktop_keeps_grid_sticky_sidebar() -> None:
    import pytest

    playwright = pytest.importorskip("playwright.sync_api")
    sync_playwright = playwright.sync_playwright

    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    html = client.get("/mission-control/executive-overview", headers=AUTH).text

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
        )
        page = context.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        desktop = page.evaluate(
            """() => {
              const shell = document.querySelector('.mc-shell');
              const aside = document.querySelector('.mc-sidebar');
              const htmlEl = document.documentElement;
              return {
                shellDisplay: getComputedStyle(shell).display,
                shellGrid: getComputedStyle(shell).gridTemplateColumns,
                asidePos: getComputedStyle(aside).position,
                asideOverflow: getComputedStyle(aside).overflowY,
                htmlOverflow: getComputedStyle(htmlEl).overflow,
                docCanScroll: htmlEl.scrollHeight > htmlEl.clientHeight + 1,
              };
            }"""
        )
        assert desktop["shellDisplay"] == "grid"
        assert "288px" in desktop["shellGrid"]
        assert desktop["asidePos"] == "sticky"
        assert desktop["asideOverflow"] == "auto"
        # Desktop must not force html overflow:hidden from the mobile rules.
        assert desktop["htmlOverflow"] != "hidden"
        browser.close()
