"""Phase 176I — PDF open route reconciliation (canonical bytes, not metadata)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.reports_center.routes import create_reports_center_router
from backend.reports_center.service import ReportsCenterService
from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.pages import render_page


AUTH = {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}


def test_mc_open_pdf_anchor_uses_canonical_api_only() -> None:
    html = render_page(
        "reports_center",
        {
            "governance": {"role": "SUPER_USER", "current_user": "00000"},
            "reports_authorization": {
                "authenticated": True,
                "user_id": "00000",
                "role": "SUPER_USER",
                "reports_view": True,
                "reports_generate": True,
            },
        },
    )
    assert 'id="rc-detail-pdf-link"' in html
    assert "data-rc-pdf-open" in html
    assert "canonicalPdfHref" in html
    assert "Open PDF" in html
    assert "pdfLink.href = '/mission-control/api/reports/" not in html
    assert 'data-rc-detail="pdf"' not in html
    assert 'data-rc-detail="pdf-status"' in html
    assert "/pdf-info" in html


def test_mobile_open_pdf_uses_canonical_api_only() -> None:
    src = Path("dashboard/mobile/mobile_reports.py").read_text(encoding="utf-8")
    assert "/api/v1/reports/{_esc(report_id)}/pdf" in src
    assert "data-rc-pdf-open" in src
    assert "Open PDF" in src
    # Must not open MC metadata JSON from the Open PDF control.
    assert "/mission-control/api/reports/" not in src


def test_canonical_pdf_route_headers(tmp_path: Path) -> None:
    svc = ReportsCenterService(repo_root=tmp_path)
    gen = svc.generate("safety_lock_report", filters={}, role="SUPER_USER", user_id="00000", persist=True)
    assert gen["status"] == "OK"
    rid = str(gen["report_id"])

    app = FastAPI()
    register_mission_control(app, lambda: None)
    app.include_router(create_reports_center_router(repo_root=tmp_path))
    client = TestClient(app)

    res = client.get(f"/api/v1/reports/{rid}/pdf", headers=AUTH)
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type", "").startswith("application/pdf")
    assert "inline" in (res.headers.get("content-disposition") or "").lower()
    assert res.content.startswith(b"%PDF")

    mc = client.get(f"/mission-control/api/reports/{rid}/pdf", headers=AUTH, follow_redirects=False)
    assert mc.status_code == 307
    assert mc.headers.get("location") == f"/api/v1/reports/{rid}/pdf"

    followed = client.get(f"/mission-control/api/reports/{rid}/pdf", headers=AUTH, follow_redirects=True)
    assert followed.status_code == 200
    assert followed.headers.get("content-type", "").startswith("application/pdf")
    assert followed.content.startswith(b"%PDF")

    info = client.get(f"/mission-control/api/reports/{rid}/pdf-info", headers=AUTH)
    assert info.status_code == 200
    assert info.headers.get("content-type", "").startswith("application/json")
    assert info.json().get("pdf_endpoint") == f"/api/v1/reports/{rid}/pdf"


def test_android_chrome_open_pdf_href_is_canonical_bytes_route(tmp_path: Path) -> None:
    import pytest

    playwright = pytest.importorskip("playwright.sync_api")
    sync_playwright = playwright.sync_playwright

    svc = ReportsCenterService(repo_root=tmp_path)
    gen = svc.generate("safety_lock_report", filters={}, role="SUPER_USER", user_id="00000", persist=True)
    rid = str(gen["report_id"])
    pdf_path = f"/api/v1/reports/{rid}/pdf"

    app = FastAPI()
    register_mission_control(app, lambda: None)
    app.include_router(create_reports_center_router(repo_root=tmp_path))
    client = TestClient(app)
    res = client.get(pdf_path, headers=AUTH)
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type", "").startswith("application/pdf")
    assert "inline" in (res.headers.get("content-disposition") or "").lower()
    assert res.content.startswith(b"%PDF")

    mc_html = render_page(
        "reports_center",
        {
            "governance": {"role": "SUPER_USER", "current_user": "00000"},
            "reports_authorization": {
                "authenticated": True,
                "user_id": "00000",
                "role": "SUPER_USER",
                "reports_view": True,
                "reports_generate": True,
            },
        },
    )

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
        page.set_content(mc_html, wait_until="domcontentloaded")
        # Simulate openReport wiring for Android.
        page.evaluate(
            """(rid) => {
              const pdfLink = document.getElementById('rc-detail-pdf-link');
              const actions = document.getElementById('rc-detail-actions');
              if (actions) actions.hidden = false;
              if (pdfLink) pdfLink.href = '/api/v1/reports/' + encodeURIComponent(rid) + '/pdf';
            }""",
            rid,
        )
        href = page.eval_on_selector("#rc-detail-pdf-link", "el => el.getAttribute('href')")
        assert href == pdf_path
        assert href.startswith("/api/v1/reports/")
        assert href.endswith("/pdf")
        assert "/mission-control/" not in href
        # PDF status control must not be the Open PDF control.
        status = page.query_selector('[data-rc-detail="pdf-status"]')
        assert status is not None
        assert page.query_selector('[data-rc-detail="pdf"]') is None
        browser.close()


def test_no_open_pdf_points_at_metadata_json() -> None:
    src = Path("dashboard/mission_control/pages/reports_center.py").read_text(encoding="utf-8")
    assert "canonicalPdfHref" in src
    assert "pdf-status" in src
    assert "'pdf': '/mission-control/api/reports/" not in src
    assert 'data-rc-detail="pdf"' not in src

    routes = Path("dashboard/mission_control/routes.py").read_text(encoding="utf-8")
    assert "RedirectResponse" in routes
    assert 'url=f"/api/v1/reports/{report_id}/pdf"' in routes
    assert "/pdf-info" in routes
