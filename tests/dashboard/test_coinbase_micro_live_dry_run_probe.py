from __future__ import annotations

import copy
import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.coinbase_micro_live_dry_run_probe import (
    COINBASE_MICRO_LIVE_DRY_RUN_PROBE_PAYLOAD_VERSION,
    PROBE_FAIL,
    PROBE_MODE,
    PROBE_PASS,
    PROBE_REVIEW_REQUIRED,
    build_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def _valid_requested_order() -> dict:
    return {
        "broker": "coinbase",
        "symbol": "BTC-USD",
        "asset_class": "crypto",
        "currency": "CAD",
        "capital": "15.00",
        "order_type": "limit",
        "max_live_orders": 1,
        "max_slippage_pct": "0.35",
    }


def _valid_intent() -> dict:
    return build_micro_live_pilot_order_intent_payload(
        _valid_requested_order(),
        side="BUY",
    )


def test_probe_is_non_executing_and_passes_default_intent() -> None:
    payload = build_coinbase_micro_live_dry_run_probe_payload(_valid_intent())

    assert (
        payload["payload_version"]
        == COINBASE_MICRO_LIVE_DRY_RUN_PROBE_PAYLOAD_VERSION
    )
    assert payload["probe_id"].startswith("CBPROBE-")
    assert payload["probe_mode"] == PROBE_MODE
    assert payload["validation_status"] == PROBE_PASS
    assert payload["broker"] == "Coinbase Advanced"
    assert payload["symbol"] == "BTC-USD"
    assert payload["order_type"] == "limit"
    assert payload["max_pilot_capital_cad"] == "15.00"
    assert payload["max_slippage_pct"] == "0.35"
    assert payload["max_live_orders"] == 1
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["credential_secret_exposed"] is False
    assert payload["audit_payload"]["order_submitted"] is False
    assert payload["audit_payload"]["broker_mutated"] is False
    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_submit_endpoint"] is True


def test_probe_fails_for_unsafe_or_out_of_scope_intent() -> None:
    intent = copy.deepcopy(_valid_intent())
    intent.update(
        {
            "execution_allowed": True,
            "symbol": "ETH-USD",
            "order_type": "market",
            "max_pilot_capital_cad": "20.00",
            "max_slippage_pct": "0.50",
            "max_live_orders": 2,
        }
    )

    payload = build_coinbase_micro_live_dry_run_probe_payload(intent)
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["validation_status"] == PROBE_FAIL
    assert "execution_allowed_false" in failed_ids
    assert "symbol_is_btc_usd" in failed_ids
    assert "order_type_is_limit" in failed_ids
    assert "capital_cap_cad_15" in failed_ids
    assert "slippage_cap_0_35" in failed_ids
    assert "max_live_orders_one" in failed_ids
    assert payload["blockers"]
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False


def test_probe_review_required_when_approvals_are_missing() -> None:
    intent = copy.deepcopy(_valid_intent())
    intent["required_approvals"] = []

    payload = build_coinbase_micro_live_dry_run_probe_payload(intent)
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["validation_status"] == PROBE_REVIEW_REQUIRED
    assert "required_approvals_present" in failed_ids
    assert payload["blockers"] == []
    assert "REVIEW_ITEMS_REMAIN" in payload["warnings"]


def test_probe_redacts_sensitive_audit_payload() -> None:
    intent = copy.deepcopy(_valid_intent())
    intent["api_key"] = "SHOULD_NOT_LEAK"
    intent["requested_order"]["api_secret"] = "SHOULD_NOT_LEAK"

    payload = build_coinbase_micro_live_dry_run_probe_payload(intent)
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert "SHOULD_NOT_LEAK" not in encoded
    assert "REDACTED" in encoded


def test_probe_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_coinbase_micro_live_dry_run_probe_payload(_valid_intent())

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False


def test_probe_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_coinbase_micro_live_dry_run_probe_payload()

    assert "/api/v1/coinbase-micro-live-dry-run-probe" in routes
    assert payload["probe_mode"] == PROBE_MODE
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["audit_payload"]["order_submitted"] is False
    assert payload["audit_payload"]["broker_mutated"] is False


def test_probe_operator_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "/api/v1/coinbase-micro-live-dry-run-probe" in markup
    assert "Coinbase Dry-Run Probe Evidence" in markup
    assert "Probe Blockers / Warnings" in markup
    assert "No order was submitted" in markup
    assert "broker-mutation disabled" in markup
