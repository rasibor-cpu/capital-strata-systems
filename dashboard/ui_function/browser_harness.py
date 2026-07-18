"""Optional Playwright live-browser harness for Phase 176C.

Install (documented, optional):

    pip install -r requirements-browser.txt
    playwright install chromium

If Playwright is not installed, callers should skip live browser suites.
ASGI TestClient workflow certification remains mandatory.
"""

from __future__ import annotations

from typing import Any


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


def run_live_browser_smoke(base_url: str) -> dict[str, Any]:
    """Hit top-level web routes in a real Chromium session and assert no page errors."""
    if not playwright_available():
        return {"ok": False, "skipped": True, "reason": "playwright_not_installed"}

    from playwright.sync_api import sync_playwright

    failures: list[str] = []
    console_errors: list[str] = []
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
        "/mission-control/executive-overview",
        "/mission-control/reports",
        "/mission-control/runtime-operations",
        "/mission-control/portfolio",
        "/mission-control/risk-command",
        "/mission-control/broker-management",
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda err: console_errors.append(f"pageerror:{err}"))
        page.on("console", lambda msg: console_errors.append(f"console:{msg.type}:{msg.text}") if msg.type == "error" else None)
        for route in routes:
            url = base_url.rstrip("/") + route
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if response is None or response.status >= 500:
                    failures.append(f"{route}: bad_status={getattr(response, 'status', None)}")
                    continue
                # Reports subtabs must be present and clickable
                if route.endswith("/reports"):
                    for target in ("rc-categories", "rc-create", "rc-library"):
                        loc = page.locator(f'[data-css-subtab="{target}"]')
                        if loc.count() == 0:
                            failures.append(f"reports_missing_subtab:{target}")
                        else:
                            loc.first.click(timeout=5000)
                    expand = page.locator('[data-css-disclosure-expand-all="true"]')
                    if expand.count():
                        expand.first.click(timeout=5000)
                    # Ensure catalog JSON parsed (selector populated)
                    options = page.locator("#rc-report-code option")
                    if options.count() < 2:
                        failures.append("reports_selector_not_populated")

                # Mobile viewport pass for reports
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{route}: {type(exc).__name__}:{exc}")
        # Mobile viewport smoke on reports
        page.set_viewport_size({"width": 390, "height": 844})
        try:
            page.goto(base_url.rstrip("/") + "/mission-control/reports", wait_until="domcontentloaded", timeout=30000)
            if page.locator('[data-css-subtab="rc-categories"]').count() == 0:
                failures.append("mobile_viewport_reports_missing_categories")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"mobile_viewport:{exc}")
        browser.close()
    # Filter noisy third-party console noise if any — keep pageerrors always
    hard = [e for e in console_errors if e.startswith("pageerror:")]
    return {
        "ok": not failures and not hard,
        "skipped": False,
        "failures": failures,
        "console_errors": console_errors[:50],
        "routes_checked": len(routes),
    }
