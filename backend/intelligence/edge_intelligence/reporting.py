"""DIP-004 read-only Edge Intelligence reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from backend.intelligence.edge_intelligence.models import (
    ADVISORY_FLAGS,
    EDGE_REPORT_VERSION,
    EdgeRecord,
    canonical_hash,
)


@dataclass(frozen=True)
class EdgeReportBuilder:
    edges: Sequence[EdgeRecord]
    generated_at: str

    def full_report(self) -> dict[str, Any]:
        ordered = sorted(self.edges, key=lambda e: e.edge_id)
        sections = {
            "top_edges": _rank(ordered, key=lambda e: (e.metrics.get("expectancy", 0.0), e.current_confidence), reverse=True),
            "weakest_edges": _rank(ordered, key=lambda e: (e.metrics.get("expectancy", 0.0), -e.maximum_drawdown if hasattr(e, "maximum_drawdown") else 0.0)),
            "improving_edges": _rank([e for e in ordered if e.current_drift == "REGIME_SHIFT"], key=lambda e: e.current_confidence, reverse=True),
            "decaying_edges": _rank([e for e in ordered if e.current_drift in {"DEGRADING", "DECAYING"}], key=lambda e: e.current_confidence, reverse=True),
            "stable_edges": _rank([e for e in ordered if e.current_stability_label == "STABLE"], key=lambda e: e.current_stability, reverse=True),
            "emerging_edges": _rank([e for e in ordered if e.lifecycle_state == "EVIDENCE_THRESHOLD_MET"], key=lambda e: e.current_confidence, reverse=True),
            "strategy_comparison": _category(ordered, "strategy"),
            "regime_comparison": _category(ordered, "regime"),
            "holding_time_analysis": _category(ordered, "holding_period"),
            "signal_analysis": _category(ordered, "signal"),
            "evidence_quality": _evidence_quality(ordered),
        }
        payload = {
            "report_version": EDGE_REPORT_VERSION,
            "generated_at": self.generated_at,
            "advisory_flags": dict(ADVISORY_FLAGS),
            "edge_count": len(ordered),
            "sections": sections,
        }
        payload["report_hash"] = canonical_hash(payload)
        return payload


def _edge_summary(edge: EdgeRecord) -> dict[str, Any]:
    metrics = edge.metrics
    explanation = edge.explanation
    return {
        "edge_id": edge.edge_id,
        "name": edge.name,
        "category": edge.category,
        "lifecycle_state": edge.lifecycle_state,
        "sample_size": edge.sample_size,
        "expectancy": metrics.get("expectancy"),
        "profit_factor": metrics.get("profit_factor"),
        "confidence": edge.current_confidence,
        "confidence_label": edge.current_confidence_label,
        "stability": edge.current_stability,
        "stability_label": edge.current_stability_label,
        "drift": edge.current_drift,
        "trade_references": list(edge.trade_references),
        "evidence_references": list(edge.evidence_references),
        "explanation": explanation.get("summary", ""),
        "counter_evidence": list(explanation.get("counter_evidence") or []),
        "advisory_flags": dict(edge.advisory_flags),
    }


def _rank(edges: Sequence[EdgeRecord], *, key, reverse: bool = False, limit: int = 10) -> list[dict[str, Any]]:
    return [_edge_summary(edge) for edge in sorted(edges, key=lambda e: (key(e), e.edge_id), reverse=reverse)[:limit]]


def _category(edges: Sequence[EdgeRecord], category: str) -> list[dict[str, Any]]:
    return _rank([edge for edge in edges if edge.category == category], key=lambda e: e.current_confidence, reverse=True)


def _evidence_quality(edges: Sequence[EdgeRecord]) -> dict[str, Any]:
    below = [edge.edge_id for edge in edges if edge.evidence_threshold == "BELOW_THRESHOLD"]
    observational = [edge.edge_id for edge in edges if edge.evidence_threshold == "OBSERVATIONAL_ONLY"]
    supported = [edge.edge_id for edge in edges if edge.evidence_threshold == "SUPPORTED"]
    return {
        "supported": supported,
        "observational": observational,
        "below_threshold": below,
        "total_edges": len(edges),
        "advisory_flags": dict(ADVISORY_FLAGS),
    }
