from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


NODE_SECTIONS = (
    ("market", "Market Evidence", "market_intelligence"),
    ("risk", "Risk Evidence", "risk_command_center"),
    ("portfolio", "Portfolio Evidence", "portfolio_command"),
    ("committee", "Committee Evidence", "committee_view"),
    ("decision", "Decision Evidence", "decision_panel"),
    ("trace", "Trace Evidence", "decision_trace"),
    ("audit", "Audit Evidence", "audit"),
)


def build_evidence_graph(state: Mapping[str, Any]) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    runtime_hash = runtime.get("state_hash", DATA_UNAVAILABLE)
    runtime_id = runtime.get("runtime_id", DATA_UNAVAILABLE)
    decision = _primary_decision(state)
    nodes = [_node(state, node_id, label, section, runtime_hash, runtime_id) for node_id, label, section in NODE_SECTIONS]
    mismatches = [
        node["id"]
        for node in nodes
        if node.get("state_hash") not in {runtime_hash, DATA_UNAVAILABLE}
        or node.get("runtime_id") not in {runtime_id, DATA_UNAVAILABLE}
    ]
    return {
        "decision_id": decision.get("decision_id", "decision:latest"),
        "nodes": nodes,
        "edges": _edges(),
        "status": "FAIL_CLOSED" if mismatches else "PASS",
        "mismatches": sorted(mismatches),
        "source_consistency": {
            "runtime_id": runtime_id,
            "state_hash": runtime_hash,
            "decision_id": decision.get("decision_id", "decision:latest"),
        },
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "evidence_graph"),
    }


def _node(
    state: Mapping[str, Any],
    node_id: str,
    label: str,
    section: str,
    runtime_hash: Any,
    runtime_id: Any,
) -> dict[str, Any]:
    payload = _mapping(state.get(section))
    return {
        "id": node_id,
        "label": label,
        "section": section,
        "status": payload.get("status", payload.get("overall_risk_state", payload.get("source", DATA_UNAVAILABLE))),
        "source": payload.get("source", _mapping(state.get("runtime")).get("source", DATA_UNAVAILABLE)),
        "source_module": payload.get("source_module", f"dashboard.mission_control.{section}"),
        "runtime_id": payload.get("runtime_id", runtime_id),
        "state_hash": payload.get("state_hash", runtime_hash),
        "freshness": payload.get("freshness", DATA_UNAVAILABLE),
        "evidence": _evidence_preview(payload),
    }


def _evidence_preview(payload: Mapping[str, Any]) -> dict[str, Any]:
    preview = {}
    for key in ("status", "decision", "reason", "overall_risk_state", "connection_status", "execution_status"):
        if key in payload:
            preview[key] = payload[key]
    return preview


def _edges() -> list[dict[str, str]]:
    path = [node_id for node_id, _, _ in NODE_SECTIONS]
    return [
        {"from": source, "to": target, "relationship": "supports"}
        for source, target in zip(path, path[1:])
    ]


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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["NODE_SECTIONS", "build_evidence_graph"]
