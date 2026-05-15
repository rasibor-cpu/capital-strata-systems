from __future__ import annotations

import copy
import json

import backend.app.brokers.broker_registry as broker_registry

from dashboard.runtime.api_bridge import (
    create_app,
    get_micro_live_manual_pilot_checklist_payload,
)
from dashboard.runtime.coinbase_micro_live_dry_run_probe import (
    build_coinbase_micro_live_dry_run_probe_payload,
)
from dashboard.runtime.micro_live_broker_readiness_confirmation import (
    build_micro_live_broker_readiness_confirmation_payload,
)
from dashboard.runtime.micro_live_manual_pilot_checklist import (
    CHECKLIST_ELIGIBLE_FOR_MANUAL_REVIEW,
    CHECKLIST_INCOMPLETE,
    MICRO_LIVE_MANUAL_PILOT_CHECKLIST_PAYLOAD_VERSION,
    build_micro_live_manual_pilot_checklist_payload,
)
from dashboard.runtime.micro_live_operator_approval_gate import (
    build_micro_live_operator_approval_gate_payload,
)
from dashboard.runtime.micro_live_pilot_order_intent import (
    build_micro_live_pilot_order_intent_payload,
)
from dashboard.runtime.micro_live_pre_pilot_go_no_go import (
    build_micro_live_pre_pilot_go_no_go_payload,
)
from dashboard.web.web_app import _micro_live_manual_pilot_checklist_page
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


def _checklist(**overrides) -> dict:
    payloads = {
        "pilot_readiness": _readiness(),
        "order_intent": _intent(),
        "dry_run_probe": _probe(),
        "operator_approval_gate": _approval_gate(),
        "broker_readiness_confirmation": _broker_confirmation(),
        "pre_pilot_go_no_go": _go_no_go(),
        "pcnrass_summary": {"passed": True},
    }
    payloads.update(overrides)
    return build_micro_live_manual_pilot_checklist_payload(**payloads)


def test_manual_checklist_is_review_export_only_and_eligible() -> None:
    payload = _checklist()
    missing_ids = {item["item_id"] for item in payload["missing_items"]}
    completed_ids = {item["item_id"] for item in payload["completed_items"]}

    assert payload["payload_version"] == MICRO_LIVE_MANUAL_PILOT_CHECKLIST_PAYLOAD_VERSION
    assert payload["checklist_id"].startswith("MLCHECKLIST-")
    assert payload["checklist_status"] == CHECKLIST_ELIGIBLE_FOR_MANUAL_REVIEW
    assert payload["broker"] == "Coinbase Advanced"
    assert payload["symbol"] == "BTC-USD"
    assert payload["order_type"] == "limit"
    assert payload["max_pilot_capital_cad"] == "15.00"
    assert payload["max_slippage_pct"] == "0.35"
    assert payload["max_live_orders"] == 1
    assert payload["manual_operator_approval_required"] is True
    assert payload["manual_operator_approval_recorded"] is False
    assert payload["kill_switch_confirmation_required"] is True
    assert payload["kill_switch_confirmation_recorded"] is False
    assert payload["final_pcnrass_required"] is True
    assert payload["final_pcnrass_recorded"] is False
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False
    assert "pilot_readiness_present" in completed_ids
    assert "non_executing_controls_confirmed" in completed_ids
    assert "manual_operator_approval_recorded" in missing_ids
    assert "kill_switch_confirmation_recorded" in missing_ids
    assert "final_pcnrass_recorded" in missing_ids
    assert "No trading is armed by this checklist" in payload["safety_disclaimer"]
    assert payload["evidence_chain_summary"]["pre_pilot_go_no_go"]["present"] is True
    assert payload["audit_payload"]["order_placed"] is False
    assert payload["audit_payload"]["broker_mutated"] is False


def test_manual_checklist_incomplete_when_evidence_missing() -> None:
    payload = _checklist(pre_pilot_go_no_go={})
    missing_ids = {item["item_id"] for item in payload["missing_items"]}

    assert payload["checklist_status"] == CHECKLIST_INCOMPLETE
    assert "pre_pilot_go_no_go_present" in missing_ids
    assert payload["blockers"]
    assert payload["trading_armed"] is False


