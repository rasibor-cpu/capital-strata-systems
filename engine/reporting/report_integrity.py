"""
Report Integrity Module
Capital Strata Systems – Phase 17

Provides:
- Deterministic canonical JSON encoding
- SHA256 hash generation
- Schema version tagging
- Auditor reproducibility guarantee
"""

from __future__ import annotations

import json
import hashlib
from typing import Any, Dict


SCHEMA_VERSION = "v1.0"


def _canonical_json(payload: Dict[str, Any]) -> str:
    """
    Produce deterministic JSON string:
    - Sorted keys
    - No whitespace variance
    - UTF-8 normalized
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_report_hash(payload: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of canonical JSON payload.
    """
    canonical = _canonical_json(payload)
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return sha


def attach_integrity_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attach schema version + hash to report output.
    """
    canonical_payload = dict(payload)  # shallow copy

    canonical_payload["schema_version"] = SCHEMA_VERSION

    report_hash = compute_report_hash(canonical_payload)

    canonical_payload["integrity"] = {
        "hash_algo": "SHA256",
        "hash": report_hash,
    }

    return canonical_payload