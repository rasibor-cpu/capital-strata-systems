from __future__ import annotations

import copy
import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_micro_live_pilot_order_intent_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    CANONICAL_BROKER,
    CANONICAL_SYMBOL,
    MICRO_LIVE_PILOT_ORDER_INTENT_PAYLOAD_VERSION,
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page, create_app as create_web_app


def test_order_intent_is_non_executing_and_constraint_locked() -> None:
    payload = build_micro_live_pilot_order_intent_payload(side="BUY")

    assert payload["payload_version"] == MICRO_LIVE_PILOT_ORDER_INTENT_PAYLOAD_VERSION
    assert payload["intent_id"].startswith("MLINTENT-")
    assert payload["broker"] == CANONICAL_BROKER
    assert payload["symbol"] == CANONICAL_SYMBOL
    assert payload["order_type"] == "limit"
    assert payload["side"] == "BUY"
    assert payload["side_review_only"] is True
    assert payload["max_pilot_capital_cad"] == "15.00"
    assert payload["max_slippage_pct"] == "0.35"
    assert payload["max_live_orders"] == 1
    assert payload["execution_allowed"] is False
    assert payload["requires_operator_confirmation"] is True
    assert payload["requires_broker_dry_run_certification"] is True
    assert payload["requires_kill_switch_verification"] is True
    assert payload["requires_pcnrass_release_check"] is True
    assert "LIVE_ORDER_EXECUTION_DISABLED_FROM_INTENT_PACKAGE" in payload["blockers"]


def test_order_intent_required_approvals_are_visible() -> None:
    payload = build_micro_live_pilot_order_intent_payload()
    approvals = set(payload["required_approvals"])

    assert "explicit operator confirmation" in approvals
    assert "Coinbase non-executing dry-run certification" in approvals
    assert "kill-switch verification" in approvals
    assert "PCNRASS release check" in approvals
    assert "broker readiness evidence" in approvals


def test_order_intent_blocks_out_of_scope_requests_and_redacts() -> None:
    payload = build_micro_live_pilot_order_intent_payload(
        {
            "broker": "oanda",
            "symbol": "ETH-USD",
            "asset_class": "fx",
            "currency": "USD",
            "capital": "20.00",
            "order_type": "market",
            "max_live_orders": 2,
            "max_slippage_pct": "0.50",
            "api_key": "SHOULD_NOT_LEAK",
            "note": "token=SHOULD_NOT_LEAK",
        }
    )
    blockers = set(payload["blockers"])
    encoded = json.dumps(payload, sort_keys=True)

    assert "REQUESTED_BROKER_OUTSIDE_PILOT_SCOPE" in blockers
    assert "REQUESTED_SYMBOL_OUTSIDE_PILOT_SCOPE" in blockers
    assert "REQUESTED_ORDER_TYPE_NOT_LIMIT" in blockers
    assert "REQUESTED_CAPITAL_EXCEEDS_CAD_15" in blockers
    assert "REQUESTED_SLIPPAGE_EXCEEDS_0_35_PCT" in blockers
    assert "SHOULD_NOT_LEAK" not in encoded
    assert "REDACTED" in encoded


def test_order_intent_does_not_mutate_requested_order() -> None:
    requested = {
        "broker": "coinbase",
        "symbol": "BTC-USD",
        "asset_class": "crypto",
        "currency": "CAD",
        "capital": "15.00",
        "order_type": "limit",
        "max_live_orders": 1,
        "max_slippage_pct": "0.35",
    }
    before = copy.deepcopy(requested)

    payload = build_micro_live_pilot_order_intent_payload(requested)

    assert requested == before
    assert payload["execution_allowed"] is False
    assert payload["requested_order"]["symbol"] == "BTC-USD"


def test_order_intent_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_micro_live_pilot_order_intent_payload()

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["execution_allowed"] is False


def test_order_intent_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_micro_live_pilot_order_intent_payload()

    assert "/api/v1/micro-live-pilot-order-intent" in routes
    assert payload["execution_allowed"] is False
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["source_metadata"]["no_account_mutation"] is True


def test_order_intent_operator_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "/api/v1/micro-live-pilot-order-intent" in markup
    assert "Order Intent Evidence" in markup
    assert "Required Approvals" in markup
    assert "No order will be placed from this page" in markup
    assert "Coinbase Advanced" in markup
    assert "BTC-USD" in markup
    assert "CAD $15" in markup
