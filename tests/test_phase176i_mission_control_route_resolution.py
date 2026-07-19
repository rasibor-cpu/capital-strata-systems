"""Phase 176I — Mission Control route resolution reconciliation."""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.navigation import (
    MISSION_CONTROL_SECTIONS,
    resolve_section_slug,
    section_for_key,
)
from dashboard.mission_control.pages import render_page


# Canonical expectations: route path → visible labels
EXPECTED = {
    "executive-overview": {
        "key": "executive_overview",
        "nav": "Executive Overview",
        "h1": "Executive Overview",
        "title_part": "Executive Overview",
    },
    "reports": {
        "key": "reports_center",
        "nav": "Reports",
        "h1": "Reports",
        "title_part": "Reports",
    },
    "runtime-operations": {
        "key": "runtime_operations",
        "nav": "Runtime Operations",
        "h1": "Runtime Operations",
        "title_part": "Runtime Operations",
    },
    "trade-operations": {
        "key": "trade_operations",
        "nav": "Trade Operations",
        "h1": "Trade Operations",
        "title_part": "Trade Operations",
    },
    "portfolio": {"key": "portfolio", "nav": "Portfolio", "h1": "Portfolio", "title_part": "Portfolio"},
    "market-intelligence": {
        "key": "market_intelligence",
        "nav": "Market Intelligence",
        "h1": "Market Intelligence",
        "title_part": "Market Intelligence",
    },
    "risk-command": {
        "key": "risk_command",
        "nav": "Risk Command",
        "h1": "Risk Command",
        "title_part": "Risk Command",
    },
    "options-income": {
        "key": "options_income",
        "nav": "Options Income",
        "h1": "Options Income",
        "title_part": "Options Income",
    },
    "broker-management": {
        "key": "broker_management",
        "nav": "Broker Management",
        "h1": "Broker Management",
        "title_part": "Broker Management",
    },
    "alerts-incidents": {
        "key": "alerts_incidents",
        "nav": "Alerts and Incidents",
        "h1": "Alerts and Incidents",
        "title_part": "Alerts and Incidents",
    },
    "certification-readiness": {
        "key": "certification_readiness",
        "nav": "Certification and Readiness",
        "h1": "Certification and Readiness",
        "title_part": "Certification and Readiness",
    },
    "audit-explainability": {
        "key": "audit_explainability",
        "nav": "Audit and Explainability",
        "h1": "Audit and Explainability",
        "title_part": "Audit and Explainability",
    },
    "learning-performance": {
        "key": "learning_performance",
        "nav": "Learning and Performance",
        "h1": "Learning and Performance",
        "title_part": "Learning and Performance",
    },
    "users-governance": {
        "key": "users_governance",
        "nav": "Users and Governance",
        "h1": "Users and Governance",
        "title_part": "Users and Governance",
    },
    "system-configuration": {
        "key": "system_configuration",
        "nav": "System Configuration",
        "h1": "System Configuration",
        "title_part": "System Configuration",
    },
    "documentation-runbooks": {
        "key": "documentation_runbooks",
        "nav": "Documentation / Runbooks",
        "h1": "Documentation / Runbooks",
        "title_part": "Documentation / Runbooks",
    },
}

# Trusted-header identity (autouse fixture disables live session restore).
_AUTH_HEADERS = {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}


def _client() -> TestClient:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    return TestClient(app)


def _parse(html: str) -> dict[str, str]:
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    breadcrumb = re.search(r'class="mc-breadcrumb">(.*?)</div>', html, re.S)
    h1 = re.search(r"<h1>(.*?)</h1>", html, re.S)
    # Prefer nav markup only — theme CSS also contains aria-current="page".
    nav = re.search(r'<nav class="mc-nav"[^>]*>(.*?)</nav>', html, re.S)
    nav_html = nav.group(1) if nav else html
    current = re.search(
        r'<a[^>]*aria-current="page"[^>]*>\s*<span[^>]*>[^<]*</span>\s*<span[^>]*>(.*?)</span>\s*</a>',
        nav_html,
        re.S,
    )
    if current is None:
        current = re.search(r'<a[^>]*aria-current="page"[^>]*>(.*?)</a>', nav_html, re.S)
    return {
        "title": (title.group(1).strip() if title else ""),
        "breadcrumb": (breadcrumb.group(1).strip() if breadcrumb else ""),
        "h1": (h1.group(1).strip() if h1 else ""),
        "aria_current": re.sub(r"<[^>]+>", "", current.group(1)).strip() if current else "",
    }


