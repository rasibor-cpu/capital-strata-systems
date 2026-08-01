"""Phase 191 — registry export (redacted, immutable payload)."""

from __future__ import annotations

import json
from typing import Any

from backend.app.governance.enterprise_certification_registry.hashing import RegistryHash
from backend.app.governance.enterprise_certification_registry.snapshot import RegistrySnapshot

_SECRET_FRAGMENTS = ("token", "secret", "password", "api_key", "credential", "bearer")


def _redact(payload: Any) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(frag in lowered for frag in _SECRET_FRAGMENTS):
                out[str(key)] = "[REDACTED]"
            else:
                out[str(key)] = _redact(value)
        return out
    if isinstance(payload, list):
        return [_redact(v) for v in payload]
    return payload


class RegistryExporter:
    def export_snapshot(self, snapshot: RegistrySnapshot) -> dict[str, Any]:
        payload = _redact(snapshot.as_dict())
        payload["execution_authority"] = False
        payload["export_hash"] = RegistryHash.hash_payload(payload)
        return payload

    def export_json(self, snapshot: RegistrySnapshot) -> str:
        return json.dumps(self.export_snapshot(snapshot), sort_keys=True, indent=2)
