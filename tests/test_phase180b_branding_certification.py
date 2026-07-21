from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.broker_reporting.page_layout import build_paginated_document
from backend.common.branding import get_brand_service
from backend.executive_intelligence.print_report import build_text_pdf
from backend.reports_center.registry import all_definitions
from dashboard.mobile.mobile_app import app as mobile_app
from dashboard.enterprise_shell.nav_contract import SPA_SHELL_CACHE
from dashboard.reports_viewer.paginated_viewer import render_paginated_viewer
from dashboard.reports_viewer.report_adapter import registered_report_document
from dashboard.web.web_app import create_app
from launcher.css_mobile_launcher import app as launcher_app


def test_brand_service_is_complete_and_assets_are_versioned() -> None:
    brand = get_brand_service()
    snapshot = brand.snapshot()
    assert snapshot["schema_version"] == "css.branding.v1"
    assert snapshot["asset_version"] == "180a1"
    assert snapshot["palette"]["theme"] == "#101820"
    assert snapshot["application_name"] == "Capital Strata Systems Mission Control"
    required = {
        "logo",
        "monochrome_logo",
        "watermark_logo",
        "favicon",
        "favicon_16",
        "favicon_32",
        "apple_touch",
        "icon_192",
        "icon_512",
        "maskable_192",
        "maskable_512",
    }
    assert required <= set(snapshot["assets"])
    for key in required:
        assert brand.asset_path(key).is_file()
    for key in required - {"favicon"}:
        assert f"v={brand.asset_version}" in brand.asset_url(key)


def test_all_application_manifests_and_heads_use_brand_service() -> None:
    brand = get_brand_service()
    mobile = TestClient(mobile_app)
    web = TestClient(create_app())
    launcher = TestClient(launcher_app)

    assert mobile.get("/manifest.webmanifest").json() == brand.manifest()
    assert web.get("/manifest.webmanifest").json() == brand.manifest()
    assert launcher.get("/manifest.json").json() == brand.manifest(
        start_url="/mobile-launcher",
        app_id="/css-mobile-launcher",
        name="CSS Mobile Launcher",
        short_name="CSS",
        shell_cache=SPA_SHELL_CACHE,
    )
    for response in (
        mobile.get("/login"),
        web.get("/dashboard"),
        launcher.get("/mobile-dashboard"),
        launcher.get("/mobile-launcher"),
    ):
        assert response.status_code == 200
        assert brand.asset_url("favicon_32") in response.text
        assert brand.asset_url("apple_touch") in response.text
        assert brand.palette.theme in response.text


def test_document_standard_applies_header_footer_and_watermark() -> None:
    brand = get_brand_service()
    document = build_paginated_document(
        title="Brand Certification",
        report_id="BRAND-180B",
        css_version="RC1.1",
        commit_reference=None,
        generated_at="2026-07-21T10:00:00Z",
        executive_summary=["Branding certification evidence."],
        sections=[("Evidence", {"status": "PASS"})],
    )
    payload = document.as_dict()
    assert payload["branding"]["organization"] == brand.organization_name
    assert payload["branding"]["document_id"] == "BRAND-180B"
    assert payload["branding"]["classification"] == (
        brand.document_standard.classification
    )
    assert payload["branding"]["watermark"]["opacity"] < 0.1
    assert "watermark" in payload["presentation"]["required_elements"]

    continuous_html = document.to_html()
    paginated_html = render_paginated_viewer(payload)
    for rendered in (continuous_html, paginated_html):
        assert 'class="css-brand-watermark"' in rendered
        assert brand.asset_url("watermark_logo") in rendered
        assert brand.organization_name in rendered
        assert brand.document_standard.confidentiality_banner in rendered
        assert "Page 1 of" in rendered
        assert "BRAND-180B" in rendered
        assert "RC1.1" in rendered


def test_pdf_writer_contains_printable_low_contrast_watermark() -> None:
    brand = get_brand_service()
    pdf = build_text_pdf(
        ["Brand certification", "Execution blocked"],
        watermark_text=brand.organization_name,
    )
    assert pdf.startswith(b"%PDF-1.4")
    assert b"0.92 g" in pdf
    assert brand.organization_name.encode("ascii") in pdf
    assert brand.document_standard.confidentiality_banner.encode(
        "latin-1", errors="replace"
    ) in pdf


def test_every_registered_report_renders_with_canonical_watermark(tmp_path: Path) -> None:
    brand = get_brand_service()
    for definition in all_definitions():
        document, _ = registered_report_document(
            definition.report_code,
            repo_root=tmp_path,
            role="SUPER_USER",
        )
        rendered = render_paginated_viewer(document)
        assert brand.asset_url("watermark_logo") in rendered, definition.report_code
        assert brand.document_standard.confidentiality_banner in rendered
        assert str(document.get("report_id") or "UNKNOWN") in rendered


def test_active_presentations_do_not_resolve_branding_files_directly() -> None:
    root = Path(__file__).resolve().parents[1]
    active_sources = (
        "dashboard/mobile/mobile_app.py",
        "dashboard/web/web_app.py",
        "dashboard/enterprise_shell/mobile_landing.py",
        "dashboard/enterprise_shell/shell.py",
        "dashboard/reports_viewer/paginated_viewer.py",
        "launcher/css_mobile_launcher.py",
        "launcher/templates/mobile_dashboard.html",
        "launcher/templates/mobile_launcher.html",
        "backend/broker_reporting/page_layout.py",
        "backend/reports_center/pdf_renderer.py",
        "backend/executive_intelligence/print_report.py",
    )
    for relative in active_sources:
        source = (root / relative).read_text(encoding="utf-8")
        assert "assets/branding" not in source
        assert "assets\\branding" not in source
        assert "css_icon_1024x1024.png" not in source
        assert "css-icon-maskable-512.png" not in source
