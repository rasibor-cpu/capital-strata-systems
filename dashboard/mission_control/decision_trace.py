from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


TRACE_STAGES = (
    "Market Regime",
    "Signal Engine",
    "Portfolio Constraints",
    "Risk Committee",
    "AntiBleedGuard",
    "Trade Gate",
    "Final Decision",
)


def build_decision_trace(state: Mapping[str, Any]) -> dict[str, Any]:
    decision = _primary_decision(state)
    audit = _mapping(state.get("audit"))
    evidence = _mapping(audit.get("audit_evidence"))
    raw_trace = evidence.get("decision_trace")
    stages = [_stage_from_mapping(state, item) for item in raw_trace] if isinstance(raw_trace, list) else _default_stages(state, decision)
    return {
        "decision_id": decision.get("decision_id", "decision:latest"),
        "status": decision.get("decision", "UNKNOWN"),
        "stages": stages,
        "read_only": True,
        **_metadata(state, "decision_trace"),
    }


def _default_stages(state: Mapping[str, Any], decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    market = _mapping(state.get("market_intelligence"))
    risk = _mapping(state.get("risk"))
    portfolio = _mapping(state.get("portfolio"))
    trading = _mapping(state.get("trading"))
    return [
        _stage(state, "Market Regime", market.get("market_regime"), DATA_UNAVAILABLE, "Market regime evidence", market),
        _stage(state, "Signal Engine", decision.get("decision"), decision.get("decision_score"), decision.get("reason"), {"probability": decision.get("probability")}),
        _stage(state, "Portfolio Constraints", "PASS" if portfolio.get("equity") != DATA_UNAVAILABLE else "NOT EVALUATED", DATA_UNAVAILABLE, "Portfolio availability evidence", portfolio),
        _stage(state, "Risk Committee", risk.get("overall_risk_state"), risk.get("risk_score"), risk.get("trade_gate_status"), risk),
        _stage(state, "AntiBleedGuard", risk.get("anti_bleed_guard"), DATA_UNAVAILABLE, "AntiBleedGuard status", risk),
        _stage(state, "Trade Gate", trading.get("execution_status"), DATA_UNAVAILABLE, trading.get("last_execution_event", DATA_UNAVAILABLE), trading),
        _stage(state, "Final Decision", decision.get("decision"), decision.get("confidence"), decision.get("reason"), decision),
    ]


def _stage_from_mapping(state: Mapping[str, Any], item: Any) -> dict[str, Any]:
    data = _mapping(item)
    return _stage(
        state,
        data.get("stage", DATA_UNAVAILABLE),
        data.get("status", DATA_UNAVAILABLE),
        data.get("score", DATA_UNAVAILABLE),
        data.get("reason", DATA_UNAVAILABLE),
        data.get("evidence", {}),
    )


def _stage(state: Mapping[str, Any], stage: Any, status: Any, score: Any, reason: Any, evidence: Any) -> dict[str, Any]:
    return {
        "stage": stage or DATA_UNAVAILABLE,
        "status": status if status not in (None, "") else DATA_UNAVAILABLE,
        "score": score if score not in (None, "") else DATA_UNAVAILABLE,
        "reason": reason if reason not in (None, "") else DATA_UNAVAILABLE,
        "evidence": evidence if isinstance(evidence, Mapping) else {},
        **_metadata(state, "decision_trace.stage"),
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


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


__all__ = ["TRACE_STAGES", "build_decision_trace"]
