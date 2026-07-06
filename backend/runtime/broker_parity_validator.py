from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from backend.runtime.broker_readiness_framework import (
    BROKER_PARITY_COMPARABLE_FIELDS,
    broker_readiness_payload,
    build_broker_readiness_snapshot,
)
from backend.runtime.live_execution_authority import evaluate_live_execution_authority


BROKER_PARITY_BROKERS = ("COINBASE", "OANDA")


@dataclass(frozen=True)
class BrokerParityReport:
    coinbase_readiness: dict[str, Any]
    oanda_readiness: dict[str, Any]
    parity_status: str
    mismatched_fields: list[dict[str, Any]] = field(default_factory=list)
    authority_parity: bool = False
    fail_closed_parity: bool = False
    scenario_results: dict[str, Any] = field(default_factory=dict)
    comparable_fields: tuple[str, ...] = BROKER_PARITY_COMPARABLE_FIELDS
    advisory_only: bool = True
    execution_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["comparable_fields"] = list(self.comparable_fields)
        return payload


def validate_broker_parity(
    coinbase_readiness: Mapping[str, Any] | None = None,
    oanda_readiness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    coinbase = _readiness_payload("COINBASE", "CRYPTO", coinbase_readiness)
    oanda = _readiness_payload("OANDA", "FX", oanda_readiness)
    mismatched_fields = _mismatched_fields(coinbase, oanda)
    scenarios = _scenario_results()
    authority_parity = all(bool(result["authority_parity"]) for result in scenarios.values())
    fail_closed_parity = all(bool(result["fail_closed_parity"]) for result in scenarios.values())
    parity_status = "PASS" if not mismatched_fields and authority_parity and fail_closed_parity else "REVIEW"
    return BrokerParityReport(
        coinbase_readiness=coinbase,
        oanda_readiness=oanda,
        parity_status=parity_status,
        mismatched_fields=mismatched_fields,
        authority_parity=authority_parity,
        fail_closed_parity=fail_closed_parity,
        scenario_results=scenarios,
    ).as_dict()


def broker_parity_payload(
    broker_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary = broker_summary if isinstance(broker_summary, Mapping) else {}
    parity = summary.get("broker_parity") if isinstance(summary.get("broker_parity"), Mapping) else None
    if parity:
        report = dict(parity)
    else:
        readiness = summary.get("broker_readiness") if isinstance(summary.get("broker_readiness"), Mapping) else {}
        selected = str(summary.get("selected_broker", readiness.get("broker_name", "NONE")) or "NONE").upper()
        coinbase = readiness if selected == "COINBASE" else None
        oanda = readiness if selected == "OANDA" else None
        report = validate_broker_parity(coinbase, oanda)
    report["advisory_only"] = True
    report["execution_allowed"] = False
    return report


def _readiness_payload(
    broker_name: str,
    broker_type: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = dict(payload) if isinstance(payload, Mapping) else {}
    source.setdefault("broker_name", broker_name)
    source.setdefault("broker_type", broker_type)
    source.setdefault("mode", "live")
    source.setdefault("execution_supported", True)
    source.setdefault("execution_enabled", False)
    return broker_readiness_payload(build_broker_readiness_snapshot(source))


def _mismatched_fields(
    coinbase: Mapping[str, Any],
    oanda: Mapping[str, Any],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for field_name in BROKER_PARITY_COMPARABLE_FIELDS:
        coinbase_value = coinbase.get(field_name)
        oanda_value = oanda.get(field_name)
        if coinbase_value != oanda_value:
            mismatches.append(
                {
                    "field": field_name,
                    "coinbase": coinbase_value,
                    "oanda": oanda_value,
                }
            )
    return mismatches


def _scenario_results() -> dict[str, Any]:
    scenarios = {
        "missing_credentials": (_missing_credentials_snapshot, "ARMED"),
        "authentication_failed": (_authentication_failed_snapshot, "ARMED"),
        "broker_execution_disabled": (_execution_disabled_snapshot, "ARMED"),
        "pilot_disarmed": (_pilot_disarmed_snapshot, "DISARMED"),
    }
    return {name: _evaluate_scenario(factory, pilot_state=pilot_state) for name, (factory, pilot_state) in scenarios.items()}


def _evaluate_scenario(factory: Any, *, pilot_state: str) -> dict[str, Any]:
    coinbase_evidence = _authority_evidence(factory("COINBASE", "CRYPTO"), pilot_state=pilot_state)
    oanda_evidence = _authority_evidence(factory("OANDA", "FX"), pilot_state=pilot_state)
    coinbase = evaluate_live_execution_authority(coinbase_evidence).as_dict()
    oanda = evaluate_live_execution_authority(oanda_evidence).as_dict()
    authority_fields = ("execution_authority", "can_live_execute", "live_authority_state", "authority_reason", "failed_conditions")
    authority_parity = all(coinbase.get(field) == oanda.get(field) for field in authority_fields)
    fail_closed = (
        coinbase.get("execution_authority") is False
        and oanda.get("execution_authority") is False
        and coinbase.get("can_live_execute") is False
        and oanda.get("can_live_execute") is False
    )
    return {
        "authority_parity": authority_parity,
        "fail_closed_parity": fail_closed,
        "coinbase_authority": coinbase,
        "oanda_authority": oanda,
    }


def _authority_evidence(readiness: Mapping[str, Any], *, pilot_state: str) -> dict[str, Any]:
    return {
        "broker_readiness": dict(readiness),
        "operator_requested_live": True,
        "live_micro_pilot_state": pilot_state,
        "capital_governor": "PASS",
        "unified_trade_gate": "PASS",
        "margin_gate": "PASS",
        "anti_bleed_guard": "PASS",
        "rbac": "PASS",
        "kill_switch": "CLEAR",
        "go_no_go": "GO",
    }


def _missing_credentials_snapshot(broker_name: str, broker_type: str) -> dict[str, Any]:
    return _readiness_payload(
        broker_name,
        broker_type,
        {
            "credential_status": "MISSING",
            "credentials_health": "MISSING",
            "authentication_health": "NOT_TESTED",
            "connection_health": "NOT_CONNECTED",
            "market_data_health": "NOT_TESTED",
            "account_data_health": "UNAVAILABLE",
            "authority_block_reason": "Credentials Missing",
        },
    )


def _authentication_failed_snapshot(broker_name: str, broker_type: str) -> dict[str, Any]:
    return _readiness_payload(
        broker_name,
        broker_type,
        {
            "credential_status": "PRESENT",
            "credentials_health": "READY",
            "authenticated": False,
            "connected": False,
            "authentication_health": "FAILED",
            "connection_health": "NOT_CONNECTED",
            "authority_block_reason": "Authentication Not Verified",
        },
    )


def _execution_disabled_snapshot(broker_name: str, broker_type: str) -> dict[str, Any]:
    return _ready_snapshot(broker_name, broker_type, execution_enabled=False)


def _pilot_disarmed_snapshot(broker_name: str, broker_type: str) -> dict[str, Any]:
    snapshot = _ready_snapshot(broker_name, broker_type, execution_enabled=True)
    return snapshot


def _ready_snapshot(
    broker_name: str,
    broker_type: str,
    *,
    execution_enabled: bool,
) -> dict[str, Any]:
    return _readiness_payload(
        broker_name,
        broker_type,
        {
            "credential_status": "PRESENT",
            "authenticated": True,
            "connected": True,
            "account_loaded": True,
            "market_data_ready": True,
            "products_loaded": 2,
            "broker_health": "HEALTHY",
            "infrastructure_health": "HEALTHY",
            "credentials_health": "READY",
            "authentication_health": "AUTHENTICATED",
            "connection_health": "CONNECTED",
            "market_data_health": "READY",
            "account_data_health": "READY",
            "execution_supported": True,
            "execution_enabled": execution_enabled,
            "authority_block_reason": "Broker Execution Disabled" if not execution_enabled else "Pilot Disarmed",
        },
    )


__all__ = [
    "BROKER_PARITY_BROKERS",
    "BrokerParityReport",
    "broker_parity_payload",
    "validate_broker_parity",
]