def test_manual_checklist_cross_checks_scope_and_caps() -> None:
    intent = copy.deepcopy(_intent())
    intent["symbol"] = "ETH-USD"
    probe = copy.deepcopy(_probe())
    probe["max_slippage_pct"] = "0.50"

    payload = _checklist(order_intent=intent, dry_run_probe=probe)
    missing_ids = {item["item_id"] for item in payload["missing_items"]}

    assert payload["checklist_status"] == CHECKLIST_INCOMPLETE
    assert "evidence_chain_consistent" in missing_ids
    assert "capital_and_risk_caps_consistent" in missing_ids
    assert payload["order_submit_allowed"] is False


def test_manual_checklist_fails_closed_when_execution_is_enabled() -> None:
    intent = copy.deepcopy(_intent())
    probe = copy.deepcopy(_probe())
    broker_confirmation = copy.deepcopy(_broker_confirmation())
    go_no_go = copy.deepcopy(_go_no_go())
    intent["execution_allowed"] = True
    probe["order_submit_allowed"] = True
    broker_confirmation["broker_mutation_allowed"] = True
    go_no_go["trading_armed"] = True

    payload = _checklist(
        order_intent=intent,
        dry_run_probe=probe,
        broker_readiness_confirmation=broker_confirmation,
        pre_pilot_go_no_go=go_no_go,
    )
    missing_ids = {item["item_id"] for item in payload["missing_items"]}

    assert payload["checklist_status"] == CHECKLIST_INCOMPLETE
    assert "non_executing_controls_confirmed" in missing_ids
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False


def test_manual_checklist_redacts_sensitive_values() -> None:
    intent = {**_intent(), "api_key": "SHOULD_NOT_LEAK"}
    probe = {**_probe(), "note": "token=SHOULD_NOT_LEAK"}

    payload = _checklist(order_intent=intent, dry_run_probe=probe)
    encoded = json.dumps(payload, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert payload["source_metadata"]["secrets_redacted"] is True


def test_manual_checklist_does_not_call_broker_registry(monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("broker registry must not be called")

    monkeypatch.setattr(broker_registry, "get_broker_spec", fail_if_called)

    payload = _checklist()

    assert payload["source_metadata"]["no_broker_calls"] is True
    assert payload["source_metadata"]["no_order_placement"] is True
    assert payload["source_metadata"]["no_trading_arm"] is True
    assert payload["source_metadata"]["no_persistence_activation"] is True


def test_manual_checklist_api_route_is_read_only() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_micro_live_manual_pilot_checklist_payload()

    assert "/api/v1/micro-live-manual-pilot-checklist" in routes
    assert "/api/v1/micro-live-manual-pilot-approval" not in routes
    assert payload["manual_operator_approval_recorded"] is False
    assert payload["kill_switch_confirmation_recorded"] is False
    assert payload["final_pcnrass_recorded"] is False
    assert payload["trading_armed"] is False
    assert payload["execution_allowed"] is False
    assert payload["order_submit_allowed"] is False
    assert payload["broker_mutation_allowed"] is False
    assert payload["persistence_enabled"] is False


def test_manual_checklist_print_export_ui_route_renders() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_manual_pilot_checklist_page()

    assert "/micro-live-manual-pilot-checklist" in routes
    assert "CSS Manual Micro-Live Pilot Checklist" in markup
    assert "Manual Micro-Live Pilot Checklist" in markup
    assert "Checklist/export only" in markup
    assert "No approval grant" in markup
    assert "No trading is armed by this checklist" in markup
    assert "Pilot Scope" in markup
    assert "Required Items" in markup
    assert "Completed Items" in markup
    assert "Missing Items" in markup
    assert "Evidence Chain Summary" in markup
    assert "Safety Disclaimer" in markup
    assert "/api/v1/micro-live-manual-pilot-checklist" in markup
