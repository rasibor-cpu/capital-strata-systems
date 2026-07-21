from __future__ import annotations

from pathlib import Path
import struct

from fastapi.testclient import TestClient

from backend.common.branding import get_brand_service
from dashboard.mobile import mobile_app

ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "assets" / "branding"


def _png_dimensions(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", data[16:24])


def test_manifest_is_installable_and_uses_separate_regular_and_maskable_icons() -> None:
    client = TestClient(mobile_app.app)
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    assert response.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
    manifest = response.json()
    assert manifest == get_brand_service().manifest()
    assert manifest["name"] == "Capital Strata Systems Mission Control"
    assert manifest["short_name"] == "CSS Mission Control"
    assert manifest["id"] == "/css-mission-control"
    assert manifest["start_url"] == "/dashboard"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["display_override"] == [
        "window-controls-overlay",
        "standalone",
        "minimal-ui",
    ]
    assert manifest["orientation"] == "any"
    icon_contract = {
        (item["sizes"], item["purpose"], item["src"])
        for item in manifest["icons"]
    }
    assert ("192x192", "any", "/pwa/css-icon-192.png?v=180a1") in icon_contract
    assert ("512x512", "any", "/pwa/css-icon-512.png?v=180a1") in icon_contract
    assert (
        "192x192",
        "maskable",
        "/pwa/css-icon-maskable-192.png?v=180a1",
    ) in icon_contract
    assert (
        "512x512",
        "maskable",
        "/pwa/css-icon-maskable-512.png?v=180a1",
    ) in icon_contract
    assert client.get("/dashboard", follow_redirects=False).status_code == 303


def test_complete_icon_family_exists_and_routes_have_expected_dimensions() -> None:
    client = TestClient(mobile_app.app)
    routes = {
        "/favicon-16x16.png?v=180a1": (16, 16),
        "/favicon-32x32.png?v=180a1": (32, 32),
        "/apple-touch-icon.png?v=180a1": (180, 180),
        "/pwa/css-icon-192.png?v=180a1": (192, 192),
        "/pwa/css-icon-512.png?v=180a1": (512, 512),
        "/pwa/css-icon-maskable-192.png?v=180a1": (192, 192),
        "/pwa/css-icon-maskable-512.png?v=180a1": (512, 512),
    }
    for route, expected in routes.items():
        response = client.get(route)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-css-pwa-version"] == "180a1"
        assert _png_dimensions(response.content) == expected
    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"] == "image/x-icon"
    assert favicon.content[:4] == b"\x00\x00\x01\x00"

    expected_files = {
        "favicon.ico",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "apple-touch-icon.png",
        "css-icon-192.png",
        "css-icon-512.png",
        "css-icon-maskable-192.png",
        "css-icon-maskable-512.png",
    }
    assert expected_files <= {path.name for path in BRANDING.iterdir()}


def test_every_mobile_page_uses_the_canonical_pwa_head_and_registration() -> None:
    client = TestClient(mobile_app.app)
    pages = [client.get("/login").text, mobile_app._page("Test", "<main>Test</main>")]
    for page in pages:
        assert '<link rel="manifest" href="/manifest.webmanifest">' in page
        assert '<link rel="icon" href="/favicon.ico" sizes="any">' in page
        assert "/favicon-16x16.png?v=180a1" in page
        assert "/favicon-32x32.png?v=180a1" in page
        assert "/apple-touch-icon.png?v=180a1" in page
        assert '<meta name="mobile-web-app-capable" content="yes">' in page
        assert '<meta name="apple-mobile-web-app-capable" content="yes">' in page
        assert '<meta name="apple-mobile-web-app-title" content="CSS Mission Control">' in page
        assert '<meta name="application-name" content="CSS Mission Control">' in page
        assert '<meta name="theme-color" content="#101820">' in page
        assert "service-worker.js?v=180a1" in page
        assert 'updateViaCache: "none"' in page


def test_service_worker_caches_only_public_branding_and_offline_shell() -> None:
    client = TestClient(mobile_app.app)
    response = client.get("/service-worker.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"
    script = response.text
    safe_assets = script.split("const PROTECTED_PREFIXES", 1)[0]
    for protected in (
        "/api",
        "/login",
        "/dashboard",
        "/reports",
        "/mission-control",
        "/broker",
        "/runtime",
    ):
        assert protected not in safe_assets
        assert f'"{protected}"' in script
    assert "cache.put" not in script
    assert "caches.match(event.request" in script
    assert 'caches.match("/pwa-offline")' in script
    assert "key.startsWith(CACHE_PREFIX)" in script
    assert "self.clients.claim()" in script


def test_brand_assets_and_markup_contain_no_browser_branding() -> None:
    source = (BRANDING / "css_icon_1024x1024.png").read_bytes().lower()
    manifest = str(get_brand_service().manifest()).lower()
    page = mobile_app._page("Brand Audit", "<main>CSS</main>").lower()
    for forbidden in ("chrome", "google", "chromium"):
        assert forbidden.encode("ascii") not in source
        assert forbidden not in manifest
        assert forbidden not in page
    assert _png_dimensions((BRANDING / "css_icon_1024x1024.png").read_bytes()) == (
        1024,
        1024,
    )
    assert get_brand_service().asset_path("logo").exists()
