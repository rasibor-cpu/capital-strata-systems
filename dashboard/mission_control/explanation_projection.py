from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_decision_explanation(state: Mapping[str, Any]) -> dict[str, Any]:
    decision = _primary_decision(state)
    trace = _mapping(state.get("decision_trace"))
    stages = trace.get("stages") if isinstance(trace.get("stages"), list) else []
    blocker = _first_blocker(stages)
    missing = _missing_evidence(stages)
    reason = decision.get("reason", DATA_UNAVAILABLE)
    decision_text = str(decision.get("decision", "UNKNOWN")).upper()
    if decision_text == "UNKNOWN" and _runtime_unavailable(state):
        plain = "Runtime unavailable. No synthetic explanation was generated."
    elif decision_text == "APPROVED":
        plain = f"Decision approved because available evidence passed the observed decision chain. Primary reason: {reason}."
    elif decision_text in {"BLOCKED", "REJECTED"}:
        plain = f"Decision refused because {blocker.get('stage', 'a subsystem')} reported {blocker.get('status', reason)}."
    elif decision_text == "WATCH":
        plain = f"Decision remains watch-only while evidence develops. Primary reason: {reason}."
    else:
        plain = f"Decision is {decision_text}. Primary reason: {reason}."
    return {
        "decision_id": decision.get("decision_id", "decision:latest"),
        "decision": decision_text,
        "plain_language": plain,
        "why_approved": plain if decision_text == "APPROVED" else DATA_UNAVAILABLE,
        "why_rejected": plain if decision_text in {"BLOCKED", "REJECTED"} else DATA_UNAVAILABLE,
        "primary_reason": reason,
        "secondary_reason": blocker.get("reason", DATA_UNAVAILABLE),
        "supporting_evidence": [stage.get("evidence", {}) for stage in stages if isinstance(stage, Mapping)],
        "blocking_subsystem": blocker.get("stage", DATA_UNAVAILABLE),
        "blocking_rule": blocker.get("reason", DATA_UNAVAILABLE),
        "missing_evidence": missing,
        "required_improvement": _required_improvement(decision, blocker, missing),
        "read_only": True,
        **_metadata(state, "explanation_projection"),
    }


def _required_improvement(decision: Mapping[str, Any], blocker: Mapping[str, Any], missing: list[str]) -> str:
    if missing:
        return "Increase evidence"
    threshold = decision.get("confidence_threshold")
    confidence = decision.get("confidence")
    try:
        if threshold != DATA_UNAVAILABLE and confidence != DATA_UNAVAILABLE and float(confidence) < float(threshold):
            return f"confidence > {threshold}"
    except (TypeError, ValueError):
        pass
    if blocker:
        return f"{blocker.get('stage', 'blocking subsystem')} status improves"
    return DATA_UNAVAILABLE


def _first_blocker(stages: list[Any]) -> dict[str, Any]:
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        status = str(stage.get("status", "")).upper()
        if any(token in status for token in ("FAIL", "BLOCK", "RED", "REJECT", "UNAVAILABLE")):
            return dict(stage)
    return {}


def _missing_evidence(stages: list[Any]) -> list[str]:
    missing: list[str] = []
    for stage in stages:
        if isinstance(stage, Mapping) and stage.get("status") in {DATA_UNAVAILABLE, "UNAVAILABLE", "NOT EVALUATED"}:
            missing.append(str(stage.get("stage", "UNKNOWN")))
    return missing


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
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_decision_explanation"]
