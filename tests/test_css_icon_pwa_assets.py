from __future__ import annotations

from fastapi.testclient import TestClient

from dashboard.mobile.mobile_app import app as mobile_app
from dashboard.web.web_app import create_app


def test_mobile_app_pwa_icons_and_saved_link_metadata() -> None:
    client = TestClient(mobile_app)

    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    icons = {item["src"] for item in manifest.json()["icons"]}
    assert "/static/css_pwa_icon_192.png" in icons
    assert "/static/css_pwa_icon_512.png" in icons

    for path, content_type in {
        "/favicon.ico": "image/x-icon",
        "/apple-touch-icon.png": "image/png",
        "/static/css_pwa_icon_192.png": "image/png",
        "/static/css_pwa_icon_512.png": "image/png",
    }.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == content_type
        assert response.content

    page = client.get("/login")
    assert page.status_code == 200
    assert '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">' in page.text
    assert '<link rel="icon" type="image/png" sizes="192x192" href="/static/css_pwa_icon_192.png">' in page.text


def test_web_app_css_icon_routes_and_dashboard_metadata() -> None:
    client = TestClient(create_app())

    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    assert manifest.json()["short_name"] == "CSS"

    for path, content_type in {
        "/favicon.ico": "image/x-icon",
        "/apple-touch-icon.png": "image/png",
        "/static/css_pwa_icon_192.png": "image/png",
        "/static/css_pwa_icon_512.png": "image/png",
    }.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == content_type
        assert response.content

    page = client.get("/dashboard")
    assert page.status_code == 200
    assert '<link rel="manifest" href="/manifest.webmanifest">' in page.text
    assert '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">' in page.text
