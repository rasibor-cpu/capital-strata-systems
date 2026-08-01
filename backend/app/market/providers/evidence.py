"""Phase 186A-R1 — canonical offline evidence hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def canonical_evidence_hash(payload: Mapping[str, Any]) -> str:
    """SHA-256 over a sorted JSON canonicalization of material facts."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def quality_rank(quality: str) -> int:
    token = str(quality or "").upper()
    order = {
        "CERTIFIED": 3,
        "GOVERNED_IDENTITY": 3,
        "UNVERIFIED": 2,
        "UNKNOWN": 1,
    }
    return order.get(token, 0)


def weakest_quality(*qualities: str) -> str:
    if not qualities:
        return "UNKNOWN"
    ranked = sorted(((quality_rank(q), q) for q in qualities), key=lambda item: item[0])
    return ranked[0][1]
