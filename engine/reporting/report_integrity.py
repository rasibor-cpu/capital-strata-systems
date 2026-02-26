"""
Report Integrity Module – Phase 17C
Capital Strata Systems

Provides:
- Canonical JSON encoding
- SHA256 hash
- Deterministic report_id
- Schema version enforcement
"""

from __future__ import annotations

import json
import hashlib
from typing import Any, Dict
from engine.reporting.schema_registry import get_schema_version


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_hash(payload: Dict[str, Any]) -> str:
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def attach_integrity_metadata(
    payload: Dict[str, Any],
    schema_name: str,
) -> Dict[str, Any]:

    schema_version = get_schema_version(schema_name)

    envelope = dict(payload)
    envelope["schema"] = schema_name
    envelope["schema_version"] = schema_version

    integrity_hash = compute_hash(envelope)

    envelope["integrity"] = {
        "hash_algo": "SHA256",
        "hash": integrity_hash,
    }

    # Deterministic report_id (first 16 chars of hash)
    envelope["report_id"] = integrity_hash[:16]

    return envelope