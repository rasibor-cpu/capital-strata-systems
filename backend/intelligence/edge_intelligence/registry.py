"""DIP-004 persistent Edge Registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from backend.intelligence.edge_intelligence.evaluation import EdgeEvaluator
from backend.intelligence.edge_intelligence.models import (
    ADVISORY_FLAGS,
    EDGE_ANALYSIS_VERSION,
    EDGE_REGISTRY_VERSION,
    EdgeCandidate,
    EdgeRecord,
    canonical_hash,
    edge_record_from_dict,
)
from backend.intelligence.trade_dna.constants import ANALYSIS_VERSION, EVIDENCE_VERSION


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class EdgeRegistry:
    """Append-aware registry with permanent edge IDs."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._records_by_id: dict[str, EdgeRecord] = {}
        self._ids_by_signature: dict[str, str] = {}
        if self.path is not None and self.path.exists():
            self._load()

    def list_edges(self) -> tuple[EdgeRecord, ...]:
        return tuple(self._records_by_id[key] for key in sorted(self._records_by_id))

    def get(self, edge_id: str) -> EdgeRecord | None:
        return self._records_by_id.get(edge_id)

    def get_by_signature(self, signature: str) -> EdgeRecord | None:
        edge_id = self._ids_by_signature.get(signature)
        return self._records_by_id.get(edge_id) if edge_id else None

    def upsert_candidates(
        self,
        *,
        candidates: Sequence[EdgeCandidate],
        evaluator: EdgeEvaluator,
        recalculated_at: str,
    ) -> tuple[EdgeRecord, ...]:
        updated = []
        for candidate in sorted(candidates, key=lambda c: c.definition_hash):
            evaluation = evaluator.evaluate(candidate)
            existing = self.get_by_signature(candidate.definition_hash)
            if existing is None:
                edge_id = self._next_edge_id()
                created_at = recalculated_at
                history: tuple[dict[str, Any], ...] = ()
            else:
                edge_id = existing.edge_id
                created_at = existing.created_at
                history = existing.historical_versions
                previous = existing.snapshot()
                if (
                    existing.edge_fingerprint
                    and existing.edge_fingerprint != evaluation.edge_fingerprint
                    and previous not in history
                ):
                    history = tuple(sorted((*history, previous), key=lambda row: str(row.get("last_recalculated") or "")))
            record = EdgeRecord(
                edge_id=edge_id,
                permanent_edge_id=edge_id,
                signature=candidate.definition_hash,
                definition_hash=candidate.definition_hash,
                definition=candidate.definition.to_dict(),
                edge_fingerprint=evaluation.edge_fingerprint,
                name=candidate.name,
                category=candidate.category,
                description=candidate.description,
                lifecycle_state=evaluation.lifecycle_state,
                created_at=created_at,
                last_recalculated=recalculated_at,
                analysis_version=evaluation.analysis_version,
                evidence_version=evaluation.evidence_version,
                edge_analysis_version=EDGE_ANALYSIS_VERSION,
                registry_version=EDGE_REGISTRY_VERSION,
                current_confidence=evaluation.confidence_score,
                current_confidence_label=evaluation.confidence_label,
                current_stability=evaluation.stability_score,
                current_stability_label=evaluation.stability_label,
                current_drift=evaluation.drift_state,
                evidence_threshold=evaluation.evidence_threshold,
                sample_size=evaluation.sample_size,
                metrics=evaluation.to_dict(),
                historical_versions=history,
                parent_edge_ids=existing.parent_edge_ids if existing else (),
                child_edge_ids=existing.child_edge_ids if existing else (),
                supporting_edges=existing.supporting_edges if existing else (),
                conflicting_edges=existing.conflicting_edges if existing else (),
                independent_edges=existing.independent_edges if existing else (),
                trade_references=candidate.trade_ids,
                evidence_references=candidate.dna_ids,
                explanation_references=(evaluation.metrics_hash,),
                explanation=evaluation.explanation.to_dict(),
                advisory_flags=dict(ADVISORY_FLAGS),
            ).with_hash()
            self._records_by_id[edge_id] = record
            self._ids_by_signature[candidate.definition_hash] = edge_id
            updated.append(record)
        self._persist()
        return tuple(updated)

    def link_edges(
        self,
        *,
        edge_id: str,
        parent_edge_ids: Sequence[str] = (),
        child_edge_ids: Sequence[str] = (),
        supporting_edges: Sequence[str] = (),
        conflicting_edges: Sequence[str] = (),
        independent_edges: Sequence[str] = (),
    ) -> EdgeRecord:
        existing = self._records_by_id[edge_id]
        parents = self._relationship_ids(edge_id, parent_edge_ids, "parent")
        children = self._relationship_ids(edge_id, child_edge_ids, "child")
        supporting = self._relationship_ids(edge_id, supporting_edges, "support")
        conflicting = self._relationship_ids(edge_id, conflicting_edges, "conflict")
        independent = self._relationship_ids(edge_id, independent_edges, "independent", allow_self=False)
        payload = existing.to_dict(include_hash=False)
        payload.update(
            {
                "parent_edge_ids": parents,
                "child_edge_ids": children,
                "supporting_edges": supporting,
                "conflicting_edges": conflicting,
                "independent_edges": independent,
            }
        )
        record = edge_record_from_dict(payload).with_hash()
        self._records_by_id[edge_id] = record
        self._persist()
        return record

    def registry_hash(self) -> str:
        return canonical_hash(self.to_dict(include_hashes=True))

    def to_dict(self, *, include_hashes: bool = True) -> dict[str, Any]:
        return {
            "registry_version": EDGE_REGISTRY_VERSION,
            "edge_count": len(self._records_by_id),
            "advisory_flags": dict(ADVISORY_FLAGS),
            "edges": [
                self._records_by_id[key].to_dict(include_hash=include_hashes)
                for key in sorted(self._records_by_id)
            ],
        }

    def _next_edge_id(self) -> str:
        max_id = 0
        for edge_id in self._records_by_id:
            if edge_id.startswith("EDGE-"):
                try:
                    max_id = max(max_id, int(edge_id.split("-", 1)[1]))
                except ValueError:
                    pass
        return f"EDGE-{max_id + 1:06d}"

    def _relationship_ids(
        self,
        edge_id: str,
        values: Sequence[str],
        relationship: str,
        *,
        allow_self: bool = False,
    ) -> tuple[str, ...]:
        ids = tuple(sorted({str(value) for value in values if str(value).strip()}))
        if not allow_self and edge_id in ids:
            raise ValueError(f"edge_relationship_self_reference:{relationship}:{edge_id}")
        missing = [value for value in ids if value not in self._records_by_id]
        if missing:
            raise ValueError(f"edge_relationship_unknown_reference:{relationship}:{','.join(missing)}")
        return ids

    def _load(self) -> None:
        if self.path is None:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        for item in payload.get("edges") or []:
            if not isinstance(item, Mapping):
                continue
            record = edge_record_from_dict(item)
            self._records_by_id[record.edge_id] = record
            self._ids_by_signature[record.signature] = record.edge_id

    def _persist(self) -> None:
        if self.path is not None:
            _atomic_write_json(self.path, self.to_dict(include_hashes=True))
