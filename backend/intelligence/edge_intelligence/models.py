"""DIP-004 Edge Intelligence data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping, Sequence

from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION
from backend.intelligence.trade_dna.hashing import compute_content_hash


EDGE_ANALYSIS_VERSION = "css.edge_intelligence.analysis.v1"
EDGE_REGISTRY_VERSION = "css.edge_intelligence.registry.v1"
EDGE_REPORT_VERSION = "css.edge_intelligence.report.v1"

ADVISORY_FLAGS = {
    "advisory_only": True,
    "execution_allowed": False,
    "capital_movement_allowed": False,
    "broker_action_allowed": False,
    "risk_limit_action_allowed": False,
    "trade_authorization_allowed": False,
    "runtime_control_allowed": False,
    "live_execution_allowed": False,
    "recommendations": False,
    "optimization": False,
}

LIFECYCLE_DISCOVERED = "DISCOVERED"
LIFECYCLE_UNDER_OBSERVATION = "UNDER_OBSERVATION"
LIFECYCLE_EVIDENCE_THRESHOLD_MET = "EVIDENCE_THRESHOLD_MET"
LIFECYCLE_STABLE = "STABLE"
LIFECYCLE_DRIFTING = "DRIFTING"
LIFECYCLE_DECAYING = "DECAYING"
LIFECYCLE_ARCHIVED = "ARCHIVED"


def canonical_hash(payload: Mapping[str, Any]) -> str:
    return compute_content_hash(dict(payload))


@dataclass(frozen=True)
class EdgeDefinition:
    """Immutable semantic definition of an edge.

    This object owns identity. It never contains transient metrics,
    confidence, stability, drift, evidence references, or trade populations.
    """

    category: str
    name: str
    description: str
    cohort_key: str
    cohort_definition: dict[str, Any]
    normalized_predicates: dict[str, Any]
    definition_version: str = "css.edge_definition.v1"
    parent_definition_hash: str | None = None

    @property
    def definition_hash(self) -> str:
        payload = {
            "category": _normalize_scalar(self.category),
            "cohort_key": _normalize_scalar(self.cohort_key),
            "cohort_definition": _normalize_payload(self.cohort_definition),
            "normalized_predicates": _normalize_payload(self.normalized_predicates),
            "definition_version": self.definition_version,
            "parent_definition_hash": self.parent_definition_hash or "",
        }
        return f"edge-definition:{canonical_hash(payload)}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["definition_hash"] = self.definition_hash
        payload["cohort_definition"] = _normalize_payload(self.cohort_definition)
        payload["normalized_predicates"] = _normalize_payload(self.normalized_predicates)
        return payload


@dataclass(frozen=True)
class EdgeCandidate:
    definition: EdgeDefinition
    trade_ids: tuple[str, ...]
    dna_ids: tuple[str, ...]

    @property
    def category(self) -> str:
        return self.definition.category

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def cohort_key(self) -> str:
        return self.definition.cohort_key

    @property
    def cohort_definition(self) -> dict[str, Any]:
        return dict(self.definition.cohort_definition)

    @property
    def definition_hash(self) -> str:
        return self.definition.definition_hash

    @property
    def signature(self) -> str:
        return self.definition_hash

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signature"] = self.signature
        payload["definition_hash"] = self.definition_hash
        payload["trade_ids"] = list(self.trade_ids)
        payload["dna_ids"] = list(self.dna_ids)
        return payload


@dataclass(frozen=True)
class EdgeExplanation:
    summary: str
    why_detected: str
    metric_drivers: tuple[dict[str, Any], ...]
    confidence_breakdown: dict[str, float]
    stability_breakdown: dict[str, Any]
    drift_breakdown: dict[str, Any]
    threshold_results: dict[str, Any]
    supporting_trade_ids: tuple[str, ...]
    supporting_dna_ids: tuple[str, ...]
    counter_evidence: tuple[dict[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["metric_drivers"] = list(self.metric_drivers)
        payload["supporting_trade_ids"] = list(self.supporting_trade_ids)
        payload["supporting_dna_ids"] = list(self.supporting_dna_ids)
        payload["counter_evidence"] = list(self.counter_evidence)
        payload["limitations"] = list(self.limitations)
        return payload


@dataclass(frozen=True)
class EdgeEvaluation:
    sample_size: int
    independent_observations: int
    win_rate: float
    loss_rate: float
    profit_factor: float
    expectancy: float
    median_return: float
    average_return: float
    maximum_drawdown: float
    average_holding_seconds: float
    median_holding_seconds: float
    confidence_score: float
    confidence_label: str
    stability_score: float
    stability_label: str
    persistence_score: float
    drift_score: float
    drift_state: str
    evidence_threshold: str
    lifecycle_state: str
    metrics_hash: str
    edge_fingerprint: str
    analysis_version: str
    evidence_version: str
    explanation: EdgeExplanation

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["explanation"] = self.explanation.to_dict()
        return payload


@dataclass(frozen=True)
class EdgeRecord:
    edge_id: str
    permanent_edge_id: str
    signature: str
    definition_hash: str
    definition: dict[str, Any]
    edge_fingerprint: str
    name: str
    category: str
    description: str
    lifecycle_state: str
    created_at: str
    last_recalculated: str
    analysis_version: str = ANALYSIS_VERSION
    evidence_version: str = EVIDENCE_VERSION
    edge_analysis_version: str = EDGE_ANALYSIS_VERSION
    registry_version: str = EDGE_REGISTRY_VERSION
    current_confidence: float = 0.0
    current_confidence_label: str = "LOW"
    current_stability: float = 0.0
    current_stability_label: str = "INSUFFICIENT_HISTORY"
    current_drift: str = "INSUFFICIENT_RECENT_EVIDENCE"
    evidence_threshold: str = "BELOW_THRESHOLD"
    sample_size: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    historical_versions: tuple[dict[str, Any], ...] = ()
    parent_edge_ids: tuple[str, ...] = ()
    child_edge_ids: tuple[str, ...] = ()
    supporting_edges: tuple[str, ...] = ()
    conflicting_edges: tuple[str, ...] = ()
    independent_edges: tuple[str, ...] = ()
    trade_references: tuple[str, ...] = ()
    evidence_references: tuple[str, ...] = ()
    explanation_references: tuple[str, ...] = ()
    explanation: dict[str, Any] = field(default_factory=dict)
    advisory_flags: dict[str, bool] = field(default_factory=lambda: dict(ADVISORY_FLAGS))
    content_hash: str = ""

    def with_hash(self) -> "EdgeRecord":
        payload = self.to_dict(include_hash=False)
        return replace(self, content_hash=canonical_hash(payload))

    def snapshot(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "definition_hash": self.definition_hash,
            "edge_fingerprint": self.edge_fingerprint,
            "analysis_version": self.analysis_version,
            "evidence_version": self.evidence_version,
            "last_recalculated": self.last_recalculated,
            "lifecycle_state": self.lifecycle_state,
            "current_confidence": self.current_confidence,
            "current_stability": self.current_stability,
            "current_drift": self.current_drift,
            "evidence_threshold": self.evidence_threshold,
            "sample_size": self.sample_size,
            "expectancy": self.metrics.get("expectancy"),
            "profit_factor": self.metrics.get("profit_factor"),
            "win_rate": self.metrics.get("win_rate"),
            "average_return": self.metrics.get("average_return"),
            "median_return": self.metrics.get("median_return"),
            "persistence": self.metrics.get("persistence_score"),
            "evidence_references": list(self.evidence_references),
        }

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["historical_versions"] = list(self.historical_versions)
        payload["parent_edge_ids"] = list(self.parent_edge_ids)
        payload["child_edge_ids"] = list(self.child_edge_ids)
        payload["supporting_edges"] = list(self.supporting_edges)
        payload["conflicting_edges"] = list(self.conflicting_edges)
        payload["independent_edges"] = list(self.independent_edges)
        payload["trade_references"] = list(self.trade_references)
        payload["evidence_references"] = list(self.evidence_references)
        payload["explanation_references"] = list(self.explanation_references)
        if not include_hash:
            payload["content_hash"] = ""
        return payload


def edge_record_from_dict(payload: Mapping[str, Any]) -> EdgeRecord:
    return EdgeRecord(
        edge_id=str(payload["edge_id"]),
        permanent_edge_id=str(payload.get("permanent_edge_id") or payload["edge_id"]),
        signature=str(payload["signature"]),
        definition_hash=str(payload.get("definition_hash") or payload["signature"]),
        definition=dict(payload.get("definition") or {}),
        edge_fingerprint=str(payload.get("edge_fingerprint") or payload.get("metrics", {}).get("metrics_hash") or ""),
        name=str(payload.get("name") or ""),
        category=str(payload.get("category") or ""),
        description=str(payload.get("description") or ""),
        lifecycle_state=str(payload.get("lifecycle_state") or LIFECYCLE_DISCOVERED),
        created_at=str(payload.get("created_at") or ""),
        last_recalculated=str(payload.get("last_recalculated") or ""),
        analysis_version=str(payload.get("analysis_version") or ANALYSIS_VERSION),
        evidence_version=str(payload.get("evidence_version") or EVIDENCE_VERSION),
        edge_analysis_version=str(payload.get("edge_analysis_version") or EDGE_ANALYSIS_VERSION),
        registry_version=str(payload.get("registry_version") or EDGE_REGISTRY_VERSION),
        current_confidence=float(payload.get("current_confidence") or 0.0),
        current_confidence_label=str(payload.get("current_confidence_label") or "LOW"),
        current_stability=float(payload.get("current_stability") or 0.0),
        current_stability_label=str(payload.get("current_stability_label") or "INSUFFICIENT_HISTORY"),
        current_drift=str(payload.get("current_drift") or "INSUFFICIENT_RECENT_EVIDENCE"),
        evidence_threshold=str(payload.get("evidence_threshold") or "BELOW_THRESHOLD"),
        sample_size=int(payload.get("sample_size") or 0),
        metrics=dict(payload.get("metrics") or {}),
        historical_versions=tuple(dict(v) for v in payload.get("historical_versions") or ()),
        parent_edge_ids=_string_tuple(payload.get("parent_edge_ids")),
        child_edge_ids=_string_tuple(payload.get("child_edge_ids")),
        supporting_edges=_string_tuple(payload.get("supporting_edges")),
        conflicting_edges=_string_tuple(payload.get("conflicting_edges")),
        independent_edges=_string_tuple(payload.get("independent_edges")),
        trade_references=_string_tuple(payload.get("trade_references")),
        evidence_references=_string_tuple(payload.get("evidence_references")),
        explanation_references=_string_tuple(payload.get("explanation_references")),
        explanation=dict(payload.get("explanation") or {}),
        advisory_flags={**ADVISORY_FLAGS, **dict(payload.get("advisory_flags") or {})},
        content_hash=str(payload.get("content_hash") or ""),
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_payload(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_normalize_payload(item) for item in value]
    return _normalize_scalar(value)


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().upper()
    return value
