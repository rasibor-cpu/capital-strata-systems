"""Phase 191 — deterministic registry hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from backend.app.governance.enterprise_certification_registry.models import CertificationRegistryEntry


class RegistryHash:
    """Immutable hashing helpers for entries and snapshots."""

    @staticmethod
    def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

    @staticmethod
    def hash_payload(payload: Mapping[str, Any]) -> str:
        return hashlib.sha256(RegistryHash.canonical_bytes(payload)).hexdigest()

    @staticmethod
    def hash_entry(entry: CertificationRegistryEntry) -> str:
        body = entry.as_dict()
        # Exclude nested mutable-looking diagnostics noise already frozen; hash full dict.
        return RegistryHash.hash_payload(body)

    @staticmethod
    def hash_entries(entries: Sequence[CertificationRegistryEntry]) -> str:
        payload = {
            "count": len(entries),
            "entries": [e.as_dict() for e in sorted(entries, key=lambda x: x.registry_id)],
        }
        return RegistryHash.hash_payload(payload)
