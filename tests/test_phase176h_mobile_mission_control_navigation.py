"""Phase 176H — Mission Control mobile/touch navigation reconciliation.

Phase 176H.1: navigation is native-anchor only (no touchend preventDefault).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.layout import MC_NAV_TOUCH_DEBUG_JS, render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.mission_control.theme import MISSION_CONTROL_CSS


REQUIRED_LABELS = [
    "Executive Overview",
    "Reports",
    "Runtime Operations",
    "Trade Operations",
    "Portfolio",
    "Market Intelligence",
    "Risk Command",
    "Options Income",
    "Broker Management",
    "Alerts and Incidents",
    "Certification and Readiness",
    "Audit and Explainability",
    "Learning and Performance",
    "Users and Governance",
    "System Configuration",
    "Documentation / Runbooks",
]


def _shell_html(**kwargs) -> str:
    return render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-07-18T00:00:00Z",
            "platform": {"product": "CSS", "runtime_mode": "PAPER"},
            "safety": {
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "safety_status": "LOCKED",
            },
            "runtime": {"heartbeat_status": "OK"},
            "governance": {"role": "SUPER_USER", "current_user": "00000"},
            "reports_authorization": {
                "authenticated": True,
                "user_id": "00000",
                "role": "SUPER_USER",
                "reports_view": True,
                "reports_generate": True,
            },
        },
        active_section="reports_center",
        **kwargs,
    )


def test_all_mc_nav_items_are_real_anchors() -> None:
    html = _shell_html()
    assert 'class="mc-nav"' in html
    for section in MISSION_CONTROL_SECTIONS:
        assert f'href="{section.route}"' in html
        assert f'data-section="{section.key}"' in html
        assert section.label in html
    assert html.count('href="/mission-control/') == len(MISSION_CONTROL_SECTIONS)
    assert 'data-mc-nav="native-anchor-176h1"' in html
    assert 'name="css-mc-nav" content="native-anchor-176h1"' in html


def test_mobile_css_static_sidebar_no_scrollport() -> None:
    assert "overflow-y: auto" in MISSION_CONTROL_CSS  # desktop sidebar may scroll
    assert "@media (max-width: 1100px)" in MISSION_CONTROL_CSS
    assert "position: static" in MISSION_CONTROL_CSS
    assert "overflow: visible" in MISSION_CONTROL_CSS
    assert "touch-action: manipulation" in MISSION_CONTROL_CSS
    assert "pointer-events: none" in MISSION_CONTROL_CSS
    assert "min-height: 44px" in MISSION_CONTROL_CSS


def test_no_nav_preventdefault_in_default_shell() -> None:
    html = _shell_html(touch_debug=False)
    assert "location.assign" not in html
    # Production shell must not ship the 176H touchend interceptor.
    assert "Force navigation when the browser suppresses" not in html
    assert "mc-touch-debug" not in html


def test_touch_debug_overlay_only_when_enabled() -> None:
    assert "touch_debug=1" in MC_NAV_TOUCH_DEBUG_JS
    assert "elementFromPoint" in MC_NAV_TOUCH_DEBUG_JS
    enabled = _shell_html(touch_debug=True)
    assert "mc-touch-debug" in enabled or "touch_debug=1" in enabled
    assert "elementFromPoint" in enabled


def test_http_routes_resolve_for_every_section() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    matrix = []
    for section in MISSION_CONTROL_SECTIONS:
        res = client.get(
            section.route,
            headers={"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"},
        )
        assert res.status_code == 200, section.route
        assert f'href="{section.route}"' in res.text
        assert 'aria-label="Mission Control navigation"' in res.text
        assert "native-anchor-176h1" in res.text
        assert res.headers.get("cache-control", "").lower() == "no-store"
        matrix.append((section.label, "PASS"))
    assert [label for label, _ in matrix] == [s.label for s in MISSION_CONTROL_SECTIONS]
    assert all(status == "PASS" for _, status in matrix)
    for label in REQUIRED_LABELS:
        assert any(label == s.label for s in MISSION_CONTROL_SECTIONS)


def test_safety_locks_unchanged_in_shell() -> None:
    from backend.reports_center.constants import SAFETY_LOCKS

    assert SAFETY_LOCKS == {
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }
