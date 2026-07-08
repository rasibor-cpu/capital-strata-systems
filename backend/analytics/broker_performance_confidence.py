from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .broker_performance_intelligence import BrokerPerformanceIntelligenceEngine
from .decision_confidence_framework import DecisionConfidenceFramework


def build_broker_performance_confidence_report(
    dashboard_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(dashboard_payload) if isinstance(dashboard_payload, Mapping) else {}
    broker = _mapping(payload.get("broker_summary"))
    risk = _mapping(payload.get("risk_summary"))
    execution = _mapping(payload.get("execution_summary"))
    account = _mapping(payload.get("account_summary"))
    session = _mapping(payload.get("session"))

    operational_status = _selected_operational_status(payload, broker)
    diagnostics = _broker_diagnostics(broker)
    readiness = _mapping(broker.get("broker_readiness"))
    performance = BrokerPerformanceIntelligenceEngine().score_broker(
        broker,
        execution_metrics=execution,
        operational_status=operational_status,
        credential_diagnostics=diagnostics,
        broker_readiness=readiness,
    )
    confidence = DecisionConfidenceFramework().evaluate_confidence(
        broker_readiness=readiness,
        broker_diagnostics=diagnostics,
        broker_performance=performance,
        runtime_health={
            "engine_mode": payload.get("engine_mode", session.get("engine_mode", "SAFE")),
            "resolved_mode": payload.get("resolved_mode", session.get("resolved_mode", "paper")),
        },
        trade_gate_context={
            "gate_status": risk.get("gate_status", "OPEN"),
            "risk_state": risk.get("risk_state", "NORMAL"),
            "unified_trade_gate": _mapping(payload.get("governance_summary")).get("unified_trade_gate_active", True),
        },
        account_context=account,
        live_readiness_constraints={
            "can_live_execute": broker.get("can_live_execute", False),
            "execution_authority": broker.get("execution_authority", False),
            "go_no_go": broker.get("go_no_go", "NO GO"),
            "live_authority_state": broker.get("live_authority_state", "BLOCKED"),
        },
        requested_mode=str(broker.get("broker_mode", payload.get("resolved_mode", "paper"))),
    )
    return {
        "broker_performance_intelligence": performance,
        "decision_confidence": confidence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_enabled": False,
    }


def _selected_operational_status(payload: Mapping[str, Any], broker: Mapping[str, Any]) -> dict[str, Any]:
    selected_broker = str(broker.get("selected_broker", broker.get("broker", "UNKNOWN")) or "UNKNOWN").upper()
    explicit = _mapping(payload.get("broker_operational_status"))
    if explicit:
        selected = _mapping(explicit.get("selected"))
        if selected:
            return selected
        by_name = _mapping(explicit.get(selected_broker.lower()))
        if by_name:
            return by_name
    nested = _mapping(broker.get("broker_operational_status"))
    if nested:
        selected = _mapping(nested.get("selected"))
        if selected:
            return selected
        by_name = _mapping(nested.get(selected_broker.lower()))
        if by_name:
            return by_name
        return nested
    validation_key = "oanda_live_validation" if selected_broker == "OANDA" else "coinbase_live_validation"
    validation = _mapping(broker.get(validation_key, payload.get(validation_key)))
    validation_status = _mapping(_mapping(validation.get("broker_validation")).get("broker_operational_status"))
    if validation_status:
        return validation_status
    supported_assets = broker.get("supported_assets")
    product_count = len(supported_assets) if isinstance(supported_assets, list) else 0
    connected = bool(broker.get("connected") or broker.get("broker_connected"))
    api_health = str(broker.get("api_health", broker.get("broker_health", "UNKNOWN")) or "UNKNOWN").upper()
    account_readiness = str(broker.get("account_readiness", "UNKNOWN") or "UNKNOWN").upper()
    return {
        "broker": selected_broker,
        "operational_state": "OPERATIONAL" if connected and api_health in {"OK", "READY", "HEALTHY"} else "PENDING",
        "latency_ms": broker.get("latency_ms"),
        "market_data_status": "OK" if product_count > 0 else "PENDING",
        "balance_status": "AVAILABLE" if account_readiness in {"OK", "READY", "AVAILABLE"} else "NOT_AVAILABLE",
        "account_sync_status": "OK" if account_readiness in {"OK", "READY", "AVAILABLE"} else "PENDING",
        "product_count": product_count,
        "failure_reason": "NONE",
    }


def _broker_diagnostics(broker: Mapping[str, Any]) -> dict[str, Any]:
    direct = _mapping(broker.get("broker_credential_diagnostics"))
    if direct:
        return direct
    credential_diagnostics = _mapping(broker.get("credential_diagnostics"))
    nested = _mapping(credential_diagnostics.get("broker_credential_diagnostics"))
    if nested:
        return nested
    return credential_diagnostics


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_broker_performance_confidence_report"]
