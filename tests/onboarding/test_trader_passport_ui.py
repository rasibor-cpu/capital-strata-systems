"""CSS Trader Passport UI tests (Issue #102): real browser, real API, temporary store.

Runs the standalone Passport app on a free local port (never 8765) and drives it with Playwright/Chromium.
Requires: playwright (pip) and a Chromium build. Accessibility checks also need axe-core: set CSS_AXE_PATH to
axe.min.js (e.g. from `npm install axe-core`). Without them these tests SKIP and say why; they never pass silently.
Set CSS_PASSPORT_EVIDENCE_DIR to keep screenshots.

S24-class viewport here is an emulation (360x780 CSS px, DPR 3, touch). It is not physical-device evidence.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

from backend.app.auth.token_store import token_store  # noqa: E402
from backend.app.onboarding.service import OnboardingService  # noqa: E402
from backend.app.onboarding.standalone import create_app  # noqa: E402
from backend.app.onboarding.store import OnboardingStore  # noqa: E402

from .test_trader_passport import BASE  # noqa: E402

S24 = {"viewport": {"width": 360, "height": 780}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
AXE = os.getenv("CSS_AXE_PATH")
EVIDENCE = Path(os.getenv("CSS_PASSPORT_EVIDENCE_DIR", "")) if os.getenv("CSS_PASSPORT_EVIDENCE_DIR") else None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert port != 8765
    return port


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    os.environ["CSS_PASSPORT_DEMO"] = "1"
    store = OnboardingStore(tmp_path_factory.mktemp("passport"))
    app = create_app(OnboardingService(store))
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        exe = os.getenv("CSS_CHROMIUM_PATH") or next(
            (str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")), None)
        try:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception as e:                                   # no browser available: skip, loudly
            pytest.skip(f"Chromium not available: {e}")
        yield b
        b.close()


def _page(browser, server, user, **ctx):
    token = token_store.create_session(user, ["user"], minutes=30)
    context = browser.new_context(**{**S24, **ctx})
    context.add_init_script(f"sessionStorage.setItem('css_token', {json.dumps(token)});")
    page = context.new_page()
    page.goto(server + "/passport/app/index.html")
    page.wait_for_selector("h1")
    return page, token


def _shot(page, name):
    if EVIDENCE:
        _settle(page)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{name}.png"), full_page=True)


def _settle(page):
    """Wait until every running animation/transition has finished, so checks see the final rendering."""
    page.evaluate("Promise.all(document.getAnimations().map(a => a.finished.catch(() => null)))")


def _axe(page):
    if not AXE:
        return None
    _settle(page)
    page.add_script_tag(path=AXE)
    res = page.evaluate("async () => (await axe.run(document, {runOnly: ['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']})).violations"
                        ".map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length}))")
    return res


def _current(page, server, token):
    return page.request.get(server + "/passport/session", headers={"Authorization": "Bearer " + token}).json()


def _answer_stage(page, stage, persona, keyboard=False):
    for q in stage.get("questions", []):
        v = persona.get(q["id"])
        t = q["type"]
        if v is None:
            continue
        if t in ("text", "email", "phone"):
            page.fill(f"#{q['id']}", v)
        elif t == "country":
            page.select_option(f"#{q['id']}", v)
        elif t == "consent":
            if v:
                page.check(f"#{q['id']}")
        elif t in ("single", "quiz"):
            if keyboard:
                page.focus(f"#{q['id']}-{q['options'][0]['value']}")
                idx = [o["value"] for o in q["options"]].index(v)
                for _ in range(idx):
                    page.keyboard.press("ArrowDown")
                page.keyboard.press("Space")
            else:
                page.click(f"label[for='{q['id']}-{v}']")
        elif t == "boolean":
            page.click(f"label[for='{q['id']}-{'true' if v else 'false'}']")
        elif t == "multi":
            for x in v:
                page.click(f"label[for='{q['id']}-{x}']")
        elif t == "matrix":
            for row, band in v.items():
                page.click(f"label[for='{q['id']}__{row}-{band}']")
        elif t == "rank":
            for x in v:
                page.click(f"[data-qid='{q['id']}'] button[data-value='{x}']")


def _layout_checks(page):
    overflow = page.evaluate("document.scrollingElement.scrollWidth - window.innerWidth")
    assert overflow <= 1, f"horizontal overflow {overflow}px"
    small = page.evaluate("""[...document.querySelectorAll('.option label, .btn, .field input, .field select, .consent, .rank-btn')]
        .filter(e => e.offsetParent !== null).map(e => e.getBoundingClientRect())
        .filter(r => r.height < 44 || r.width < 44).length""")
    assert small == 0, f"{small} tap targets smaller than 44px"
    clipped = page.evaluate("""[...document.querySelectorAll('.options, .segmented, .field, .card, .kpi, .table-wrap table')]
        .filter(e => e.offsetParent !== null && e.scrollWidth - e.clientWidth > 1 && !e.closest('.table-wrap'))
        .map(e => e.className)""")
    assert clipped == [], f"content overflows its container: {clipped}"


def test_full_flow_s24_accessibility_and_layout(browser, server):
    page, token = _page(browser, server, "ui-full")
    seen, violations = [], {}
    for step in range(40):
        view = _current(page, server, token)
        stage = view["stage"]
        assert page.locator("h1").first.inner_text().strip(), "every step has a title"
        if stage["kind"] != "result":
            assert page.get_attribute("#progressbar", "aria-valuenow") == str(view["progress"]["position"])
        _layout_checks(page)
        v = _axe(page)
        if v:
            violations[stage["id"]] = v
        _shot(page, f"s24_{step:02d}_{stage['id']}")
        if stage["kind"] == "result":
            break
        seen.append(stage["id"])
        _answer_stage(page, stage, BASE, keyboard=stage["id"] == "behaviour")   # one step entirely by keyboard
        page.click("#next")
        page.wait_for_function("(id) => !document.querySelector('[data-qid]') || true", arg=stage["id"])
        page.wait_for_timeout(120)
    assert seen[0] == "welcome" and "acknowledgements" in seen
    page.click("#next")                                            # Build my Passport
    page.wait_for_selector(".pp-hero")
    assert "Recommended mode" in page.inner_text(".pp-hero")
    assert "grants no execution authority" in page.inner_text("main")
    _layout_checks(page)
    _shot(page, "s24_passport")
    v = _axe(page)
    if v:
        violations["passport"] = v
    page.goto(server + "/passport/app/index.html#performance")
    page.wait_for_selector(".kpis")
    assert "not real trades" in page.inner_text(".sample")
    assert page.locator(".kpi").count() == 4
    _layout_checks(page)
    _shot(page, "s24_performance")
    v = _axe(page)
    if v:
        violations["performance"] = v
    if AXE is None:
        pytest.skip("flow and layout checked; axe-core not configured (CSS_AXE_PATH), accessibility scan skipped")
    assert violations == {}, violations


def test_errors_are_announced_and_focused(browser, server):
    page, _ = _page(browser, server, "ui-errors")
    page.click("#next")                                            # welcome without the acknowledgement
    page.wait_for_selector("#err-ack_risk_intro:not([hidden])")
    assert page.get_attribute("#ack_risk_intro", "aria-invalid") == "true"
    assert page.evaluate("document.activeElement.id") == "ack_risk_intro"
    page.wait_for_timeout(100)
    assert "fix" in page.inner_text("#live")
    _shot(page, "s24_error_state")


def test_back_and_resume_in_browser(browser, server):
    page, token = _page(browser, server, "ui-resume")
    page.check("#ack_risk_intro"); page.click("#next")
    page.wait_for_selector("#display_name")
    page.fill("#display_name", "Kofi"); page.fill("#email", "kofi@example.com"); page.select_option("#country", "GH")
    page.click("label[for='preferred_channel-email']"); page.click("#next")
    page.wait_for_selector("text=Your goals and priorities")
    page.click("#back"); page.wait_for_selector("#display_name")
    assert page.input_value("#display_name") == "Kofi"
    page.reload(); page.wait_for_selector("#display_name")          # resume after reload
    assert page.input_value("#email") == "kofi@example.com"


def test_reduced_motion(browser, server):
    page, _ = _page(browser, server, "ui-motion", reduced_motion="reduce")
    dur = page.evaluate("getComputedStyle(document.querySelector('.progress-fill')).transitionDuration")
    anim = page.evaluate("getComputedStyle(document.querySelector('.stage')).animationName")
    assert dur in ("0s", "0s, 0s") and anim == "none"


def test_text_scaling_200_percent(browser, server):
    page, _ = _page(browser, server, "ui-zoom")
    page.add_style_tag(content="html{font-size:200%}")
    page.wait_for_timeout(100)
    assert page.evaluate("document.scrollingElement.scrollWidth - window.innerWidth") <= 1
    _shot(page, "s24_text_200pct")


@pytest.mark.parametrize("name,vp", [("landscape", {"width": 780, "height": 360}), ("tablet", {"width": 800, "height": 1280}),
                                     ("desktop", {"width": 1440, "height": 900})])
def test_responsive_layouts(browser, server, name, vp):
    page, _ = _page(browser, server, f"ui-{name}", viewport=vp, is_mobile=name != "desktop")
    _layout_checks(page)
    _shot(page, f"{name}_welcome")
    page.goto(server + "/passport/app/index.html#performance")
    page.wait_for_selector(".kpis")
    assert page.evaluate("document.scrollingElement.scrollWidth - window.innerWidth") <= 1
    _shot(page, f"{name}_performance")


def test_conditional_steps_accessibility(browser, server):
    """The Leverage and Auto-check steps only appear on some paths; walk one that shows both and scan them."""
    persona = dict(BASE, experience_by_class=dict(BASE["experience_by_class"], fx="beginner"),
                   preferred_markets=["equities", "fx"], uses_leverage="small", assistance_preference="auto_interest")
    page, token = _page(browser, server, "ui-conditional")
    scanned, violations = [], {}
    for _ in range(40):
        stage = _current(page, server, token)["stage"]
        if stage["kind"] == "result":
            break
        if stage["id"] in ("knowledge_leverage", "auto_check"):
            _layout_checks(page)
            v = _axe(page)
            if v:
                violations[stage["id"]] = v
            scanned.append(stage["id"])
            _shot(page, f"s24_conditional_{stage['id']}")
        _answer_stage(page, stage, persona)
        page.click("#next")
        page.wait_for_timeout(150)
    assert scanned == ["knowledge_leverage", "auto_check"]
    if AXE is None:
        pytest.skip("conditional steps reached and layout-checked; axe-core not configured, scan skipped")
    assert violations == {}, violations
