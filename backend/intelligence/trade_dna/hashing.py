"""DIP-002 Trade DNA hashing — deterministic content digests."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


CONTENT_HASH_FIELD = "content_hash"


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Serialize a mapping to stable UTF-8 JSON for hashing."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def strip_content_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow copy without content_hash (hash is over the remainder)."""
    return {k: v for k, v in payload.items() if k != CONTENT_HASH_FIELD}


def compute_content_hash(payload: Mapping[str, Any]) -> str:
    """SHA-256 hex digest of canonical JSON excluding content_hash itself."""
    body = strip_content_hash(payload)
    return hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def verify_content_hash(payload: Mapping[str, Any]) -> bool:
    """Return True when payload.content_hash matches recomputed digest."""
    declared = payload.get(CONTENT_HASH_FIELD)
    if not isinstance(declared, str) or not declared:
        return False
    return declared == compute_content_hash(payload)
