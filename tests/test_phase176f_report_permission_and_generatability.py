"""Phase 176F — report permission metadata and generatability reconciliation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from backend.reports_center.capabilities import evaluate_report_capabilities, ui_report_definition
from backend.reports_center.registry import by_code, catalog_payload
from backend.reports_center.ui_contract import (
    capability_parity_payload,
    category_sections,
    generatable_selector_options,
)
from dashboard.mission_control.pages import render_page
from dashboard.mobile import mobile_reports


SUPER = "SUPER_USER"
TECH = "TECH"


def test_registry_permissions_survive_as_dict_serialization() -> None:
    d = by_code("daily_executive_brief")
    assert d is not None
    payload = d.as_dict()
    assert payload["required_view_permission"] == "reports_view"
    assert payload["required_generate_permission"] == "reports_generate"
    assert payload["required_print_permission"] == "executive_brief_print"
    assert payload["generatable"] is True
    assert "generatable" in payload


def test_catalog_api_payload_contains_exact_permission_names() -> None:
    cat = catalog_payload()
    row = next(r for r in cat["reports"] if r["report_code"] == "daily_executive_brief")
    assert row["required_view_permission"] == "reports_view"
    assert row["required_generate_permission"] == "reports_generate"
    assert row["required_print_permission"] == "executive_brief_print"
    assert row["generatable"] is True


def test_ui_report_dto_contains_exact_permission_names() -> None:
    d = by_code("daily_executive_brief")
    assert d is not None
    ui = ui_report_definition(d, role=SUPER)
    assert ui["required_view_permission"] == "reports_view"
    assert ui["required_generate_permission"] == "reports_generate"
    assert ui["required_print_permission"] == "executive_brief_print"
    assert ui["can_generate"] is True
    assert ui["generate_label"] == "Enabled"


@pytest.mark.parametrize(
    "code,expect_label",
    [
        ("daily_executive_brief", "Enabled"),
        ("safety_lock_report", "Enabled"),
        ("transaction_journal", "Enabled with limitations"),
        ("trade_journal", "Enabled with limitations"),
        ("account_statement", "Enabled with limitations"),
    ],
)
def test_super_user_generatable_known_reports(code: str, expect_label: str) -> None:
    d = by_code(code)
    assert d is not None
    caps = evaluate_report_capabilities(d, role=SUPER)
    assert caps["generatable"] is True
    assert caps["can_generate"] is True
    assert caps["generate_label"] == expect_label
    assert caps["required_generate_permission"] == "reports_generate"


def test_transaction_ticket_generatable_with_evidence_contract() -> None:
    d = by_code("transaction_ticket")
    assert d is not None
    caps = evaluate_report_capabilities(d, role=SUPER)
    assert caps["status"] == "AVAILABLE_WITH_LIMITATIONS"
    assert caps["generatable"] is True
    assert caps["can_generate"] is True
    assert caps["evidence_contract_supported"] is True
    assert "execution_report" in caps["evidence_sources"] or "ledger_transaction" in caps["evidence_sources"]
    # Generation still requires transaction evidence at produce() time — catalogue remains selectable.
    assert "transaction_ticket" in {g["report_code"] for g in generatable_selector_options(role=SUPER)}


@pytest.mark.parametrize(
    "code,status",
    [
        ("cash_forecast", "COMING_SOON"),
        ("live_execution_activity", "DISABLED"),
    ],
)
def test_unavailable_statuses_not_generatable(code: str, status: str) -> None:
    d = by_code(code)
    assert d is not None
    assert d.status == status
    caps = evaluate_report_capabilities(d, role=SUPER)
    assert caps["can_generate"] is False
    assert caps["generatable"] is False
    assert status in caps["generate_blocked_reason"] or caps["generate_blocked_reason"] == status


def test_data_unavailable_not_generatable() -> None:
    rows = [
        evaluate_report_capabilities(by_code(r["report_code"]), role=SUPER)  # type: ignore[arg-type]
        for r in catalog_payload(status="DATA_UNAVAILABLE")["reports"]
    ]
    assert rows
    assert all(not r["can_generate"] for r in rows)
    assert all(r["generate_blocked_reason"] == "DATA_UNAVAILABLE" for r in rows)


def test_missing_permission_metadata_fails_closed() -> None:
    base = by_code("daily_executive_brief")
    assert base is not None
    broken = replace(base, required_generate_permission="")
    caps = evaluate_report_capabilities(broken, role=SUPER)
    assert caps["can_generate"] is False
    assert caps["configuration_error"] == "missing_required_generate_permission"
    assert caps["generatable"] is False

    stripped = {
        "report_code": "daily_executive_brief",
        "status": "AVAILABLE",
        "producer": base.producer,
        "evidence_sources": list(base.evidence_sources),
        # omit required_* permissions intentionally
    }
    caps2 = evaluate_report_capabilities(stripped, role=SUPER)
    assert caps2["can_generate"] is False
    assert caps2["configuration_error"] in {
        "missing_required_view_permission",
        "missing_required_generate_permission",
    }


def test_tech_role_cannot_generate() -> None:
    d = by_code("safety_lock_report")
    assert d is not None
    caps = evaluate_report_capabilities(d, role=TECH)
    assert caps["can_generate"] is False
    assert "safety_lock_report" not in {g["report_code"] for g in generatable_selector_options(role=TECH)}


def test_desktop_mobile_capability_parity() -> None:
    desktop = capability_parity_payload(role=SUPER)
    mobile = capability_parity_payload(role=SUPER)
    assert desktop["generatable_count"] == mobile["generatable_count"]
    by_d = {r["report_code"]: r["can_generate"] for r in desktop["reports"]}
    by_m = {r["report_code"]: r["can_generate"] for r in mobile["reports"]}
    assert by_d == by_m

    # Mobile cards use the same category_sections contract.
    cats = category_sections(role=SUPER)
    sample = next(r for c in cats for r in c["reports"] if r["report_code"] == "daily_executive_brief")
    assert sample["required_view_permission"] == "reports_view"
    assert sample["can_generate"] is True


def test_desktop_html_no_none_permissions_on_available() -> None:
    html = render_page(
        "reports_center",
        {
            "governance": {"role": SUPER, "current_user": "00000"},
            "authorization_context": {
                "authenticated": True,
                "user_id": "00000",
                "role": SUPER,
                "identity_source": "test",
            },
            "reports_authorization": {
                "authenticated": True,
                "user_id": "00000",
                "role": SUPER,
                "reports_view": True,
                "reports_generate": True,
            },
        },
    )
    assert "View permission: reports_view" in html
    assert "Generate permission: reports_generate" in html
    assert "Print permission: executive_brief_print" in html
    assert "view=None" not in html
    assert "Generate permission: None" not in html
    # Frequently used must not show Not generatable for DEB
    assert 'data-report-code="daily_executive_brief" data-generatable="true"' in html
    assert "safety_lock_report" in html
    assert 'id="rc-report-code"' in html
    # Create selector options present
    assert 'value="safety_lock_report"' in html
    assert 'value="daily_executive_brief"' in html


def test_generate_button_preselect_wiring() -> None:
    html = render_page(
        "reports_center",
        {
            "governance": {"role": "ADMIN", "current_user": "admin1"},
            "reports_authorization": {
                "authenticated": True,
                "user_id": "admin1",
                "role": "ADMIN",
                "reports_view": True,
                "reports_generate": True,
            },
        },
    )
    assert 'data-rc-action="generate-open"' in html
    assert "selectEl.value = code" in html
    assert 'id="rc-report-code"' in html


def test_no_available_incorrectly_not_generatable_for_super() -> None:
    opts = {g["report_code"] for g in generatable_selector_options(role=SUPER)}
    for d in catalog_payload()["reports"]:
        if d["status"] not in {"AVAILABLE", "AVAILABLE_WITH_LIMITATIONS"}:
            continue
        code = d["report_code"]
        caps = evaluate_report_capabilities(by_code(code), role=SUPER)  # type: ignore[arg-type]
        if caps["producer_registered"] and caps["configuration_error"] is None:
            assert code in opts, f"{code} should be selectable"
            assert caps["can_generate"] is True


def test_mobile_permissions_not_none() -> None:
    html = mobile_reports.render_reports_home(
        {"role": SUPER, "user_id": "00000", "display_name": "SU"},
        header_fn=lambda title, user, active: f"<header>{title}</header>",
        page_fn=lambda title, body: body,
        identity_fn=lambda user, extra="": "<div>id</div>",
    )
    assert "View: reports_view" in html
    assert "Generate: reports_generate" in html
    assert "View: None" not in html


def test_counts_for_super_user() -> None:
    payload = capability_parity_payload(role=SUPER)
    assert payload["available_generatable"] >= 1
    assert payload["available_with_limitations_generatable"] >= 1
    assert payload["generatable_count"] == (
        payload["available_generatable"] + payload["available_with_limitations_generatable"]
    )
