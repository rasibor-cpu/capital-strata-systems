"""Browser UX tests for the mandatory onboarding / risk-acceptance page (Playwright, Chromium).

Skipped when Playwright is not installed (same convention as the existing phase176 UI tests).
The page is served by the real router; identity comes from a test cookie.
"""
from __future__ import annotations

import json
import socket
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from css118_support import KEY  # noqa: E402
from backend.trading_profiles.api import ONBOARDING_PATH, create_trading_profiles_router  # noqa: E402
from backend.trading_profiles.service import TradingProfileService  # noqa: E402

TOTAL_PAGES = 12


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def server(tmp_path):
    root = tmp_path / "tp"

    def resolver(request):
        user = request.cookies.get("test_user")
        return {"user_id": user, "session_id": "sess-" + user} if user else None

    app = FastAPI()
    app.include_router(create_trading_profiles_router(
        user_resolver=resolver, service_factory=lambda: TradingProfileService(root, key_provider=lambda: KEY)))
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield {"url": f"http://127.0.0.1:{port}", "root": root}
    srv.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def _page(browser, server, *, user="ux-user", viewport=None):
    context = browser.new_context(viewport=viewport or {"width": 1280, "height": 900})
    context.add_cookies([{"name": "test_user", "value": user, "url": server["url"]}])
    page = context.new_page()
    page.goto(server["url"] + ONBOARDING_PATH)
    return page


def _choose_settings(page, mode="CSS Autonomous Trading", personality="Balanced"):
    page.get_by_label(mode, exact=True).check()
    page.select_option("#personality", personality)
    page.click("#review-settings-btn")
    page.wait_for_selector("#step-summary:not(.hidden)")
    page.click("#to-agreement-btn")
    page.wait_for_selector("#step-reader:not(.hidden)")


def _wait_page(page, n):
    page.wait_for_function(f"document.getElementById('end-marker').textContent.includes('page {n} of {TOTAL_PAGES}')")


def _consent_state(server):
    return json.loads((server["root"] / "consent_state.json").read_text())


def test_initial_state_acknowledgement_unchecked_and_accept_disabled(server, browser):
    page = _page(browser, server)
    assert page.is_checked("#ack-checkbox") is False
    assert page.is_disabled("#ack-checkbox") and page.is_disabled("#accept-btn")


def test_scroll_gating_on_every_page_then_explicit_acknowledgement(server, browser):
    page = _page(browser, server)
    _choose_settings(page)
    assert page.locator("#summary li").count() >= 5  # risk implications shown before the agreement
    gated_pages = []
    for n in range(1, TOTAL_PAGES + 1):
        _wait_page(page, n)
        marker_hidden = page.evaluate("""(() => {
            const r = document.getElementById('reader').getBoundingClientRect();
            const m = document.getElementById('end-marker').getBoundingClientRect();
            return m.bottom > r.bottom + 1; })()""")
        if marker_hidden:
            gated_pages.append(n)
            page.wait_for_timeout(150)  # give the observer a chance to (wrongly) fire
            assert page.is_disabled("#next-btn"), f"page {n}: next must stay disabled until the end is reached"
            # Scroll to just short of the end: the end-of-page marker is still partly hidden.
            page.evaluate("""(() => { const r = document.getElementById('reader'), m = document.getElementById('end-marker');
                const gap = m.getBoundingClientRect().bottom - r.getBoundingClientRect().bottom;
                r.scrollTop = Math.max(0, gap - m.offsetHeight / 2); })()""")
            assert page.evaluate("""(() => { const r = document.getElementById('reader').getBoundingClientRect();
                return document.getElementById('end-marker').getBoundingClientRect().bottom > r.bottom; })()""")
            page.wait_for_timeout(150)
            assert page.is_disabled("#next-btn"), f"page {n}: almost at the end is not the end"
            page.evaluate("(() => { const r = document.getElementById('reader'); r.scrollTop = r.scrollHeight; })()")
        page.wait_for_function("!document.getElementById('next-btn').disabled")
        page.click("#next-btn")
    page.wait_for_selector("#step-accept:not(.hidden)")
    assert len(gated_pages) >= 8, gated_pages  # most pages need real scrolling at this viewport
    assert page.is_enabled("#ack-checkbox") and not page.is_checked("#ack-checkbox")
    assert page.is_disabled("#accept-btn")
    page.check("#ack-checkbox")
    assert page.is_enabled("#accept-btn")
    page.uncheck("#ack-checkbox")
    assert page.is_disabled("#accept-btn")
    page.check("#ack-checkbox")
    page.click("#accept-btn")
    page.wait_for_selector("#step-done:not(.hidden)")
    receipt = page.inner_text("#receipt")
    assert "Live trading authorized" in receipt and "No" in receipt
    service = TradingProfileService(server["root"], key_provider=lambda: KEY)
    assert service.consent.verify_active("ux-user") == (True, "consent_valid")
    review = next(iter(_consent_state(server)["reviews"].values()))
    assert all(p.get("reviewed_at_utc") for p in review["pages"].values())


