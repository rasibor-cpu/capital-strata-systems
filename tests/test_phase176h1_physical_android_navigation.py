"""Phase 176H.1 — physical Android Mission Control navigation remediation."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.mission_control.theme import MISSION_CONTROL_CSS


AUTH = {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}


def _client() -> TestClient:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    return TestClient(app)


def test_every_nav_item_has_valid_same_origin_path_href() -> None:
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
    for section in MISSION_CONTROL_SECTIONS:
        assert f'href="{section.route}"' in html
        assert section.route.startswith("/mission-control/")
        assert "javascript:" not in section.route


def test_production_shell_has_no_nav_preventdefault_interceptor() -> None:
    client = _client()
    res = client.get("/mission-control/executive-overview", headers=AUTH)
    assert res.status_code == 200
    assert "location.assign" not in res.text
    assert "Force navigation when the browser suppresses" not in res.text
    assert 'content="native-anchor-176h1"' in res.text


def test_nav_child_spans_use_pointer_events_none() -> None:
    assert ".mc-nav a > *" in MISSION_CONTROL_CSS
    assert "pointer-events: none" in MISSION_CONTROL_CSS


def test_mobile_layout_disables_sticky_overlay_risk() -> None:
    # Under the mobile media query, sidebar and topbar are static.
    idx = MISSION_CONTROL_CSS.index("@media (max-width: 1100px)")
    mobile = MISSION_CONTROL_CSS[idx : idx + 800]
    assert "position: static" in mobile
    assert ".mc-sidebar" in mobile
    assert ".mc-topbar" in mobile


def test_cache_control_no_store_on_mc_html() -> None:
    client = _client()
    res = client.get("/mission-control/reports", headers=AUTH)
    assert res.headers.get("cache-control", "").lower() == "no-store"


def test_touch_debug_query_injects_overlay_script() -> None:
    client = _client()
    off = client.get("/mission-control/reports", headers=AUTH)
    on = client.get("/mission-control/reports?touch_debug=1", headers=AUTH)
    assert "css MC touch_debug=1" not in off.text.lower() and "mc-touch-debug" not in off.text
    assert "touch_debug=1" in on.text
    assert "elementFromPoint" in on.text


def test_service_worker_excludes_mission_control_html() -> None:
    src = Path("dashboard/mobile/mobile_app.py").read_text(encoding="utf-8")
    assert 'pathname.startsWith("/mission-control")' in src
    assert "css-mobile-shell-v176h1" in src


def test_js_disabled_navigation_via_plain_anchors(tmp_path: Path) -> None:
    """Plain anchors remain the sole navigation mechanism (no JS required)."""
    client = _client()
    res = client.get("/mission-control/executive-overview", headers=AUTH)
    assert res.status_code == 200
    # With JS disabled, browsers follow href. Prove each href resolves server-side.
    for section in MISSION_CONTROL_SECTIONS:
        page = client.get(section.route, headers=AUTH)
        assert page.status_code == 200
        assert f"<h1>" in page.text
