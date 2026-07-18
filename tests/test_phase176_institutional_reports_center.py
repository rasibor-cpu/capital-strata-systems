"""Phase 176 — CSS Institutional Reports Center tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.reports_center.archive import ReportArchiveStore
from backend.reports_center.catalogue import CATALOGUE, build_catalogue
from backend.reports_center.producers import validate_filters
from backend.reports_center.rbac import ReportsAccessControl
from backend.reports_center.registry import by_code, catalog_payload
from backend.reports_center.routes import create_reports_center_router
from backend.reports_center.service import ReportsCenterService
from backend.security.permissions import PermissionEngine
from dashboard.mission_control.host_registration import register_mission_control
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS


def test_catalogue_unique_codes_and_valid_statuses() -> None:
    codes = [d.report_code for d in CATALOGUE]
    assert len(codes) == len(set(codes))
    assert len(CATALOGUE) >= 100
    valid = {
        "AVAILABLE",
        "AVAILABLE_WITH_LIMITATIONS",
        "DATA_UNAVAILABLE",
        "DISABLED",
        "COMING_SOON",
        "DEPRECATED",
    }
    for d in CATALOGUE:
        assert d.status in valid
        assert d.category
        assert d.schema_version
        if d.status in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"}:
            assert d.producer, d.report_code
            assert d.generatable


def test_no_available_without_producer() -> None:
    for d in build_catalogue():
        if d.status in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"}:
            assert d.producer, d.report_code
            assert d.validator, d.report_code
            assert d.supported_formats, d.report_code
            assert d.required_view_permission, d.report_code
            assert d.required_generate_permission, d.report_code
            assert d.evidence_sources, d.report_code
            assert d.generatable
            assert "XLSX" not in d.supported_formats
            if "PDF" in d.supported_formats:
                assert d.report_code == "daily_executive_brief"
            if d.emailable:
                assert d.report_code == "daily_executive_brief"
                assert d.email_policy == "EXECUTIVE_BRIEF_ADMIN_SUPER_ONLY"
            else:
                assert d.email_policy == "EMAIL_DISABLED"
            if d.status == "AVAILABLE_WITH_LIMITATIONS":
                assert d.official_report is False


def test_format_claims_match_implementation() -> None:
    csv_codes = {d.report_code for d in CATALOGUE if "CSV" in d.supported_formats}
    assert csv_codes <= {"transaction_journal", "trade_journal"}
    for d in CATALOGUE:
        if d.status not in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"}:
            assert not d.generatable
    assert by_code("live_execution_activity").status == "DISABLED"
    assert by_code("treasury_instrument_aggregate").status == "DATA_UNAVAILABLE"
    assert by_code("account_statement").status == "AVAILABLE_WITH_LIMITATIONS"
    handlers_src = Path("backend/reports_center/producers.py").read_text(encoding="utf-8")
    for d in CATALOGUE:
        if d.generatable:
            assert f'"{d.report_code}"' in handlers_src, d.report_code


def test_navigation_includes_reports_and_count_16() -> None:
    keys = [s.key for s in MISSION_CONTROL_SECTIONS]
    assert "reports_center" in keys
    assert len(MISSION_CONTROL_SECTIONS) == 16


def test_unsafe_filters_rejected() -> None:
    try:
        validate_filters({"account": "../etc/passwd"})
        assert False, "expected ValueError"
    except ValueError:
        pass
    try:
        validate_filters({"q": "1; DROP TABLE x"})
        assert False
    except ValueError:
        pass
    ok = validate_filters({"account": "ACC-1", "from_date": "2026-07-01"})
    assert ok["account"] == "ACC-1"


def test_rbac_staff_denied_generate_admin_allowed() -> None:
    access = ReportsAccessControl(PermissionEngine())
    assert access.can_generate("ADMIN", "reports_generate")
    assert access.can_print("SUPER_USER", "reports_print_all")
    assert not access.can_generate("VIEWER", "reports_generate")
    assert not access.can_email("STAFF", "executive_brief_email")
    assert not access.can_email("ADMIN", "")  # EMAIL_DISABLED default
    assert access.can_email("ADMIN", "executive_brief_email")


def test_generate_safety_lock_and_archive(tmp_path: Path) -> None:
    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    result = svc.generate("safety_lock_report", filters={}, role="ADMIN", user_id="admin1", persist=True)
    assert result["status"] == "OK"
    assert result["report"]["advisory_only"] is True
    assert result["report"]["execution_allowed"] is False
    assert result["report"]["live_trading_blocked"] is True
    assert result["report"]["broker_execution_armed"] is False
    report_id = result["report_id"]
    retrieved = svc.retrieve(report_id, role="ADMIN")
    assert retrieved["status"] == "OK"
    verify = svc.verify_integrity(report_id, role="ADMIN", user_id="admin1")
    assert verify["outcome"] == "PASS"


def test_coming_soon_not_generatable(tmp_path: Path) -> None:
    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    result = svc.generate("cash_forecast", role="ADMIN", user_id="admin1")
    assert result["status"] == "NOT_GENERATABLE"


def test_transaction_journal_and_ticket(tmp_path: Path) -> None:
    ledger = tmp_path / "reporting_store"
    ledger.mkdir()
    (ledger / "pnl_ledger_test.jsonl").write_text(
        json.dumps(
            {
                "ts_utc": "2026-07-17T12:00:00Z",
                "symbol": "EUR_USD",
                "side": "BUY",
                "qty": 1000,
                "pnl": 12.5,
                "fees": 1.0,
                "user_id": "trader1",
                "broker": "OANDA",
                "is_paper": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    # Point env-relative path by writing under cwd-style: producers look at repo_root / reporting_store
    journal = svc.generate(
        "transaction_journal",
        filters={"from_date": "2026-07-01", "to_date": "2026-07-18", "user": "trader1"},
        role="ADMIN",
        user_id="admin1",
    )
    assert journal["status"] == "OK"
    assert journal["report"]["content"]["count"] >= 1

    ticket = svc.generate(
        "transaction_ticket",
        filters={
            "execution_evidence_json": json.dumps(
                {
                    "execution_id": "EX1",
                    "order_id": "ORD1",
                    "symbol": "EUR_USD",
                    "side": "BUY",
                    "filled_qty": 1000,
                    "fill_price": 1.1,
                    "is_paper": True,
                    "api_key": "SHOULD_NOT_APPEAR",
                }
            )
        },
        role="ADMIN",
        user_id="admin1",
    )
    assert ticket["status"] == "OK"
    html = ticket["report"]["html"]
    assert "EX1" in html
    assert "SHOULD_NOT_APPEAR" not in html
    assert "PAPER" in html or "paper" in html.lower() or "MODE BANNER" in html


def test_account_statement_limitation_banner(tmp_path: Path) -> None:
    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    result = svc.generate("account_statement", filters={"account": "A1"}, role="ADMIN", user_id="a")
    assert result["status"] == "OK"
    assert "AVAILABLE_WITH_LIMITATIONS" in result["report"]["limitations"]
    assert result["report"]["official_report"] is False


def test_print_denied_for_viewer(tmp_path: Path) -> None:
    svc = ReportsCenterService(repo_root=tmp_path, archive_root=tmp_path / "reports", audit_root=tmp_path / "audit")
    gen = svc.generate("broker_health_report", role="ADMIN", user_id="a")
    # May FAIL if no evidence — still archive FAILED
    if gen["status"] != "OK":
        # Force safety lock which always works
        gen = svc.generate("safety_lock_report", role="ADMIN", user_id="a")
    report_id = gen["report_id"]
    denied = svc.printable_html(report_id, role="VIEWER", user_id="v1")
    assert denied["status"] == "DENIED"
    allowed = svc.printable_html(report_id, role="ADMIN", user_id="a")
    assert allowed["status"] == "OK"


def test_email_endpoint_disabled() -> None:
    app = FastAPI()
    app.include_router(create_reports_center_router(repo_root=Path.cwd()))
    client = TestClient(app)
    resp = client.post(
        "/api/v1/reports/cssrpt_x/email",
        headers={"X-CSS-Role": "ADMIN", "X-CSS-User-Id": "admin"},
        json={"recipients": ["x@y.com"]},
    )
    assert resp.status_code == 403
    assert resp.json()["status"] == "EMAIL_DISABLED"


def test_mission_control_get_only_reports_routes() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: None)
    client = TestClient(app)
    nav = client.get("/mission-control/api/navigation")
    assert nav.status_code == 200
    assert any(s.get("key") == "reports_center" for s in nav.json())
    cat = client.get("/mission-control/api/reports/catalog")
    assert cat.status_code == 200
    body = cat.json()
    assert body["total_registered"] == len(CATALOGUE)
    assert body.get("read_only") is True
    assert body.get("execution_allowed") is False
    assert body.get("live_trading_blocked") is True
    # Writes must not be registered on Mission Control
    assert client.post("/mission-control/api/reports/catalog").status_code in {405, 404, 400}

def test_fincon_report_printer_importable() -> None:
    from engine.reporting.report_printer import list_reports

    names = list_reports()
    assert "supervisory_control_pack" in names
    assert "treasury_instrument_aggregate" in names


def test_immutable_final_no_silent_overwrite(tmp_path: Path) -> None:
    store = ReportArchiveStore(tmp_path / "reports")
    a = store.publish(
        family="risk_exposure",
        report_type="safety_lock_report",
        report_date="2026-07-18",
        payload={"report_status": "FINAL", "title": "v1", "content": {"n": 1}},
        validation={"finalization_allowed": True},
    )
    b = store.publish(
        family="risk_exposure",
        report_type="safety_lock_report",
        report_date="2026-07-18",
        payload={"report_status": "FINAL", "title": "v2", "content": {"n": 2}},
        validation={"finalization_allowed": True},
    )
    assert a["report_version"] != b["report_version"]
    assert a["report_id"] != b["report_id"]
    first = store.retrieve(a["report_id"])
    assert first["content"]["n"] == 1


def test_catalog_search() -> None:
    payload = catalog_payload(q="executive")
    assert payload["count"] >= 5
    assert by_code("daily_executive_brief") is not None
    assert by_code("daily_executive_brief").status == "AVAILABLE"
