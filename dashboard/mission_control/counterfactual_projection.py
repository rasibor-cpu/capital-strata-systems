from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_counterfactual_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    decision = _primary_decision(state)
    counterfactuals = _counterfactuals_for(state, decision)
    return {
        "decision_id": decision.get("decision_id", "decision:latest"),
        "decision": decision.get("decision", "UNKNOWN"),
        "counterfactuals": counterfactuals,
        "non_executable": True,
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "counterfactual_projection"),
    }


def _counterfactuals_for(state: Mapping[str, Any], decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    if _runtime_unavailable(state):
        return [_counterfactual("Runtime available", "Canonical runtime state becomes available.", "runtime")]

    items: list[dict[str, Any]] = []
    confidence = decision.get("confidence")
    threshold = decision.get("confidence_threshold")
    try:
        if confidence != DATA_UNAVAILABLE and threshold != DATA_UNAVAILABLE and float(confidence) < float(threshold):
            items.append(_counterfactual(f"confidence > {threshold}", "Decision confidence clears the observed threshold.", "decision_panel"))
    except (TypeError, ValueError):
        items.append(_counterfactual("confidence evidence valid", "Confidence evidence is numeric and comparable.", "decision_panel"))

    risk = _mapping(state.get("risk"))
    risk_state = str(risk.get("overall_risk_state", risk.get("risk_status", ""))).upper()
    if risk_state and risk_state not in {"GREEN", "PASS", "NORMAL", "AVAILABLE"}:
        items.append(_counterfactual("risk state improves", "Risk projection returns to a passing state.", "risk_command_center"))

    broker = _mapping(state.get("broker_telemetry"))
    broker_state = str(broker.get("connection_status", broker.get("broker_health", ""))).upper()
    if broker_state and broker_state not in {"GREEN", "PASS", "AVAILABLE", "OK"}:
        items.append(_counterfactual("broker readiness improves", "Broker telemetry returns passing connectivity evidence.", "broker_telemetry"))

    market = _mapping(state.get("market_intelligence"))
    volatility = str(market.get("volatility_state", "")).upper()
    if "HIGH" in volatility:
        items.append(_counterfactual("volatility normalizes", "Market volatility evidence moves out of high-volatility status.", "market_intelligence"))

    portfolio = _mapping(state.get("portfolio"))
    if portfolio.get("equity") == DATA_UNAVAILABLE:
        items.append(_counterfactual("portfolio evidence available", "Portfolio equity and cash evidence become available.", "portfolio"))

    if not items:
        items.append(_counterfactual("No counterfactual threshold evidence available", "Observed state does not expose a failing numeric threshold.", "decision_panel"))
    return items


def _counterfactual(condition: str, rationale: str, source_section: str) -> dict[str, Any]:
    return {
        "condition": condition,
        "rationale": rationale,
        "source_section": source_section,
        "changes_execution": False,
        "authority": "ADVISORY_ONLY",
    }


def _primary_decision(state: Mapping[str, Any]) -> dict[str, Any]:
    panel = _mapping(state.get("decision_panel"))
    decisions = panel.get("decisions")
    if isinstance(decisions, list) and decisions and isinstance(decisions[0], Mapping):
        return dict(decisions[0])
    return {"decision_id": "decision:latest", "decision": "UNKNOWN", "reason": DATA_UNAVAILABLE}


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_counterfactual_projection"]
