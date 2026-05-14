from __future__ import annotations

import copy
import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_micro_live_broker_readiness_confirmation_payload,
)
from dashboard.runtime.coinbase_micro_live_dry_run_probe import (
    build_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.micro_live_broker_readiness_confirmation import (
    BROKER_CONFIRMATION_ELIGIBLE,
    BROKER_CONFIRMATION_NOT_READY,
    BROKER_CONFIRMATION_REVIEW_REQUIRED,
    MICRO_LIVE_BROKER_READINESS_CONFIRMATION_PAYLOAD_VERSION,
    build_micro_live_broker_readiness_confirmation_payload,
)
from dashboard.runtime.micro_live_operator_approval_gate import (
    build_micro_live_operator_approval_gate_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def _dashboard_payload(selected_broker: str = "coinbase") -> dict:
    return {
        "broker_summary": {
            "selected_broker": selected_broker,
            "broker_mode": "live",
            "connected": True,
            "missing_credentials": False,
            "readiness_status": "BROKER_READY",
            "account_readiness": "LIVE_READY",
        },
    }


def _valid_probe() -> dict:
    intent = build_micro_live_pilot_order_intent_payload(
        {
            "broker": "coinbase",
            "symbol": "BTC-USD",
            "asset_class": "crypto",
            "currency": "CAD",
            "capital": "15.00",
            "order_type": "limit",
            "max_live_orders": 1,
            "max_slippage_pct": "0.35",
        },
        side="BUY",
    )
    return build_coinbase_micro_live_dry_run_probe_payload(intent)


def _approval_gate() -> dict:
    return build_micro_live_operator_approval_gate_payload(
        pilot_readiness={
            "overall_status": "REVIEW_REQUIRED",
            "unrestricted_live_trading_enabled": False,
            "automatic_live_execution_enabled": False,
            "persistence_enabled": False,
        },
        dry_run_probe=_valid_probe(),
        pcnrass_summary={"passed": True},
        broker_readiness_confirmed=True,
        kill_switch_confirmed=True,
    )


def _persistence_checklist() -> dict:
    return {
        "persistence_enabled": False,
        "writes_performed": False,
    }


def test_broker_readiness_confirmation_is_non_executing_and_review_only() -> None:
    payload = build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=_dashboard_payload(),
        dry_run_probe=_valid_probe(),
        operator_approval_gate=_approval_gate(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": False},
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert (
        payload["payload_version"]
        == MICRO_LIVE_BROKER_READINESS_CONFIRMATION_PAYLOAD_VERSION
    )
    assert payload["confirmation_id"].startswith("MLBROKER-")
    assert payload["readiness_status"] == BROKER_CONFIRMATION_REVIEW_REQUIRED
    assert payload["broker"] == "Coinbase Advanced"
    assert payload["supported_symbol"] == "BTC-USD"
    assert payload["supported_order_type"] == "limit"
    assert payload["max_pilot_capital_cad"] == "15.00"
    assert payload["max_slippage_pct"] == "0.35"
    assert payload["max_live_orders"] == 1
    assert payload["broker_connection_expected"] is True
    assert payload["credential_presence_expected"] is True
    assert payload["credential_secret_exposed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert "final_pcnrass_check_passed" in failed_ids
    assert payload["audit_payload"]["order_placed"] is False
    assert payload["audit_payload"]["broker_mutated"] is False


def test_broker_readiness_confirmation_can_be_eligible_for_manual_approval() -> None:
    payload = build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=_dashboard_payload(),
        dry_run_probe=_valid_probe(),
        operator_approval_gate=_approval_gate(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
    )

    assert payload["readiness_status"] == BROKER_CONFIRMATION_ELIGIBLE
    assert payload["failed_checks"] == []
    assert payload["blockers"] == []
    assert payload["broker_mutation_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert "NO_BROKER_STATE_WAS_MODIFIED" in payload["warnings"]


def test_broker_readiness_confirmation_fails_closed_outside_pilot_scope() -> None:
    probe = copy.deepcopy(_valid_probe())
    probe["symbol"] = "ETH-USD"
    probe["order_type"] = "market"

    payload = build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=_dashboard_payload("oanda"),
        dry_run_probe=probe,
        operator_approval_gate=_approval_gate(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["readiness_status"] == BROKER_CONFIRMATION_NOT_READY
    assert "coinbase_advanced_selected" in failed_ids
    assert "btc_usd_pilot_scope" in failed_ids
    assert "limit_order_only_scope" in failed_ids
    assert payload["blockers"]
    assert payload["broker_mutation_allowed"] is False
    assert payload["order_submit_allowed"] is False


def test_broker_readiness_confirmation_requires_persistence_disabled() -> None:
    payload = build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=_dashboard_payload(),
        dry_run_probe=_valid_probe(),
        operator_approval_gate=_approval_gate(),
        persistence_checklist={
            "persistence_enabled": True,
            "writes_performed": True,
        },
        pcnrass_summary={"passed": True},
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["readiness_status"] == BROKER_CONFIRMATION_NOT_READY
    assert "persistence_disabled" in failed_ids
    assert payload["audit_payload"]["persistence_enabled"] is False


def test_broker_readiness_confirmation_redacts_sensitive_values() -> None:
    dashboard = _dashboard_payload()
    dashboard["broker_summary"]["api_key"] = "SHOULD_NOT_LEAK"
    probe = {**_valid_probe(), "note": "token=SHOULD_NOT_LEAK"}

    payload = build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=dashboard,
        dry_run_probe=probe,
        operator_approval_gate=_approval_gate(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
    )
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["credential_secret_exposed"] is True
    assert payload["broker_mutation_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert "SHOULD_NOT_LEAK" not in encoded
    assert "REDACTED" in encoded


def test_broker_readiness_confirmation_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=_dashboard_payload(),
        dry_run_probe=_valid_probe(),
        operator_approval_gate=_approval_gate(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["source_metadata"]["no_account_mutation"] is True


def test_broker_readiness_confirmation_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_micro_live_broker_readiness_confirmation_payload()

    assert "/api/v1/micro-live-broker-readiness-confirmation" in routes
    assert payload["broker_mutation_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert payload["credential_presence_expected"] is True
    assert payload["source_metadata"]["no_broker_calls"] is True


def test_broker_readiness_confirmation_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "/api/v1/micro-live-broker-readiness-confirmation" in markup
    assert "Broker Readiness Confirmation" in markup
    assert "Broker Confirmation Checks" in markup
    assert "Broker Confirmation Blockers / Warnings" in markup
    assert "No broker state was modified" in markup
