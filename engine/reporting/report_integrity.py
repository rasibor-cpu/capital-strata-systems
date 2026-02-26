"""
engine/reporting/report_integrity.py

Report Integrity Metadata (Auditor-Grade)
----------------------------------------
Attaches reproducibility metadata + integrity hash to any report payload.

Change (2026-02-26):
- schema_name is now OPTIONAL (default = "UNSPECIFIED") to prevent
  runtime failures when callers omit it.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _stable_json(obj: Any) -> str:
    """
    Canonical JSON serialization:
    - sort keys
    - no whitespace
    - UTF-8 safe
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def attach_integrity_metadata(
    payload: Dict[str, Any],
    schema_name: Optional[str] = None,
    schema_version: str = "1.0",
) -> Dict[str, Any]:
    """
    Returns a NEW dict with integrity metadata attached.

    payload: dict
    schema_name: optional string describing schema (default "UNSPECIFIED")
    schema_version: semantic version string

    Integrity hash is computed over a canonical representation of payload
    (excluding the integrity block itself).
    """
    schema_name = (schema_name or "UNSPECIFIED").strip() or "UNSPECIFIED"

    base = dict(payload)  # shallow copy

    # Remove any existing integrity block to avoid hash recursion
    base.pop("_integrity", None)

    canonical = _stable_json(base)
    digest = _sha256_hex(canonical)

    integrity = {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "note": "sha256 computed over canonical JSON of payload (excluding _integrity).",
    }

    base["_integrity"] = integrity
    return base