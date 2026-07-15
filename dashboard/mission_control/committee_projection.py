from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


COMMITTEES = (
    "Investment Committee",
    "Risk Committee",
    "Execution Committee",
    "Capital Committee",
    "Compliance",
    "Broker Committee",
)
VALID_OUTCOMES = {"PASS", "FAIL", "WARNING", "NOT EVALUATED"}


def build_committee_view(state: Mapping[str, Any]) -> dict[str, Any]:
    raw = _raw_committees(state)
    committees = []
    contradictions: list[str] = []
    for name in COMMITTEES:
        outcome = _committee_outcome(raw, name)
        if outcome not in VALID_OUTCOMES:
            contradictions.append(name)
            outcome = "FAIL"
        committees.append(
            {
                "committee": name,
                "outcome": outcome,
                "reason": _committee_reason(raw, name),
                **_metadata(state, "committee_projection.committee"),
            }
        )
    return {
        "status": "FAIL_CLOSED" if contradictions else "PASS",
        "committees": committees,
        "contradictions": contradictions,
        "read_only": True,
        **_metadata(state, "committee_projection"),
    }


def _raw_committees(state: Mapping[str, Any]) -> Mapping[str, Any]:
    audit = _mapping(state.get("audit"))
    evidence = _mapping(audit.get("audit_evidence"))
    if isinstance(evidence.get("committees"), Mapping):
        return evidence["committees"]
    explainability = _mapping(state.get("explainability"))
    if isinstance(explainability.get("committees"), Mapping):
        return explainability["committees"]
    return {}


def _committee_outcome(raw: Mapping[str, Any], name: str) -> str:
    value = raw.get(name, raw.get(name.lower().replace(" ", "_")))
    if isinstance(value, Mapping):
        value = value.get("outcome", value.get("status", value.get("decision")))
    text = str(value or "NOT EVALUATED").upper().replace("_", " ")
    if text in {"APPROVED", "ALLOW", "GREEN"}:
        return "PASS"
    if text in {"BLOCKED", "REJECTED", "RED"}:
        return "FAIL"
    if text in {"WARN", "AMBER"}:
        return "WARNING"
    if text in VALID_OUTCOMES:
        return text
    return text


def _committee_reason(raw: Mapping[str, Any], name: str) -> str:
    value = raw.get(name, raw.get(name.lower().replace(" ", "_")))
    if isinstance(value, Mapping):
        return str(value.get("reason", DATA_UNAVAILABLE))
    return DATA_UNAVAILABLE


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


__all__ = ["COMMITTEES", "VALID_OUTCOMES", "build_committee_view"]
