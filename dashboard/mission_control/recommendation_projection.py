from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


FORBIDDEN_RECOMMENDATION_TERMS = ("BUY", "SELL", "EXECUTE", "SUBMIT", "CANCEL", "ORDER")


def build_recommendation_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    decision = _primary_decision(state)
    broker = _mapping(state.get("broker_telemetry"))
    recommendations = _recommendations_for(state, decision, broker)
    return {
        "decision_id": decision.get("decision_id", "decision:latest"),
        "decision": decision.get("decision", "UNKNOWN"),
        "recommendations": recommendations,
        "operational_recommendations": recommendations,
        "forbidden_terms_absent": _forbidden_terms_absent(recommendations),
        "execution_controls": "DISABLED_READ_ONLY",
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "recommendation_projection"),
    }


def _recommendations_for(state: Mapping[str, Any], decision: Mapping[str, Any], broker: Mapping[str, Any]) -> list[dict[str, Any]]:
    if _runtime_unavailable(state):
        return [
            _recommendation("No action", "Runtime evidence is unavailable."),
            _recommendation("Increase evidence", "Wait for canonical runtime state before interpreting decision quality."),
        ]

    decision_text = str(decision.get("decision", "UNKNOWN")).upper()
    recommendations: list[dict[str, Any]] = []
    if decision_text in {"BLOCKED", "REJECTED", "UNKNOWN"}:
        recommendations.append(_recommendation("Increase evidence", str(decision.get("reason", "Decision evidence is incomplete."))))
    elif decision_text in {"WATCH", "DEFERRED"}:
        recommendations.append(_recommendation("Continue monitoring", str(decision.get("reason", "Decision remains watch-only."))))
        recommendations.append(_recommendation("Wait for confirmation", "Do not alter execution posture from Mission Control."))
    elif decision_text == "APPROVED":
        recommendations.append(_recommendation("Continue monitoring", "Approval evidence is advisory and does not authorize trading."))
    else:
        recommendations.append(_recommendation("No action", "Decision state is not recognized."))

    broker_statuses = {
        str(broker.get("connection_status", "")).upper(),
        str(broker.get("authentication", broker.get("authentication_status", ""))).upper(),
        str(broker.get("market_data", broker.get("market_data_status", ""))).upper(),
    }
    if any(status and status not in {"PASS", "GREEN", "AVAILABLE", "OK"} for status in broker_statuses):
        recommendations.append(_recommendation("Await broker recovery", "Broker evidence is not fully passing."))
    return recommendations


def _recommendation(action: str, reason: str) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "authority": "ADVISORY_ONLY",
        "changes_execution": False,
    }


def _forbidden_terms_absent(recommendations: list[dict[str, Any]]) -> bool:
    text = " ".join(str(item.get("action", "")) for item in recommendations).upper()
    return not any(term in text for term in FORBIDDEN_RECOMMENDATION_TERMS)


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


__all__ = ["FORBIDDEN_RECOMMENDATION_TERMS", "build_recommendation_panel"]
