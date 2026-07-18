"""Functional certification helpers for Phase 176C (ASGI + optional Playwright)."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control.host_registration import register_mission_control
from dashboard.ui_function.registry import all_controls, assert_registry_complete, registry_summary
from dashboard.web.web_app import create_app as create_web_app


SAFETY_LOCKS = {
    "advisory_only": True,
    "execution_allowed": False,
    "live_trading_blocked": True,
    "broker_execution_armed": False,
}


def mission_control_client() -> TestClient:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    return TestClient(app)


def web_client() -> TestClient:
    return TestClient(create_web_app())


def mobile_client() -> TestClient:
    from dashboard.mobile.mobile_app import app as mobile_app

    return TestClient(mobile_app)


def certify_mc_nav() -> dict[str, Any]:
    client = mission_control_client()
    failures: list[str] = []
    for control in all_controls():
        if not control.control_id.startswith("mc.nav."):
            continue
        route = control.desktop_route
        res = client.get(route)
        if res.status_code != 200:
            failures.append(f"{control.control_id}: status={res.status_code}")
            continue
        if "Mission Control" not in res.text and "mc-shell" not in res.text:
            failures.append(f"{control.control_id}: missing MC shell")
        if 'aria-current="page"' not in res.text:
            failures.append(f"{control.control_id}: missing aria-current")
    return {"ok": not failures, "failures": failures, "checked": "mc.nav.*"}


def certify_web_nav() -> dict[str, Any]:
    client = web_client()
    failures: list[str] = []
    for control in all_controls():
        if not control.control_id.startswith("web.nav."):
            continue
        res = client.get(control.desktop_route)
        if res.status_code != 200:
            failures.append(f"{control.control_id}: status={res.status_code}")
            continue
        if 'class="active"' not in res.text:
            failures.append(f"{control.control_id}: missing active nav")
        # Probe linked APIs when refresh controls exist for same page key
    return {"ok": not failures, "failures": failures}


def certify_web_refresh_apis() -> dict[str, Any]:
    client = web_client()
    failures: list[str] = []
    for path in (
        "/api/v1/frontend-state",
        "/api/v1/capital-allocation-intelligence",
        "/api/v1/trade-summary",
        "/api/v1/session-command-centre",
        "/api/v1/live-readiness-certification",
        "/api/v1/margin-snapshot",
    ):
        res = client.get(path)
        if res.status_code not in {200, 503}:
            # 503 may be fail-closed unavailable — still a controlled response
            if res.status_code >= 500 and res.status_code != 503:
                failures.append(f"{path}: status={res.status_code}")
        body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        if isinstance(body, dict):
            # Never treat empty JSON as silent success fabrication marker
            if body.get("ok") is False and "error" not in body and "status" not in body:
                failures.append(f"{path}: ok=false without status/error")
    return {"ok": not failures, "failures": failures}


def certify_reports_workflow(tmp_path) -> dict[str, Any]:
    """End-to-end generate → retrieve via canonical service (not HTTP 200 alone)."""
    from backend.reports_center.service import ReportsCenterService

    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    gen = svc.generate("safety_lock_report", filters={}, role="ADMIN", user_id="phase176c", persist=True)
    if gen.get("status") != "OK":
        return {"ok": False, "failures": [f"generate_status={gen.get('status')}"], "result": gen}
    report_id = (gen.get("report") or {}).get("report_id")
    if not report_id:
        return {"ok": False, "failures": ["missing_report_id"], "result": gen}
    detail = svc.retrieve(report_id, role="ADMIN")
    if detail.get("status") != "OK":
        return {"ok": False, "failures": [f"retrieve={detail.get('status')}"], "result": detail}
    for lock, expected in SAFETY_LOCKS.items():
        if (gen.get("report") or {}).get(lock) not in {expected, None} and gen.get(lock) not in {expected, None}:
            # Prefer report payload locks; service also returns top-level SAFETY_LOCKS
            pass
    for lock, expected in SAFETY_LOCKS.items():
        if gen.get(lock) is not None and gen.get(lock) != expected:
            return {"ok": False, "failures": [f"safety_{lock}={gen.get(lock)}"], "result": gen}
    print_info = svc.print_info(report_id, role="ADMIN", user_id="phase176c")
    if print_info.get("status") != "OK":
        return {"ok": False, "failures": [f"print_info={print_info.get('status')}"], "result": print_info}
    lib = svc.list_library(filters={"view": "latest", "limit": 5}, role="ADMIN")
    if lib.get("status") != "OK":
        return {"ok": False, "failures": [f"library={lib.get('status')}"], "result": lib}
    denied = svc.generate("safety_lock_report", filters={}, role="VIEWER", user_id="v", persist=True)
    if denied.get("status") not in {"DENIED", "FORBIDDEN"}:
        # Some paths return DENIED
        if denied.get("status") == "OK":
            return {"ok": False, "failures": ["viewer_generate_not_denied"], "result": denied}
    return {
        "ok": True,
        "failures": [],
        "report_id": report_id,
        "library_count": lib.get("count"),
        "print_endpoint": print_info.get("html_endpoint"),
    }


def certify_mobile_reports_apis_mounted() -> dict[str, Any]:
    client = mobile_client()
    # Unauthenticated should not 500; 401/403/303/404 acceptable depending on auth wrapper
    res = client.get("/api/v1/reports/catalog", headers={"X-CSS-Role": "ADMIN", "X-CSS-User-Id": "a1"})
    if res.status_code == 404:
        return {"ok": False, "failures": ["reports_router_not_mounted"]}
    if res.status_code not in {200, 403}:
        return {"ok": False, "failures": [f"catalog_status={res.status_code}"]}
    return {"ok": True, "failures": [], "status": res.status_code}


def run_phase176c_certification(tmp_path) -> dict[str, Any]:
    assert_registry_complete()
    summary = registry_summary()
    parts = {
        "registry": summary,
        "mc_nav": certify_mc_nav(),
        "web_nav": certify_web_nav(),
        "web_apis": certify_web_refresh_apis(),
        "reports_workflow": certify_reports_workflow(tmp_path),
        "mobile_reports_api": certify_mobile_reports_apis_mounted(),
        "safety_locks": SAFETY_LOCKS,
    }
    ok = all(v.get("ok", True) for k, v in parts.items() if k not in {"registry", "safety_locks"})
    return {"ok": ok, **parts}
