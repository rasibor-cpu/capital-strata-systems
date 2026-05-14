from __future__ import annotations

import copy
import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_micro_live_operator_approval_gate_payload,
)
from dashboard.runtime.coinbase_micro_live_dry_run_probe import (
    build_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.micro_live_operator_approval_gate import (
    APPROVAL_GATE_ELIGIBLE,
    APPROVAL_GATE_NOT_READY,
    APPROVAL_GATE_REVIEW_REQUIRED,
    MICRO_LIVE_OPERATOR_APPROVAL_GATE_PAYLOAD_VERSION,
    build_micro_live_operator_approval_gate_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.web.web_app import _micro_live_pilot_readiness_page
from dashboard.web.web_app import create_app as create_web_app


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


def _readiness() -> dict:
    return {
        "overall_status": "REVIEW_REQUIRED",
        "unrestricted_live_trading_enabled": False,
        "automatic_live_execution_enabled": False,
        "persistence_enabled": False,
    }


def test_operator_approval_gate_defaults_to_review_only() -> None:
    payload = build_micro_live_operator_approval_gate_payload(
        pilot_readiness=_readiness(),
        dry_run_probe=_valid_probe(),
        pcnrass_summary={"passed": True},
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert (
        payload["payload_version"]
        == MICRO_LIVE_OPERATOR_APPROVAL_GATE_PAYLOAD_VERSION
    )
    assert payload["approval_gate_id"].startswith("MLAPPROVAL-")
    assert payload["readiness_status"] == APPROVAL_GATE_REVIEW_REQUIRED
    assert payload["operator_approval_required"] is True
    assert payload["operator_approval_granted"] is False
    assert payload["approval_grant_endpoint_exists"] is False
    assert payload["trading_armed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["requires_final_pcnrass_check"] is True
    assert payload["requires_kill_switch_verification"] is True
    assert payload["requires_broker_readiness_confirmation"] is True
    assert "kill_switch_pre_pilot_confirmation_present" in failed_ids
    assert "broker_readiness_confirmation_present" in failed_ids
    assert payload["audit_payload"]["order_placed"] is False
    assert payload["audit_payload"]["broker_mutated"] is False


def test_operator_approval_gate_can_be_eligible_for_manual_approval_only() -> None:
    payload = build_micro_live_operator_approval_gate_payload(
        pilot_readiness=_readiness(),
        dry_run_probe=_valid_probe(),
        pcnrass_summary={"passed": True},
        broker_readiness_confirmed=True,
        kill_switch_confirmed=True,
    )

    assert payload["readiness_status"] == APPROVAL_GATE_ELIGIBLE
    assert payload["failed_checks"] == []
    assert payload["blockers"] == []
    assert payload["operator_approval_granted"] is False
    assert payload["trading_armed"] is False
    assert "MANUAL_APPROVAL_STILL_REQUIRED_NO_TRADING_ARMED" in payload["warnings"]


def test_operator_approval_gate_fails_closed_for_executing_probe() -> None:
    probe = copy.deepcopy(_valid_probe())
    probe["order_submit_allowed"] = True
    probe["broker_mutation_allowed"] = True

    payload = build_micro_live_operator_approval_gate_payload(
        pilot_readiness=_readiness(),
        dry_run_probe=probe,
        pcnrass_summary={"passed": True},
        broker_readiness_confirmed=True,
        kill_switch_confirmed=True,
    )
    failed_ids = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["readiness_status"] == APPROVAL_GATE_NOT_READY
    assert "dry_run_probe_non_executing" in failed_ids
    assert payload["blockers"]
    assert payload["operator_approval_granted"] is False
    assert payload["trading_armed"] is False


def test_operator_approval_gate_tracks_kill_switch_evidence() -> None:
    payload = build_micro_live_operator_approval_gate_payload(
        pilot_readiness=_readiness(),
        dry_run_probe=_valid_probe(),
        pcnrass_summary={"passed": True},
        kill_switch_controls={"global_live_order_kill_switch": "engaged"},
    )
    evidence = payload["kill_switch_evidence"]

    assert evidence["kill_switch_reference_available"] is True
    assert evidence["verification_required"] is True
    assert evidence["pre_pilot_confirmation_present"] is False
    assert evidence["kill_switch_bypassed"] is False
    assert evidence["activation_performed"] is False
    assert evidence["current_decision"]["blocked"] is True
    assert evidence["live_order_path_blocked_without_confirmation"] is True


def test_operator_approval_gate_redacts_sensitive_values() -> None:
    readiness = {**_readiness(), "api_key": "SHOULD_NOT_LEAK"}
    probe = {**_valid_probe(), "note": "token=SHOULD_NOT_LEAK"}

    payload = build_micro_live_operator_approval_gate_payload(
        pilot_readiness=readiness,
        dry_run_probe=probe,
        pcnrass_summary={"passed": True},
    )
    encoded = json.dumps(payload, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert payload["broker_mutation_allowed"] is False


def test_operator_approval_gate_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = build_micro_live_operator_approval_gate_payload(
        pilot_readiness=_readiness(),
        dry_run_probe=_valid_probe(),
        pcnrass_summary={"passed": True},
    )

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["source_metadata"]["no_trading_arm"] is True


def test_operator_approval_gate_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_micro_live_operator_approval_gate_payload()

    assert "/api/v1/micro-live-operator-approval-gate" in routes
    assert "/api/v1/micro-live-operator-approval-grant" not in routes
    assert payload["operator_approval_granted"] is False
    assert payload["approval_grant_endpoint_exists"] is False
    assert payload["trading_armed"] is False
    assert payload["broker_mutation_allowed"] is False


def test_operator_approval_gate_ui_rendering() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()

    assert "/micro-live-pilot-readiness" in routes
    assert "/api/v1/micro-live-operator-approval-gate" in markup
    assert "Operator Approval Gate" in markup
    assert "Kill-Switch Verification Evidence" in markup
    assert "Approval Gate Blockers / Warnings" in markup
    assert "Manual approval still required; no trading is armed" in markup
