"""Phase 176D — canonical authorization context unification + API/HTML parity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from backend.security.authorization_context import (
    CSSAuthorizationContext,
    apply_auth_to_mission_control_state,
    context_from_identity,
    unauthenticated_context,
)
from dashboard.auth.session_bridge import load_bridged_session_context, resolve_authorization_context
from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.layout import render_mission_control_shell
from dashboard.mission_control.pages import render_page
from dashboard.web.web_app import create_app as create_web_app
from fastapi import FastAPI


def _mc_client() -> TestClient:
    app = FastAPI()
    register_mission_control(app, None)
    from backend.reports_center.routes import create_reports_center_router

    app.include_router(create_reports_center_router())
    return TestClient(app)


def _auth_state(*, user_id: str, role: str) -> dict:
    base = {
        "schema_version": "t",
        "generated_at": "t",
        "platform": {},
        "safety": {
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
        },
        "runtime": {},
        "governance": {"role": role, "current_user": user_id},
    }
    auth = context_from_identity(
        user_id=user_id,
        role=role,
        channel="test",
        identity_source="test_fixture",
    )
    return apply_auth_to_mission_control_state(base, auth)


def test_canonical_context_fields_and_safety_locks() -> None:
    auth = context_from_identity(
        user_id="00000",
        role="SUPER_USER",
        channel="test",
        identity_source="test",
    )
    assert isinstance(auth, CSSAuthorizationContext)
    assert auth.authenticated and auth.active
    assert auth.user_id == "00000"
    assert auth.role == "SUPER_USER"
    assert auth.advisory_only is True
    assert auth.execution_allowed is False
    assert auth.live_trading_blocked is True
    assert auth.broker_execution_armed is False
    reports = auth.reports_authorization()
    assert reports["reports_view"] is True
    assert reports["reports_generate"] is True
    assert reports["reports_admin"] is True


def test_empty_user_id_never_equals_00000() -> None:
    auth = context_from_identity(user_id="", role="SUPER_USER", channel="t", identity_source="t")
    assert not auth.authenticated
    assert auth.denial_reason == "empty_user_id"
    assert auth.user_id == ""


def test_no_implicit_admin_fallback_on_shell() -> None:
    html = render_mission_control_shell(
        {
            "schema_version": "t",
            "generated_at": "t",
            "platform": {},
            "safety": {"live_trading_blocked": True},
            "runtime": {},
            "governance": {"role": "DATA UNAVAILABLE", "current_user": "DATA UNAVAILABLE"},
        },
        active_section="reports_center",
    )
    assert "Access denied" in html
    assert 'data-css-subtab="rc-categories"' not in html
    assert 'id="rc-catalog-data"' not in html


def test_super_user_html_reports_grants_view() -> None:
    html = render_page("reports_center", _auth_state(user_id="00000", role="SUPER_USER"))
    assert "Access denied" not in html
    assert "rc-subnav" in html
    assert "00000" in html


def test_admin_html_reports_grants_view() -> None:
    html = render_page("reports_center", _auth_state(user_id="admin1", role="ADMIN"))
    assert "Access denied" not in html
    assert "rc-subnav" in html


def test_staff_without_reports_view_denied() -> None:
    html = render_page("reports_center", _auth_state(user_id="tech1", role="TECH"))
    assert "Access denied" in html


def test_api_html_parity_super_user(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    client = _mc_client()
    headers = {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}
    api = client.get("/mission-control/api/reports/home", headers=headers)
    assert api.status_code == 200
    assert api.json()["authorization"]["reports_view"] is True
    assert api.json()["authorization"]["user_id"] == "00000"
    assert api.json()["authorization"]["role"] == "SUPER_USER"

    page = client.get("/mission-control/reports", headers=headers)
    assert page.status_code == 200
    assert "Access denied" not in page.text
    assert "rc-subnav" in page.text
    assert '"user_id": "00000"' in page.text or "00000" in page.text


def test_api_html_parity_unauthorized(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    client = _mc_client()
    headers = {"X-CSS-Role": "TECH", "X-CSS-User-Id": "tech1"}
    api = client.get("/mission-control/api/reports/home", headers=headers)
    assert api.status_code == 403
    assert api.json()["authorization"]["reports_view"] is False
    page = client.get("/mission-control/reports", headers=headers)
    assert "Access denied" in page.text


def test_api_v1_requires_auth_no_viewer_default(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    client = TestClient(create_web_app())
    denied = client.get("/api/v1/reports/authorization")
    assert denied.status_code == 200  # endpoint returns auth payload
    body = denied.json()
    assert body.get("authenticated") is False
    assert body.get("reports_view") is False

    ok = client.get(
        "/api/v1/reports/authorization",
        headers={"X-CSS-Role": "ADMIN", "X-CSS-User-Id": "a1"},
    )
    assert ok.json()["reports_view"] is True
    assert ok.json()["user_id"] == "a1"


def test_forged_headers_denied_when_trust_disabled(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "0")
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    auth = resolve_authorization_context(
        channel="test",
        request=type("R", (), {"headers": {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}})(),
    )
    assert not auth.authenticated
    assert auth.denial_reason == "untrusted_identity_headers"


def test_inactive_and_expired_session_denied() -> None:
    inactive = context_from_identity(
        user_id="00000", role="SUPER_USER", channel="t", identity_source="t", active=False
    )
    assert not inactive.authenticated
    assert inactive.denial_reason == "inactive_user"

    from dashboard.auth.session_bridge import recovery_context

    expired = recovery_context(
        {
            "user_id": "00000",
            "role": "SUPER_USER",
            "authenticated_at": "2020-01-01T00:00:00+00:00",
        },
        channel="t",
    )
    assert not expired.authenticated
    assert expired.denial_reason == "expired_session"


def test_bridge_off_fail_closed(monkeypatch) -> None:
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    auth = load_bridged_session_context(channel="test")
    assert not auth.authenticated


@pytest.mark.live_session
def test_live_session_bridge_reads_css_auth_when_present() -> None:
    """Uses real artifact when present; skips soft if missing/expired."""
    auth = load_bridged_session_context(channel="live_check")
    path = Path("artifacts/css_auth_session.json")
    if not path.is_file():
        pytest.skip("no live css_auth_session.json")
    if auth.authenticated:
        assert auth.user_id
        assert auth.role in {"SUPER_USER", "ADMIN"} or auth.role


def test_mobile_parity_authorization_flags() -> None:
    from dashboard.mobile import mobile_reports

    assert mobile_reports.can_view_reports({"role": "SUPER_USER", "user_id": "00000"})
    assert mobile_reports.can_view_reports({"role": "ADMIN", "user_id": "a"})
    assert not mobile_reports.can_view_reports({"role": "TECH", "user_id": "t"})


def test_no_hardcoded_admin_in_mc_reports_routes() -> None:
    text = Path("dashboard/mission_control/routes.py").read_text(encoding="utf-8")
    assert 'home(role="ADMIN")' not in text
    assert 'retrieve(report_id, role="ADMIN")' not in text


def test_safety_locks_on_reports_auth(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    client = TestClient(create_web_app())
    body = client.get(
        "/api/v1/reports/authorization",
        headers={"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"},
    ).json()
    assert body["advisory_only"] is True
    assert body["execution_allowed"] is False
    assert body["live_trading_blocked"] is True
    assert body["broker_execution_armed"] is False


def test_parity_matrix_routes(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setenv("CSS_AUTH_BRIDGE_MODE", "off")
    client = _mc_client()
    headers = {"X-CSS-Role": "SUPER_USER", "X-CSS-User-Id": "00000"}
    pairs = [
        ("/mission-control/reports", "/mission-control/api/reports/home"),
    ]
    matrix = []
    for html_path, api_path in pairs:
        page = client.get(html_path, headers=headers)
        api = client.get(api_path, headers=headers)
        page_allow = "Access denied" not in page.text and page.status_code == 200
        api_allow = api.status_code == 200 and bool((api.json().get("authorization") or {}).get("reports_view"))
        matrix.append({"html": html_path, "api": api_path, "page_allow": page_allow, "api_allow": api_allow})
        assert page_allow == api_allow
    assert matrix
