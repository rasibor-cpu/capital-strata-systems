from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dashboard.runtime.frontend_contract import DATA_UNAVAILABLE


def build_opportunity_ranking(state: Mapping[str, Any]) -> dict[str, Any]:
    source = _institutional_source(state, "opportunity_intelligence")
    options = _mapping(state.get("options_income"))
    decisions = _decision_rows(state)
    raw_rows = _rows(source, "opportunities", "ranked_opportunities", fallback=options.get("opportunities", [])) or decisions
    opportunities = [_opportunity(state, item, index) for index, item in enumerate(raw_rows, start=1)]
    opportunities.sort(key=lambda item: (-_number(item.get("confidence")), -_number(item.get("expected_quality")), str(item.get("symbol"))))
    for index, item in enumerate(opportunities, start=1):
        item["ranking"] = index
    return {
        "status": "FAIL_CLOSED" if _runtime_unavailable(state) else "AVAILABLE" if opportunities else "UNAVAILABLE",
        "opportunities": opportunities,
        "opportunity_count": len(opportunities),
        "links": _links("market_intelligence", "trade_operations", "audit_explainability"),
        "read_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "advisory_only": True,
        **_metadata(state, "opportunity_ranking"),
    }


def _opportunity(state: Mapping[str, Any], item: Any, rank: int) -> dict[str, Any]:
    payload = _mapping(item)
    if not payload:
        payload = {"symbol": str(item)}
    committee = _committee_outcome(state)
    return {
        "symbol": payload.get("symbol", payload.get("instrument", DATA_UNAVAILABLE)),
        "asset_class": payload.get("asset_class", DATA_UNAVAILABLE),
        "confidence": payload.get("confidence", payload.get("decision_confidence", DATA_UNAVAILABLE)),
        "expected_quality": payload.get("expected_quality", payload.get("quality_score", payload.get("score", DATA_UNAVAILABLE))),
        "risk": payload.get("risk", payload.get("risk_score", DATA_UNAVAILABLE)),
        "blocking_reason": payload.get("blocking_reason", payload.get("reason", DATA_UNAVAILABLE)),
        "committee_outcome": payload.get("committee_outcome", committee),
        "ranking": payload.get("ranking", payload.get("rank", rank)),
        "technical_intelligence": _technical_intelligence_observability(payload),
        "external_event_intelligence": _external_event_observability(payload),
        **_metadata(state, "opportunity_ranking.opportunity"),
    }


def _technical_intelligence_observability(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = payload.get("technical_intelligence")
    if not isinstance(source, Mapping):
        diagnostics = _mapping(payload.get("diagnostics"))
        intelligence = _mapping(diagnostics.get("intelligence"))
        source = intelligence.get("technical_intelligence")
    source = source if isinstance(source, Mapping) else {}
    supporting = _mapping(_mapping(payload.get("explainability")).get("supporting_indicators"))
    timeframes = source.get("timeframes") if isinstance(source.get("timeframes"), Mapping) else {}
    snapshot_fields = [
        _mapping(item)
        for item in timeframes.values()
        if isinstance(item, Mapping)
    ]
    freshness = next((item.get("freshness") for item in snapshot_fields if item.get("freshness") not in {None, ""}), DATA_UNAVAILABLE)
    data_quality = next((item.get("data_quality") for item in snapshot_fields if item.get("data_quality") not in {None, ""}), DATA_UNAVAILABLE)
    regime = next((item.get("regime") for item in snapshot_fields if item.get("regime") not in {None, ""}), DATA_UNAVAILABLE)
    contributions = DATA_UNAVAILABLE
    for item in snapshot_fields:
        value = item.get("component_contributions")
        if value not in (None, [], ()):
            contributions = value
            break
    insufficient = False
    if "insufficient_data" in source:
        insufficient = bool(source.get("insufficient_data"))
    elif snapshot_fields:
        insufficient = all(bool(item.get("insufficient_data")) for item in snapshot_fields)
    return {
        "schema_version": source.get("schema_version", "css.tai001.technical_intelligence.v1"),
        "directional_score": source.get("directional_score", supporting.get("technical_score", DATA_UNAVAILABLE)),
        "confidence": source.get("confidence", supporting.get("technical_confidence", DATA_UNAVAILABLE)),
        "dominant_direction": source.get("dominant_direction", supporting.get("technical_direction", DATA_UNAVAILABLE)),
        "agreement": source.get("agreement", DATA_UNAVAILABLE),
        "conflict_indicators": list(source.get("conflict_indicators") or []),
        "higher_timeframe_confirmation": source.get(
            "higher_timeframe_confirmation",
            supporting.get("technical_higher_timeframe_confirmation", DATA_UNAVAILABLE),
        ),
        "freshness": source.get("freshness", freshness),
        "data_quality": source.get("data_quality", data_quality),
        "insufficient_data": source.get("insufficient_data", insufficient if snapshot_fields or source else DATA_UNAVAILABLE),
        "regime": source.get("regime", regime),
        "evidence_reasons": list(source.get("evidence_reasons") or []),
        "component_contributions": source.get("component_contributions", contributions),
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "read_only": True,
        "execution_authority": "NONE",
    }


def _external_event_observability(payload: Mapping[str, Any]) -> dict[str, Any]:
    source = payload.get("external_event_intelligence")
    if not isinstance(source, Mapping):
        diagnostics = _mapping(payload.get("diagnostics"))
        intelligence = _mapping(diagnostics.get("intelligence"))
        source = intelligence.get("external_event_intelligence")
    source = source if isinstance(source, Mapping) else {}
    return {
        "schema_version": source.get("schema_version", "css.mi_ext_001.external_event_intelligence.v1"),
        "external_event_score": source.get("external_event_score", 0.0),
        "event_confidence": source.get("event_confidence", 0.0),
        "event_freshness": source.get("event_freshness", DATA_UNAVAILABLE),
        "event_categories": list(source.get("event_categories") or []),
        "event_provenance_count": source.get("event_provenance_count", 0),
        "event_conflict_state": source.get("event_conflict_state", "NONE"),
        "event_reasons": list(source.get("event_reasons") or []),
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "direct_execution_influence": False,
        "live_network_ingestion": False,
        "read_only": True,
        "execution_authority": "NONE",
    }


def _decision_rows(state: Mapping[str, Any]) -> list[Any]:
    panel = _mapping(state.get("decision_panel"))
    rows = panel.get("decisions")
    return rows if isinstance(rows, list) else []


def _committee_outcome(state: Mapping[str, Any]) -> str:
    committee = _mapping(state.get("committee_view"))
    rows = committee.get("committees")
    if isinstance(rows, list):
        failures = [row for row in rows if isinstance(row, Mapping) and row.get("outcome") == "FAIL"]
        warnings = [row for row in rows if isinstance(row, Mapping) and row.get("outcome") == "WARNING"]
        if failures:
            return "FAIL"
        if warnings:
            return "WARNING"
        if rows:
            return "PASS"
    return DATA_UNAVAILABLE


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return -1.0


def _institutional_source(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    sources = _mapping(state.get("institutional_sources"))
    return _mapping(sources.get(key))


def _rows(source: Mapping[str, Any], *keys: str, fallback: Any = None) -> list[Any]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return value
    return fallback if isinstance(fallback, list) else []


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


__all__ = ["build_opportunity_ranking"]
