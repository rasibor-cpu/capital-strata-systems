"""Phase 176E — report generation route reconciliation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.reports_center.service import ReportsCenterService
from dashboard.mission_control.pages import render_page
from backend.security.authorization_context import apply_auth_to_mission_control_state, context_from_identity


def _auth_headers(role: str = "SUPER_USER", user_id: str = "00000") -> dict[str, str]:
    return {"X-CSS-Role": role, "X-CSS-User-Id": user_id}


def test_launcher_app_registers_reports_generate_route() -> None:
    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    openapi = client.get("/openapi.json").json()
    assert "/api/v1/reports/generate" in openapi.get("paths", {})
    assert "post" in openapi["paths"]["/api/v1/reports/generate"]
    # Controlled write surface coexists with MC GET-only reports APIs
    assert "/mission-control/api/reports/home" in openapi["paths"]


def test_web_app_still_registers_generate() -> None:
    from dashboard.web.web_app import create_app

    client = TestClient(create_app())
    openapi = client.get("/openapi.json").json()
    assert "/api/v1/reports/generate" in openapi["paths"]


def test_desktop_reports_js_uses_canonical_generate_path() -> None:
    state = apply_auth_to_mission_control_state(
        {
            "schema_version": "t",
            "generated_at": "t",
            "platform": {},
            "safety": {"live_trading_blocked": True},
            "runtime": {},
            "governance": {"role": "SUPER_USER", "current_user": "00000"},
        },
        context_from_identity(
            user_id="00000",
            role="SUPER_USER",
            channel="test",
            identity_source="test",
        ),
    )
    html = render_page("reports_center", state)
    assert "fetch('/api/v1/reports/generate'" in html or 'fetch("/api/v1/reports/generate"' in html
    assert "/api/v1/reports/" in html


def test_launcher_generate_super_user_archives(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setattr(
        "dashboard.auth.css_sign_on.restore_login_session",
        lambda users=None: None,
    )
    monkeypatch.setattr("dashboard.auth.session_bridge._load_recovery_user_ctx", lambda: None)

    from launcher.css_mobile_launcher import app

    # Isolate archive under tmp
    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    monkeypatch.setattr(
        "backend.reports_center.routes.ReportsCenterService",
        lambda repo_root=None: ReportsCenterService(
            repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit"
        ),
    )

    client = TestClient(app)
    res = client.post(
        "/api/v1/reports/generate",
        headers=_auth_headers(),
        json={"report_code": "safety_lock_report", "persist": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("status") == "OK"
    report_id = body.get("report_id") or (body.get("report") or {}).get("report_id")
    assert report_id
    assert body.get("advisory_only") is True
    assert body.get("execution_allowed") is False

    detail = client.get(f"/api/v1/reports/{report_id}", headers=_auth_headers())
    assert detail.status_code == 200
    assert detail.json().get("status") == "OK"

    library = client.get("/api/v1/reports", headers=_auth_headers())
    assert library.status_code == 200

    printed = client.get(f"/api/v1/reports/{report_id}/print", headers=_auth_headers())
    assert printed.status_code == 200
    assert "html" in printed.headers.get("content-type", "").lower() or printed.text

    versions = client.get(f"/api/v1/reports/{report_id}/versions", headers=_auth_headers())
    assert versions.status_code == 200

    audit = client.get(f"/api/v1/reports/{report_id}/audit", headers=_auth_headers())
    assert audit.status_code == 200

    verify = client.post(f"/api/v1/reports/{report_id}/verify-integrity", headers=_auth_headers())
    assert verify.status_code == 200
    assert verify.json().get("status") in {"OK", "MISMATCH"}


def test_launcher_generate_unauthorized_denied(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "1")
    monkeypatch.setattr("dashboard.auth.css_sign_on.restore_login_session", lambda users=None: None)
    monkeypatch.setattr("dashboard.auth.session_bridge._load_recovery_user_ctx", lambda: None)

    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    denied = client.post(
        "/api/v1/reports/generate",
        headers=_auth_headers("TECH", "tech1"),
        json={"report_code": "safety_lock_report"},
    )
    assert denied.status_code in {403, 400}
    missing = client.post("/api/v1/reports/generate", json={"report_code": "safety_lock_report"})
    assert missing.status_code == 403


def test_forged_headers_denied_without_trust(monkeypatch) -> None:
    monkeypatch.setenv("CSS_TRUST_INTERNAL_AUTH_HEADERS", "0")
    monkeypatch.setattr("dashboard.auth.css_sign_on.restore_login_session", lambda users=None: None)
    monkeypatch.setattr("dashboard.auth.session_bridge._load_recovery_user_ctx", lambda: None)

    from launcher.css_mobile_launcher import app

    client = TestClient(app)
    forged = client.post(
        "/api/v1/reports/generate",
        headers=_auth_headers("SUPER_USER", "00000"),
        json={"report_code": "safety_lock_report"},
    )
    assert forged.status_code == 403


def test_mobile_generate_form_still_canonical_service() -> None:
    text = Path("dashboard/mobile/mobile_reports.py").read_text(encoding="utf-8")
    assert 'action="/reports/generate"' in text
    app_text = Path("dashboard/mobile/mobile_app.py").read_text(encoding="utf-8")
    assert "create_reports_center_router" in app_text
    assert '@app.post("/reports/generate"' in app_text or "@app.post('/reports/generate'" in app_text