def test_expected_covers_all_published_routes() -> None:
    published = {s.route.rstrip("/").rsplit("/", 1)[-1] for s in MISSION_CONTROL_SECTIONS}
    assert published == set(EXPECTED)


@pytest.mark.parametrize("slug,meta", sorted(EXPECTED.items()))
def test_each_route_renders_unique_page(slug: str, meta: dict[str, str]) -> None:
    client = _client()
    res = client.get(f"/mission-control/{slug}", headers=_AUTH_HEADERS)
    assert res.status_code == 200
    assert res.headers.get("cache-control", "").lower() == "no-store"
    parsed = _parse(res.text)
    assert meta["title_part"] in parsed["title"]
    assert parsed["breadcrumb"] == f"Mission Control / {meta['nav']}"
    assert parsed["h1"] == meta["h1"]
    assert meta["nav"] in parsed["aria_current"]
    assert f'data-section="{meta["key"]}"' in res.text
    assert f'href="/mission-control/{slug}"' in res.text
    # Page heading must not silently be Executive Overview unless that is the route
    if slug != "executive-overview":
        assert parsed["h1"] != "Executive Overview"


def test_reports_route_is_reports_center_not_executive_overview() -> None:
    client = _client()
    res = client.get("/mission-control/reports", headers=_AUTH_HEADERS)
    assert res.status_code == 200
    parsed = _parse(res.text)
    assert parsed["h1"] == "Reports"
    assert "Report Categories" in res.text
    assert "Create Report" in res.text
    assert 'id="rc-categories"' in res.text
    assert 'id="rc-create"' in res.text
    # Must not present Executive Overview as the page heading
    assert "<h1>Executive Overview</h1>" not in res.text
    assert resolve_section_slug("reports") is not None
    assert resolve_section_slug("reports").key == "reports_center"


def test_unknown_mission_control_route_returns_404() -> None:
    client = _client()
    res = client.get("/mission-control/not-a-real-page", headers=_AUTH_HEADERS)
    assert res.status_code == 404
    assert "Unknown Mission Control section" in res.text
    assert "<h1>Executive Overview</h1>" not in res.text
    assert resolve_section_slug("not-a-real-page") is None


def test_desktop_and_mobile_ua_resolve_identically() -> None:
    client = _client()
    desktop = {**_AUTH_HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
    mobile = {
        **_AUTH_HEADERS,
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
    }
    for slug in EXPECTED:
        d = client.get(f"/mission-control/{slug}", headers=desktop)
        m = client.get(f"/mission-control/{slug}", headers=mobile)
        assert d.status_code == m.status_code == 200
        assert _parse(d.text)["h1"] == _parse(m.text)["h1"] == EXPECTED[slug]["h1"]


def test_section_for_key_and_render_page_fail_closed() -> None:
    with pytest.raises(KeyError):
        section_for_key("not_a_section")
    with pytest.raises(KeyError):
        render_page("not_a_section", {})
    # Known keys still resolve
    assert section_for_key("reports").key == "reports_center"
    assert section_for_key("reports_center").key == "reports_center"


def test_resolve_section_slug_matches_all_routes() -> None:
    for section in MISSION_CONTROL_SECTIONS:
        slug = section.route.rstrip("/").rsplit("/", 1)[-1]
        resolved = resolve_section_slug(slug)
        assert resolved is not None
        assert resolved.key == section.key
