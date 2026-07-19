"""Phase 176H — Mission Control mobile/touch navigation reconciliation."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.layout import MC_NAV_TOUCH_JS, render_mission_control_shell
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


def _shell_html() -> str:
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
    )


def test_all_mc_nav_items_are_real_anchors() -> None:
    html = _shell_html()
    assert 'class="mc-nav"' in html
    for section in MISSION_CONTROL_SECTIONS:
        assert f'href="{section.route}"' in html
        assert f'data-section="{section.key}"' in html
        assert section.label in html
    # No inert role=button nav without href
    assert 'class="mc-nav"' in html
    assert html.count('href="/mission-control/') == len(MISSION_CONTROL_SECTIONS)


def test_mobile_css_clears_sidebar_overflow_scrollport() -> None:
    assert "overflow-y: auto" in MISSION_CONTROL_CSS  # desktop sidebar may scroll
    assert "@media (max-width: 1100px)" in MISSION_CONTROL_CSS
    # Critical Phase 176H rule
    assert "overflow: visible" in MISSION_CONTROL_CSS
    assert "touch-action: manipulation" in MISSION_CONTROL_CSS
    assert "z-index: 6" in MISSION_CONTROL_CSS
    assert "min-height: 44px" in MISSION_CONTROL_CSS


def test_touch_nav_script_present_and_assigns_location() -> None:
    assert "touchend" in MC_NAV_TOUCH_JS
    assert "location.assign" in MC_NAV_TOUCH_JS
    assert "preventDefault" in MC_NAV_TOUCH_JS
    html = _shell_html()
    assert "location.assign" in html
    assert "touchend" in html


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
        assert "overflow: visible" in res.text
        assert "location.assign" in res.text
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
