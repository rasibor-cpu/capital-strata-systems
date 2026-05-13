from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_broker_live_dry_run_certification_payload,
)
from dashboard.runtime.broker_live_dry_run_certification import (
    BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION,
    LIVE_DRY_RUN_BLOCKED,
    LIVE_DRY_RUN_CERTIFIED,
    append_broker_live_dry_run_certification_log,
    certify_broker_live_dry_run,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads


def _live_coinbase_dashboard_payload() -> dict:
    payloads = build_smoke_payloads()
    payloads["account_payload"] = {
        **payloads["account_payload"],
        "broker": "coinbase",
        "account_mode": "live",
    }
    payloads["positions_payload"] = {"positions": []}
    payloads["session_payload"] = {
        **payloads["session_payload"],
        "live_or_paper": "live",
    }
    payloads["broker_payload"] = {
        "selected_broker": "coinbase",
        "broker_mode": "live",
        "connected": True,
        "live_trading_enabled": False,
        "last_heartbeat": "2026-05-13T16:00:00+00:00",
        "api_health": "OK",
        "reconnect_state": "STABLE",
        "supported_assets": ["crypto", "spot_crypto"],
        "account_readiness": "LIVE_READY",
        "missing_credentials": False,
        "latency_ms": 25.0,
        "readiness_status": "BROKER_READY",
        "account_snapshot": {
            "cash_balance": "10000.00",
            "total_equity": "10250.00",
            "buying_power": "5000.00",
            "currency": "USD",
        },
        "position_snapshot": [],
    }
    return DashboardHydrationCoordinator().hydrate(**payloads).to_dict()


def _dry_run_probe() -> dict:
    return {
        "broker": "coinbase",
        "symbol": "BTC-USD",
        "asset_class": "crypto",
        "side": "BUY",
        "order_type": "market",
        "dry_run": True,
        "submitted_to_broker": False,
        "would_place_live_order": False,
        "order_intent_valid": True,
        "broker_acknowledged": True,
        "estimated_notional": "25.00",
        "estimated_cost": "0.02",
        "api_secret": "SHOULD_NOT_LEAK",
    }


def test_live_dry_run_certifies_only_clean_non_executing_probe() -> None:
    report = certify_broker_live_dry_run(
        _live_coinbase_dashboard_payload(),
        order_probe=_dry_run_probe(),
    )
    payload = report.as_dict()
    encoded = json.dumps(payload, sort_keys=True)

    assert report.status == LIVE_DRY_RUN_CERTIFIED
    assert report.certified_for_live is True
    assert report.safe_degradation_required is False
    assert payload["payload_version"] == BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION
    assert payload["recommended_runtime_mode"] == "live"
    assert payload["reconciliation_status"] == "BROKER_RECONCILED"
    assert payload["order_probe_status"] == "DRY_RUN_ACKNOWLEDGED"
    assert "SHOULD_NOT_LEAK" not in encoded


def test_live_dry_run_fails_closed_without_probe() -> None:
    report = certify_broker_live_dry_run(_live_coinbase_dashboard_payload())
    failed_codes = {check.code for check in report.checks if not check.passed}

    assert report.status == LIVE_DRY_RUN_BLOCKED
    assert report.certified_for_live is False
    assert report.safe_degradation_required is True
    assert report.recommended_runtime_mode == "paper"
    assert "dry_run_probe_present" in failed_codes
    assert "dry_run_probe_non_executing" in failed_codes


def test_live_dry_run_fails_closed_for_unregistered_broker() -> None:
    dashboard_payload = _live_coinbase_dashboard_payload()
    dashboard_payload["broker_summary"] = {
        **dashboard_payload["broker_summary"],
        "selected_broker": "IBKR",
    }

    report = certify_broker_live_dry_run(
        dashboard_payload,
        order_probe=_dry_run_probe(),
    )
    failed_codes = {check.code for check in report.checks if not check.passed}

    assert report.status == LIVE_DRY_RUN_BLOCKED
    assert report.broker_registered is False
    assert "broker_registered" in failed_codes
    assert "broker_supports_live" in failed_codes


def test_live_dry_run_certification_api_is_read_only_and_fail_closed() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_broker_live_dry_run_certification_payload(lambda: state)

    assert "/api/v1/broker-live-dry-run-certification" in routes
    assert payload["payload_version"] == BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION
    assert payload["status"] == LIVE_DRY_RUN_BLOCKED
    assert payload["certified_for_live"] is False
    assert payload["recommended_runtime_mode"] == "paper"


def test_live_dry_run_log_is_jsonl_and_redacted(tmp_path) -> None:
    report = certify_broker_live_dry_run(
        _live_coinbase_dashboard_payload(),
        order_probe=_dry_run_probe(),
    )
    log_path = tmp_path / "live_dry_run_certification.jsonl"

    append_broker_live_dry_run_certification_log(report, log_path)
    encoded = log_path.read_text(encoding="utf-8")
    row = json.loads(encoded)

    assert row["payload_version"] == BROKER_LIVE_DRY_RUN_CERTIFICATION_PAYLOAD_VERSION
    assert "SHOULD_NOT_LEAK" not in encoded
