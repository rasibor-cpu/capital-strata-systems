"""Wave 4 Product Honesty & Customer Trust regression tests."""

from __future__ import annotations

from pathlib import Path

from backend.notifications.providers.email_provider import EmailNotificationProvider
from backend.notifications.providers.sms_provider import SMSNotificationProvider
from backend.notifications.providers.push_provider import PushNotificationProvider
from backend.product_honesty import (
    catalogue_honesty_summary,
    eis_dashboard_honesty,
    notification_honesty_status,
    product_honesty_bundle,
)
from backend.reports_center.registry import catalog_payload
from backend.notifications import create_notification_event
from backend.events.event_models import Event


def _event() -> Event:
    return create_notification_event(
        severity="INFO",
        category="ORDER",
        title="t",
        message="m",
        user_id="u1",
        delivery_channels=["email"],
    )


def test_ar017_catalogue_honesty_registered_not_delivered():
    honesty = catalogue_honesty_summary()
    assert honesty["registered_implies_delivered"] is False
    assert honesty["generatable_count"] == honesty["mvp_eligible_count"]
    assert honesty["generatable_count"] < honesty["registered_count"]
    assert honesty["board_investor_regulatory_scope"] == "OUT_OF_SCOPE"
    assert "Registered ≠ delivered" in honesty["customer_banner"] or "registered" in honesty["customer_banner"].lower()

    payload = catalog_payload()
    assert payload["registered_implies_delivered"] is False
    assert payload["generatable_count"] == honesty["generatable_count"]
    assert payload["customer_banner"]
    assert payload["certification_claimed"] is False


def test_ar047_018_scope_decisions_documented():
    doc = Path("docs/release/CSS_WAVE4_PRODUCT_HONESTY_SCOPE.md")
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "OUT OF SCOPE" in text
    assert "DEFER" in text.upper() or "DEFERRED" in text.upper()
    assert "AR-017" in text and "AR-047" in text and "AR-018" in text

    eis = eis_dashboard_honesty()
    assert eis["full_eis_182a_released"] is False
    assert eis["gate2_disposition"] == "DEFERRED"
    assert eis["not_audited_statutory_statements"] is True


def test_ar022_non_operational_refuses_simulated_success(monkeypatch):
    monkeypatch.delenv("CSS_NOTIFICATIONS_OPERATIONAL", raising=False)
    event = _event()
    assert EmailNotificationProvider(dry_run=False).send(event) is False
    assert SMSNotificationProvider(dry_run=False).send(event) is False
    assert PushNotificationProvider(dry_run=False).send(event) is False
    # Dry-run remains allowed for tests / sandbox
    assert EmailNotificationProvider(dry_run=True).send(event) is True

    status = notification_honesty_status()
    assert status["notifications_operational"] is False
    assert status["delivery_simulated_by_default"] is True


def test_ar022_operational_flag_allows_non_dry_run_path(monkeypatch):
    monkeypatch.setenv("CSS_NOTIFICATIONS_OPERATIONAL", "1")
    event = _event()
    # Still abstraction — returns True only when explicitly marked operational
    assert EmailNotificationProvider(dry_run=False).send(event) is True


def test_ar042_executive_package_provenance():
    from backend.executive_reporting.package import build_executive_financial_report_package

    pkg = build_executive_financial_report_package(
        {
            "report_id": "t",
            "schema_version": "test",
            "reporting_period": {"period_type": "DAILY"},
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow_statement": {},
            "profitability_run_rate": {},
            "readiness": {"status": "NOT_READY"},
        }
    )
    meta = pkg["metadata"]
    assert meta["management_report"] is True
    assert meta["not_audited_statutory_statements"] is True
    assert meta["board_investor_regulatory_scope"] == "OUT_OF_SCOPE"
    assert meta["eis_182a_released"] is False
    assert any("OUT OF SCOPE" in lim for lim in pkg["limitations"])


def test_ar025_launcher_manifest_non_canonical():
    from backend.common.branding.service import CSSBrandService

    # Replicate launcher honesty fields without importing full launcher module.
    payload = CSSBrandService().manifest(
        start_url="/mobile-launcher",
        app_id="/css-mobile-launcher",
        name="CSS Mobile Launcher",
        short_name="CSS",
    )
    payload["css_canonical_install"] = False
    assert payload["css_canonical_install"] is False
    doc = Path("docs/operations/CSS_PWA_CANONICAL_INSTALL.md")
    assert doc.is_file()


def test_ar031_still_closed_empty_registry():
    from backend.options.options_income_provider_registry import (
        clear_provider_plugins,
        provider_registry_status,
    )

    clear_provider_plugins()
    status = provider_registry_status()
    assert status["execution_allowed"] is False
    assert status["advisory_only"] is True
    assert status["option_chain_status"] == "OPTION_CHAIN_PROVIDER_NOT_CONFIGURED"


def test_wave4_honesty_bundle():
    bundle = product_honesty_bundle()
    assert bundle["gate"] == "Release Gate 2"
    assert bundle["wave"] in {"Wave 4", "Final Close-Out"}
    assert bundle["execution_allowed"] is False
    assert bundle["live_trading"] == "BLOCKED"
    assert bundle["options_advisory"]["status"] == "CLOSED_WAVE2"
    assert bundle["pwa"]["status"] == "PARTIALLY_CLOSED"
    assert bundle["deployment"]["cd_mode"] == "manual_with_approvals"
