from __future__ import annotations

import copy
import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_micro_live_pre_pilot_go_no_go_payload,
)
from dashboard.runtime.coinbase_micro_live_dry_run_probe import (
    build_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.micro_live_broker_readiness_confirmation import (
    build_micro_live_broker_readiness_confirmation_payload,
)
from dashboard.runtime.micro_live_operator_approval_gate import (
    build_micro_live_operator_approval_gate_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.runtime.micro_live_pre_pilot_go_no_go import (
    GO_NO_GO_ELIGIBLE,
    GO_NO_GO_NO_GO,
    GO_NO_GO_REVIEW_REQUIRED,
    MICRO_LIVE_PRE_PILOT_GO_NO_GO_PAYLOAD_VERSION,
    build_micro_live_pre_pilot_go_no_go_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


def _dashboard_payload() -> dict:
    return {
        "broker_summary": {
            "selected_broker": "coinbase",
            "broker_mode": "live",
            "connected": True,
            "missing_credentials": False,
            "readiness_status": "BROKER_READY",
            "account_readiness": "LIVE_READY",
        },
    }


def _readiness() -> dict:
    return {
        "overall_status": "REVIEW_REQUIRED",
        "unrestricted_live_trading_enabled": False,
        "automatic_live_execution_enabled": False,
        "persistence_enabled": False,
    }


def _intent() -> dict:
    return build_micro_live_pilot_order_intent_payload(
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


def _probe() -> dict:
    return build_coinbase_micro_live_dry_run_probe_payload(_intent())


def _approval_gate(
    *,
    kill_switch_confirmed: bool = True,
    broker_readiness_confirmed: bool = True,
) -> dict:
    return build_micro_live_operator_approval_gate_payload(
        pilot_readiness=_readiness(),
        dry_run_probe=_probe(),
        pcnrass_summary={"passed": True},
        broker_readiness_confirmed=broker_readiness_confirmed,
        kill_switch_confirmed=kill_switch_confirmed,
    )


def _broker_confirmation(*, pcnrass_passed: bool = True) -> dict:
    return build_micro_live_broker_readiness_confirmation_payload(
        dashboard_payload=_dashboard_payload(),
        dry_run_probe=_probe(),
        operator_approval_gate=_approval_gate(),
        persistence_checklist={
            "persistence_enabled": False,
            "writes_performed": False,
        },
        pcnrass_summary={"passed": pcnrass_passed},
    )


def _go_no_go(**overrides) -> dict:
    payloads = {
        "pilot_readiness": _readiness(),
        "order_intent": _intent(),
        "dry_run_probe": _probe(),
        "operator_approval_gate": _approval_gate(),
        "broker_readiness_confirmation": _broker_confirmation(),
        "pcnrass_summary": {"passed": True},
    }
    payloads.update(overrides)
    return build_micro_live_pre_pilot_go_no_go_payload(**payloads)


def test_go_no_go_record_is_review_only_and_eligible_when_evidence_aligns() -> None:
    payload = _go_no_go()

    assert payload["payload_version"] == MICRO_LIVE_PRE_PILOT_GO_NO_GO_PAYLOAD_VERSION
    assert payload["record_id"].startswith("MLGONOGO-")
    assert payload["go_no_go_status"] == GO_NO_GO_ELIGIBLE
    assert payload["broker"] == "Coinbase Advanced"
    assert payload["symbol"] == "BTC-USD"
    assert payload["order_type"] == "limit"
    assert payload["max_pilot_capital_cad"] == "15.00"
    assert payload["max_slippage_pct"] == "0.35"
    assert payload["max_live_orders"] == 1
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False
    assert payload["final_pcnrass_required"] is True
    assert payload["manual_operator_approval_required"] is True
    assert payload["kill_switch_confirmation_required"] is True
    assert payload["failed_checks"] == []
    assert payload["audit_payload"]["order_placed"] is False
    assert payload["audit_payload"]["broker_mutated"] is False


def test_go_no_go_record_requires_final_pcnrass() -> None:
    payload = _go_no_go(
        broker_readiness_confirmation=_broker_confirmation(pcnrass_passed=False),
        pcnrass_summary={"passed": False},
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["go_no_go_status"] == GO_NO_GO_NO_GO
    assert "broker_readiness_confirmation_eligible" in failed_ids
    assert "final_pcnrass_passed" in failed_ids
    assert payload["trading_armed"] is False


def test_go_no_go_record_requires_kill_switch_confirmation() -> None:
    payload = _go_no_go(
        operator_approval_gate=_approval_gate(kill_switch_confirmed=False),
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["go_no_go_status"] == GO_NO_GO_REVIEW_REQUIRED
    assert "kill_switch_pre_pilot_confirmation_present" in failed_ids
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False


def test_go_no_go_record_fails_closed_on_inconsistent_scope() -> None:
    intent = copy.deepcopy(_intent())
    probe = copy.deepcopy(_probe())
    intent["symbol"] = "ETH-USD"
    probe["order_type"] = "market"
    probe["validation_status"] = "FAIL"

    payload = _go_no_go(order_intent=intent, dry_run_probe=probe)
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["go_no_go_status"] == GO_NO_GO_NO_GO
    assert "dry_run_probe_passed" in failed_ids
    assert "scope_consistent" in failed_ids
    assert payload["blockers"]
    assert payload["execution_allowed"] is False


def test_go_no_go_record_fails_closed_when_execution_is_enabled() -> None:
    intent = copy.deepcopy(_intent())
    probe = copy.deepcopy(_probe())
    broker_confirmation = copy.deepcopy(_broker_confirmation())
    intent["execution_allowed"] = True
    probe["order_submit_allowed"] = True
    broker_confirmation["broker_mutation_allowed"] = True

    payload = _go_no_go(
        order_intent=intent,
        dry_run_probe=probe,
        broker_readiness_confirmation=broker_confirmation,
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["go_no_go_status"] == GO_NO_GO_NO_GO
    assert "order_intent_non_executing" in failed_ids
    assert "dry_run_probe_non_executing" in failed_ids
    assert "broker_confirmation_non_executing" in failed_ids
    assert payload["trading_armed"] is False


def test_go_no_go_record_redacts_sensitive_values() -> None:
    intent = {**_intent(), "api_key": "SHOULD_NOT_LEAK"}
    probe = {**_probe(), "note": "token=SHOULD_NOT_LEAK"}

    payload = _go_no_go(order_intent=intent, dry_run_probe=probe)
    encoded = json.dumps(payload, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert payload["broker_mutation_allowed"] is False
    assert payload["order_submit_allowed"] is False


def test_go_no_go_record_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = _go_no_go()

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["source_metadata"]["no_trading_arm"] is True


def test_go_no_go_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_micro_live_pre_pilot_go_no_go_payload()

    assert "/api/v1/micro-live-pre-pilot-go-no-go" in routes
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False


def test_go_no_go_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "/api/v1/micro-live-pre-pilot-go-no-go" in markup
    assert "Final Pre-Pilot Go/No-Go" in markup
    assert "Go/No-Go Checks" in markup
    assert "Go/No-Go Blockers / Warnings" in markup
    assert "No trading is armed from this page" in markup
