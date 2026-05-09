from __future__ import annotations

import json
from decimal import Decimal

from dashboard.runtime.api_bridge import (
    create_app,
    get_broker_reconciliation_payload,
)
from dashboard.runtime.broker_balance_reconciliation import (
    BROKER_DIVERGED,
    BROKER_RECONCILED,
    BROKER_UNAVAILABLE,
    append_reconciliation_log,
    reconcile_dashboard_payload,
    reconcile_broker_snapshots,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.frontend_contract import (
    build_frontend_payload,
    build_section_payload,
)
from dashboard.runtime.payload_validator import FrontendPayloadValidator
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads


def test_broker_reconciliation_passes_for_matching_snapshots() -> None:
    report = reconcile_broker_snapshots(
        css_account={
            "cash_balance": "10000.00",
            "total_equity": "10250.00",
            "buying_power": "5000.00",
            "currency": "USD",
        },
        css_positions=[
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "LONG", "qty": "0.05"},
            {"symbol": "EUR_USD", "asset_class": "FX", "side": "SHORT", "qty": "1000"},
        ],
        broker_account={
            "cash": "10000.25",
            "net_liquidation": "10250.50",
            "available_funds": "5000.00",
            "currency": "USD",
        },
        broker_positions=[
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "LONG", "qty": "0.05000000"},
            {"symbol": "EUR_USD", "asset_class": "FX", "side": "SELL", "quantity": "1000"},
        ],
        broker="IBKR",
        mode="live",
        broker_connected=True,
        readiness_status="BROKER_READY",
    )
    payload = report.as_dict()

    assert report.status == BROKER_RECONCILED
    assert report.safe_degradation_required is False
    assert payload["recommended_runtime_mode"] == "live"
    assert payload["summary"]["finding_count"] == 0
    assert json.dumps(payload, sort_keys=True)


def test_broker_reconciliation_detects_balance_and_position_divergence() -> None:
    report = reconcile_broker_snapshots(
        css_account={
            "cash_balance": "10000.00",
            "total_equity": "10250.00",
            "buying_power": "5000.00",
        },
        css_positions=[
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "LONG", "qty": "0.05"},
        ],
        broker_account={
            "cash_balance": "9900.00",
            "total_equity": "10100.00",
            "buying_power": "5000.00",
        },
        broker_positions=[
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "SHORT", "qty": "0.01"},
            {"symbol": "ETH-USD", "asset_class": "CRYPTO", "side": "LONG", "qty": "1"},
        ],
        broker="COINBASE",
        mode="live",
        broker_connected=True,
        readiness_status="BROKER_READY",
    )
    codes = {finding.code for finding in report.findings}

    assert report.status == BROKER_DIVERGED
    assert report.safe_degradation_required is True
    assert report.recommended_runtime_mode == "paper"
    assert "ACCOUNT_BALANCE_DIVERGENCE" in codes
    assert "POSITION_QTY_DIVERGENCE" in codes
    assert "POSITION_SIDE_DIVERGENCE" in codes
    assert "BROKER_POSITION_NOT_IN_CSS" in codes


def test_live_mode_missing_broker_snapshot_forces_safe_degradation() -> None:
    report = reconcile_broker_snapshots(
        css_account={"cash_balance": "10000", "total_equity": "10000"},
        css_positions=[],
        broker_account={},
        broker_positions=[],
        broker="IBKR",
        mode="live",
        broker_connected=False,
        readiness_status="BROKER_BLOCKED",
    )

    assert report.status == BROKER_UNAVAILABLE
    assert report.safe_degradation_required is True
    assert report.recommended_runtime_mode == "paper"
    assert report.escalation_level == "info"


def test_dashboard_payload_reconciliation_uses_broker_snapshots_without_secret_leakage() -> None:
    payloads = build_smoke_payloads()
    payloads["broker_payload"] = {
        "selected_broker": "IBKR",
        "broker_mode": "live",
        "connected": True,
        "live_trading_enabled": True,
        "readiness_status": "BROKER_READY",
        "account_readiness": "LIVE_READY",
        "account_snapshot": {
            "cash_balance": Decimal("10000.00"),
            "total_equity": Decimal("10250.00"),
            "buying_power": Decimal("5000.00"),
            "api_secret": "SHOULD_NOT_LEAK",
        },
        "position_snapshot": [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "side": "LONG", "qty": Decimal("0.05")},
            {"symbol": "EUR_USD", "asset_class": "FX", "side": "SHORT", "qty": Decimal("1000")},
        ],
    }
    payloads["session_payload"]["live_or_paper"] = "live"
    state = DashboardHydrationCoordinator().hydrate(**payloads)
    dashboard_payload = state.to_dict()
    report = reconcile_dashboard_payload(dashboard_payload)
    encoded = json.dumps(report.as_dict(), sort_keys=True)

    assert report.status == BROKER_RECONCILED
    assert "SHOULD_NOT_LEAK" not in encoded
    assert "REDACTED" not in encoded


def test_frontend_and_api_expose_broker_reconciliation_section() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    frontend_payload = build_frontend_payload(state)
    section_payload = build_section_payload(state, "broker_reconciliation")
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}
    direct_payload = get_broker_reconciliation_payload(lambda: state)

    assert FrontendPayloadValidator().validate(frontend_payload) is True
    assert "broker_reconciliation" in frontend_payload["sections"]
    assert section_payload["section"] == "broker_reconciliation"
    assert section_payload["data"]["payload_version"] == "css.broker_reconciliation.v1"
    assert "/api/v1/broker-reconciliation" in routes
    assert direct_payload["payload_version"] == "css.broker_reconciliation.v1"


def test_reconciliation_log_is_jsonl_and_redacted(tmp_path) -> None:
    report = reconcile_broker_snapshots(
        css_account={"cash_balance": "1", "total_equity": "1"},
        css_positions=[],
        broker_account={"cash_balance": "1", "total_equity": "1", "private_key": "NOPE"},
        broker_positions=[],
        broker_connected=True,
    )
    log_path = tmp_path / "broker_reconciliation.jsonl"

    append_reconciliation_log(report, log_path)
    encoded = log_path.read_text(encoding="utf-8")
    row = json.loads(encoded)

    assert row["payload_version"] == "css.broker_reconciliation.v1"
    assert "NOPE" not in encoded