def test_keyboard_and_screen_reader_path_via_end_of_page_marker(server, browser):
    page = _page(browser, server, user="kb-user")
    _choose_settings(page)
    for n in range(1, TOTAL_PAGES + 1):
        _wait_page(page, n)
        page.focus("#reader")
        page.keyboard.press("Tab")  # next focusable element inside the region is the end-of-page marker
        assert page.evaluate("document.activeElement.id") == "end-marker"
        page.wait_for_function("!document.getElementById('next-btn').disabled")
        page.click("#next-btn")
    page.wait_for_selector("#step-accept:not(.hidden)")
    page.keyboard.press("Tab")
    page.check("#ack-checkbox")
    page.click("#accept-btn")
    page.wait_for_selector("#step-done:not(.hidden)")
    methods = {p["method"] for p in next(iter(_consent_state(server)["reviews"].values()))["pages"].values()}
    assert methods <= {"keyboard_end", "non_scrollable_presented", "scroll_bottom"} and "keyboard_end" in methods


def test_non_scrollable_pages_on_tall_screens_are_presented_without_forced_scroll(server, browser):
    page = _page(browser, server, user="tall-user", viewport={"width": 1280, "height": 8000})
    _choose_settings(page)
    for n in range(1, TOTAL_PAGES + 1):
        _wait_page(page, n)
        page.wait_for_function("!document.getElementById('next-btn').disabled")
        page.click("#next-btn")
    page.wait_for_selector("#step-accept:not(.hidden)")
    methods = {p["method"] for p in next(iter(_consent_state(server)["reviews"].values()))["pages"].values()}
    assert methods == {"non_scrollable_presented"}
    assert not page.is_checked("#ack-checkbox") and page.is_disabled("#accept-btn")


def test_mobile_viewport_flow(server, browser):
    page = _page(browser, server, user="mobile-user", viewport={"width": 390, "height": 844})
    _choose_settings(page, mode="CSS-Assisted Trading", personality="Conservative")
    _wait_page(page, 1)
    assert page.is_disabled("#next-btn")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")  # no horizontal page scroll
    for n in range(1, TOTAL_PAGES + 1):
        _wait_page(page, n)
        page.evaluate("(() => { const r = document.getElementById('reader'); r.scrollTop = r.scrollHeight; })()")
        page.wait_for_function("!document.getElementById('next-btn').disabled")
        page.click("#next-btn")
    page.check("#ack-checkbox")
    page.click("#accept-btn")
    page.wait_for_selector("#step-done:not(.hidden)")


def test_bypass_from_the_browser_is_rejected_by_the_server(server, browser):
    page = _page(browser, server, user="bypass-user")
    _choose_settings(page)
    _wait_page(page, 1)
    result = page.evaluate("""async () => {
        const api = '/api/v1/trading-profiles';
        const reviews = await (await fetch(api + '/consent/reviews', {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({change_id: 'chg-forged'})})).json();
        return reviews;
    }""")
    assert result["ok"] is False
    # Enabling the controls in the DOM does not help: the server still requires every page.
    page.evaluate("document.getElementById('ack-checkbox').disabled = false; document.getElementById('accept-btn').disabled = false;")
    page.evaluate("document.getElementById('step-accept').classList.remove('hidden')")
    page.check("#ack-checkbox")
    page.click("#accept-btn")
    page.wait_for_function("document.getElementById('error').textContent.includes('pages_not_reviewed')")
    assert TradingProfileService(server["root"], key_provider=lambda: KEY).preferences.get("bypass-user").active is None


def test_emergency_pause_works_before_any_acceptance(server, browser):
    page = _page(browser, server, user="pause-user")
    page.click("#pause-btn")
    page.wait_for_function("document.getElementById('pause-status').textContent.includes('paused')")
    assert TradingProfileService(server["root"], key_provider=lambda: KEY).preferences.get("pause-user").paused is True
