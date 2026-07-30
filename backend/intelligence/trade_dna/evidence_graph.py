"""DIP-002 Evidence Graph — every analytical conclusion cites DNA evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class EvidenceGraphNode:
    """Traceable evidence package required for any DIP analytical conclusion."""

    trade_ids: tuple[str, ...]
    dna_ids: tuple[str, ...] = ()
    evidence_version: str = EVIDENCE_VERSION
    analysis_version: str = ANALYSIS_VERSION
    sample_size: int = 0
    confidence: float = 0.0
    generated_at: str = field(default_factory=_utc_now_iso)
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceGraphError(ValueError):
    """Raised when an evidence graph node is incomplete or invalid."""


def build_evidence_graph(
    *,
    trade_ids: Sequence[str],
    dna_ids: Sequence[str] | None = None,
    evidence_version: str = EVIDENCE_VERSION,
    analysis_version: str = ANALYSIS_VERSION,
    sample_size: Optional[int] = None,
    confidence: float,
    generated_at: Optional[str] = None,
    notes: Optional[str] = None,
) -> EvidenceGraphNode:
    """Construct a validated evidence graph node.

    No recommendation or analytical claim may omit trade_ids / versions /
    sample_size / confidence / generation timestamp.
    """
    cleaned_trades = tuple(str(t) for t in trade_ids if str(t).strip())
    if not cleaned_trades:
        raise EvidenceGraphError("evidence_requires_trade_ids")

    cleaned_dna = tuple(str(d) for d in (dna_ids or ()) if str(d).strip())
    size = int(sample_size) if sample_size is not None else len(cleaned_trades)
    if size < 1:
        raise EvidenceGraphError("evidence_sample_size_invalid")

    try:
        conf = float(confidence)
    except (TypeError, ValueError) as exc:
        raise EvidenceGraphError("evidence_confidence_invalid") from exc
    if conf != conf or conf < 0.0 or conf > 1.0:
        raise EvidenceGraphError("evidence_confidence_out_of_range")

    if not evidence_version:
        raise EvidenceGraphError("evidence_version_required")
    if not analysis_version:
        raise EvidenceGraphError("analysis_version_required")

    ts = generated_at or _utc_now_iso()
    if not ts:
        raise EvidenceGraphError("generated_at_required")

    return EvidenceGraphNode(
        trade_ids=cleaned_trades,
        dna_ids=cleaned_dna,
        evidence_version=evidence_version,
        analysis_version=analysis_version,
        sample_size=size,
        confidence=conf,
        generated_at=ts,
        notes=notes,
    )
