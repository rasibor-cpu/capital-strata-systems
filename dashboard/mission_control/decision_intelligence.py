from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


ALLOWED_DECISIONS = {"APPROVED", "BLOCKED", "WATCH", "DEFERRED", "REJECTED", "UNKNOWN"}


def build_decision_panel(state: Mapping[str, Any]) -> dict[str, Any]:
    if _runtime_unavailable(state):
        return {
            "status": "UNKNOWN",
            "decisions": [_decision(state, decision="UNKNOWN", reason="Runtime unavailable")],
            "reason": "Runtime unavailable",
            "read_only": True,
            **_metadata(state, "decision_intelligence"),
        }

    raw_decisions = _raw_decisions(state)
    decisions = [_decision(state, **item) for item in raw_decisions] if raw_decisions else [_fallback_decision(state)]
    return {
        "status": decisions[0]["decision"] if decisions else "UNKNOWN",
        "decisions": decisions,
        "reason": decisions[0].get("reason", DATA_UNAVAILABLE) if decisions else DATA_UNAVAILABLE,
        "read_only": True,
        **_metadata(state, "decision_intelligence"),
    }


def _raw_decisions(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    audit = _mapping(state.get("audit"))
    evidence = _mapping(audit.get("audit_evidence"))
    for key in ("decisions", "decision_panel", "evaluated_opportunities", "opportunities"):
        value = evidence.get(key)
        if isinstance(value, list):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _fallback_decision(state: Mapping[str, Any]) -> dict[str, Any]:
    trading = _mapping(state.get("trading"))
    status = str(trading.get("execution_status", DATA_UNAVAILABLE)).upper()
    decision = "BLOCKED" if "BLOCK" in status or "REJECT" in status else "WATCH" if status not in {DATA_UNAVAILABLE, "UNKNOWN"} else "UNKNOWN"
    return _decision(
        state,
        decision=decision,
        reason=trading.get("last_execution_event") or status or DATA_UNAVAILABLE,
        quality_score=trading.get("execution_quality", DATA_UNAVAILABLE),
    )


def _decision(state: Mapping[str, Any], **payload: Any) -> dict[str, Any]:
    decision = str(payload.get("decision") or payload.get("status") or "UNKNOWN").upper()
    if decision not in ALLOWED_DECISIONS:
        decision = "UNKNOWN"
    return {
        "decision_id": str(payload.get("decision_id") or payload.get("id") or "decision:latest"),
        "symbol": payload.get("symbol", DATA_UNAVAILABLE),
        "asset_class": payload.get("asset_class", DATA_UNAVAILABLE),
        "decision": decision,
        "confidence": payload.get("confidence", DATA_UNAVAILABLE),
        "confidence_threshold": payload.get("confidence_threshold", payload.get("threshold", DATA_UNAVAILABLE)),
        "decision_score": payload.get("decision_score", payload.get("score", DATA_UNAVAILABLE)),
        "probability": payload.get("probability", DATA_UNAVAILABLE),
        "quality_score": payload.get("quality_score", DATA_UNAVAILABLE),
        "reason": payload.get("reason", DATA_UNAVAILABLE),
        "generated_timestamp": payload.get("generated_at", payload.get("timestamp", state.get("generated_at", DATA_UNAVAILABLE))),
        **_metadata(state, "decision_intelligence.decision"),
    }


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


__all__ = ["ALLOWED_DECISIONS", "build_decision_panel"]
