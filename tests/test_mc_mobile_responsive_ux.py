"""Mission Control mobile responsive presentation — no semantic/data changes."""

from __future__ import annotations

import re

from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.mission_control.pages.executive_overview import render as render_executive_overview
from dashboard.mission_control.theme import MISSION_CONTROL_CSS


STATUS_KEYS = (
    "runtime",
    "execution",
    "broker",
    "broker-health",
    "platform",
    "safety",
    "posture",
)

PRIORITY_LABELS = (
    "Execution Status",
    "Cash",
    "Portfolio Value",
    "Session P&L",
    "Open Positions",
    "Next Maturity",
)


def _shell(**kwargs) -> str:
    return render_mission_control_shell(
        {
            "schema_version": "test",
            "generated_at": "2026-09-05T00:00:00Z",
            "platform": {
                "product": "CSS Mission Control",
                "runtime_mode": "DISABLED",
                "broker_health": "DISABLED",
                "platform_status": "RED",
                "selected_broker": "UNAVAILABLE",
                "broker_mode": "UNAVAILABLE",
            },
            "platform_status": {
                "runtime_mode": "DISABLED",
                "execution_state": "BLOCKED",
                "broker_mode": "UNAVAILABLE",
            },
            "safety": {
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "safety_status": "PASS",
            },
            "runtime": {"heartbeat_status": "UNAVAILABLE"},
            "portfolio": {
                "cash": "UNAVAILABLE",
                "portfolio_value": "UNAVAILABLE",
                "session_pnl": "UNAVAILABLE",
                "open_positions": "UNAVAILABLE",
                "next_maturity": "UNAVAILABLE",
                "execution_status": "BLOCKED",
                "operating_context": {
                    "advisory_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                },
            },
        },
        active_section="executive_overview",
        **kwargs,
    )


def test_single_native_nav_and_mobile_toggle() -> None:
    html = _shell()
    assert html.count('class="mc-nav"') == 1
    assert html.count('id="mc-nav-toggle"') == 1
    assert 'class="mc-mobile-chrome"' in html
    assert 'class="mc-nav-toggle-btn"' in html
    assert 'class="mc-nav-close"' in html
    assert 'for="mc-nav-toggle"' in html
    assert "CSS Mission Control" in html
    assert "Executive Overview" in html
    nav_block = re.search(r'<nav class="mc-nav"[^>]*>(.*?)</nav>', html, re.S)
    assert nav_block is not None
    hrefs = re.findall(r'href="(/mission-control/[^"]+)"', nav_block.group(1))
    assert len(hrefs) == len(MISSION_CONTROL_SECTIONS)
    assert "location.assign" not in html


def test_status_items_are_individually_rendered() -> None:
    html = _shell()
    strip = re.search(
        r'<div class="mc-status-strip"[^>]*>(.*?)</div>',
        html,
        re.S,
    )
    assert strip is not None
    for key in STATUS_KEYS:
        assert f'data-mc-status="{key}"' in strip.group(1)
    assert "Runtime" in strip.group(1)
    assert "DISABLED" in strip.group(1)
    assert "Execution" in strip.group(1)
    assert "BLOCKED" in strip.group(1)
    assert "Broker" in strip.group(1)
    assert "UNAVAILABLE" in strip.group(1)
    assert "Broker Health" in strip.group(1)
    assert "Platform" in strip.group(1)
    assert "RED" in strip.group(1)
    assert "Safety" in strip.group(1)
    assert "PASS" in strip.group(1)
    assert "Posture" in strip.group(1)
    assert "ADVISORY / READ-ONLY" in strip.group(1)
    # Concatenation defect: values must not immediately adjoin the next label.
    assert "DISABLEDExecution" not in html
    assert "BLOCKEDBroker" not in html


def test_css_collapses_nav_and_wraps_status_on_phone() -> None:
    assert ".mc-nav-toggle:checked ~ .mc-sidebar" in MISSION_CONTROL_CSS
    assert ".mc-mobile-chrome" in MISSION_CONTROL_CSS
    assert "min-width: 44px" in MISSION_CONTROL_CSS
    assert "min-height: 44px" in MISSION_CONTROL_CSS
    assert "grid-template-columns: repeat(auto-fit, minmax(148px, 1fr))" in MISSION_CONTROL_CSS
    assert ".mc-table-wrap" in MISSION_CONTROL_CSS
    assert "@media (max-width: 430px)" in MISSION_CONTROL_CSS
    assert "@media (max-width: 768px)" in MISSION_CONTROL_CSS
    assert "max-height: min(46vh, 420px)" not in MISSION_CONTROL_CSS
    desktop = MISSION_CONTROL_CSS[: MISSION_CONTROL_CSS.index("@media (max-width: 1100px)")]
    assert "grid-template-columns: 288px 1fr" in desktop
    assert ".mc-shell {\n  min-height: 100vh;\n  display: grid;" in desktop


def test_executive_overview_priority_and_sections() -> None:
    body = render_executive_overview(
        {
            "platform": {"runtime_mode": "DISABLED", "platform_status": "RED"},
            "safety": {
                "advisory_only": True,
                "execution_allowed": False,
                "live_trading_blocked": True,
                "broker_execution_armed": False,
                "safety_status": "PASS",
            },
            "portfolio": {
                "cash": "UNAVAILABLE",
                "portfolio_value": "UNAVAILABLE",
                "session_pnl": "UNAVAILABLE",
                "open_positions": "UNAVAILABLE",
                "next_maturity": "UNAVAILABLE",
                "execution_status": "BLOCKED",
                "operating_context": {
                    "advisory_only": True,
                    "read_only": True,
                    "execution_allowed": False,
                    "live_trading_blocked": True,
                    "broker_execution_armed": False,
                },
            },
            "mock_data_label": "RUNTIME DATA",
        }
    )
    assert 'aria-label="Executive cockpit priority"' in body
    assert "Session P&amp;L by Instrument" in body or "Session P&L by Instrument" in body
    assert "Current Holdings / Exposure" in body
    assert "Operating Context" in body
    first = body.find('aria-label="Executive cockpit priority"')
    second = body.find("Session P&amp;L by Instrument")
    if second < 0:
        second = body.find("Session P&L by Instrument")
    assert 0 <= first < second
    positions = []
    for label in PRIORITY_LABELS:
        token = f"<span>{label}</span>"
        pos = body.find(token)
        if pos < 0:
            pos = body.find(f"<span>{label.replace('&', '&amp;')}</span>")
        positions.append(pos)
    assert all(pos >= 0 for pos in positions)
    assert positions == sorted(positions)
    assert "execution_allowed" in body
    assert "False" in body
    assert "live_trading_blocked" in body
    assert "True" in body
    assert "broker_execution_armed" in body
    assert "advisory_only" in body


def test_safety_semantics_unchanged_in_shell() -> None:
    html = _shell()
    assert "ADVISORY / READ-ONLY" in html
    assert "BLOCKED" in html
    assert "DISABLED" in html
    assert "execution_allowed" in html or "Execution" in html
    assert "No execution authority is granted from Mission Control." in html


def test_status_class_does_not_treat_unavailable_as_available() -> None:
    from dashboard.mission_control.pages._components import status_class

    assert status_class("UNAVAILABLE") == "bad"
    assert status_class("unavailable") == "bad"
    assert status_class("Unavailable") == "bad"
    assert status_class("AVAILABLE") == "good"
    assert status_class("available") == "good"
    assert status_class("Available") == "good"
    assert status_class("UNAVAILABLE") != status_class("AVAILABLE")
    assert status_class("UNAVAILABLE") != "good"
    assert status_class("AVAILABLE") != "bad"


def test_status_class_keeps_blocked_disabled_pass_and_advisory_neutral() -> None:
    from dashboard.mission_control.pages._components import status_class

    assert status_class("DISABLED") == "bad"
    assert status_class("disabled") == "bad"
    assert status_class("BLOCKED") == "bad"
    assert status_class("blocked") == "bad"
    assert status_class("PASS") == "good"
    assert status_class("pass") == "good"
    assert status_class("RED") == "bad"
    assert status_class("ADVISORY / READ-ONLY") == "neutral"
    assert status_class("advisory / read-only") == "neutral"
    assert status_class("READ-ONLY") == "neutral"
    assert status_class("NOT_READY") == "bad"


def test_metric_grid_unavailable_tag_is_not_green() -> None:
    from dashboard.mission_control.pages._components import metric_grid

    html = metric_grid((("Cash", "UNAVAILABLE", "UNAVAILABLE"), ("Cash Available", "12", "AVAILABLE")))
    assert "UNAVAILABLE" in html
    assert 'mc-status bad">UNAVAILABLE' in html
    assert 'mc-status good">UNAVAILABLE' not in html
    assert 'mc-status good">AVAILABLE' in html
