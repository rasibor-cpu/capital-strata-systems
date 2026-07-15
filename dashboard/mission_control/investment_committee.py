from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_investment_committee_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    source = _institutional_source(state, "investment_committee")
    decisions = _decision_rows(state)
    opportunities = _rows(_mapping(state.get("opportunity_ranking")), "opportunities")
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else source.get("status", "AVAILABLE" if decisions or opportunities else "UNAVAILABLE"),
        "current_decisions": source.get("current_decisions", decisions),
        "highest_ranked_ideas": source.get("highest_ranked_ideas", opportunities[:5]),
        "blocked_ideas": source.get("blocked_ideas", [row for row in opportunities if str(row.get("committee_outcome", "")).upper() == "FAIL"]),
        "capital_recommendations": source.get("capital_recommendations", []),
        "decision_quality": source.get("decision_quality", _mapping(state.get("decision_panel")).get("status", DATA_UNAVAILABLE)),
        "confidence_distribution": source.get("confidence_distribution", _confidence_distribution(decisions)),
        "links": _links("trade_operations", "audit_explainability", "portfolio"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "investment_committee"),
    }


def _confidence_distribution(decisions: list[Mapping[str, Any]]) -> dict[str, int]:
    buckets = {"low": 0, "medium": 0, "high": 0, "unavailable": 0}
    for row in decisions:
        try:
            confidence = float(row.get("confidence"))
        except (TypeError, ValueError):
            buckets["unavailable"] += 1
            continue
        if confidence >= 0.75:
            buckets["high"] += 1
        elif confidence >= 0.5:
            buckets["medium"] += 1
        else:
            buckets["low"] += 1
    return buckets


def _decision_rows(state: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _mapping(state.get("decision_panel")).get("decisions")
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _institutional_source(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    sources = _mapping(state.get("institutional_sources"))
    return _mapping(sources.get(key))


def _rows(source: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
    return []


def _links(*keys: str) -> list[dict[str, str]]:
    return [{"label": key.replace("_", " ").title(), "route": f"/mission-control/{key.replace('_', '-')}"} for key in keys]


def _metadata(state: Mapping[str, Any], source_module: str) -> dict[str, Any]:
    runtime = _mapping(state.get("runtime"))
    snapshot = _mapping(state.get("runtime_snapshot"))
    freshness = _mapping(state.get("freshness"))
    decision = _mapping(state.get("decision_panel"))
    return {
        "source": runtime.get("source", snapshot.get("source", DATA_UNAVAILABLE)),
        "source_module": f"dashboard.mission_control.{source_module}",
        "provenance": snapshot.get("provenance", {}),
        "generated_at": state.get("generated_at", DATA_UNAVAILABLE),
        "freshness": freshness.get("overall_freshness", DATA_UNAVAILABLE),
        "runtime_id": runtime.get("runtime_id", snapshot.get("runtime_id", DATA_UNAVAILABLE)),
        "state_hash": runtime.get("state_hash", snapshot.get("state_hash", DATA_UNAVAILABLE)),
        "decision_hash": decision.get("state_hash", DATA_UNAVAILABLE),
    }


def _runtime_unavailable(state: Mapping[str, Any]) -> bool:
    runtime = _mapping(state.get("runtime"))
    return str(runtime.get("runtime_status", "")).upper() in {"OFFLINE", "UNAVAILABLE"} or str(runtime.get("source", "")).upper() in {"", "UNAVAILABLE", "UNKNOWN"}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["build_investment_committee_panel"]
