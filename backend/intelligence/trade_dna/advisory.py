"""DIP-002 Layer 3 — advisory conclusions (never become facts)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from backend.common.advisory_payload import AdvisoryPayloadBuilder
from backend.intelligence.trade_dna.constants import ADVISORY_VERSION, LAYER_ADVISORY
from backend.intelligence.trade_dna.evidence_graph import EvidenceGraphError, EvidenceGraphNode


@dataclass(frozen=True)
class AdvisoryConclusion:
    """Recommendation-only payload bound to an Evidence Graph node.

    Never stored inside Trade DNA fact records.
    """

    recommendation_id: str
    kind: str
    summary: str
    evidence: EvidenceGraphNode
    confidence_score: float
    opportunity_ranking: Optional[float] = None
    advisory_version: str = ADVISORY_VERSION
    layer: str = LAYER_ADVISORY
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Enforce advisory safety lock on every serialization.
        return AdvisoryPayloadBuilder.lock(
            {
                **payload,
                "recommendation_kind": self.kind,
                "capital_movement": False,
            },
            force_live_block=True,
        )


def build_advisory_conclusion(
    *,
    recommendation_id: str,
    kind: str,
    summary: str,
    evidence: EvidenceGraphNode,
    confidence_score: float,
    opportunity_ranking: Optional[float] = None,
    details: Optional[dict[str, Any]] = None,
) -> AdvisoryConclusion:
    if not recommendation_id:
        raise EvidenceGraphError("advisory_requires_recommendation_id")
    if not kind:
        raise EvidenceGraphError("advisory_requires_kind")
    if not summary:
        raise EvidenceGraphError("advisory_requires_summary")
    if evidence is None:
        raise EvidenceGraphError("advisory_requires_evidence")
    if not evidence.trade_ids:
        raise EvidenceGraphError("advisory_evidence_missing_trade_ids")
    return AdvisoryConclusion(
        recommendation_id=recommendation_id,
        kind=kind,
        summary=summary,
        evidence=evidence,
        confidence_score=float(confidence_score),
        opportunity_ranking=opportunity_ranking,
        details=dict(details or {}),
    )
