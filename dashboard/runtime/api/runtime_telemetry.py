"""
Phase 177F — Runtime Telemetry API (read-only).

GET /api/runtime-telemetry
GET /api/runtime-telemetry/status
GET /api/runtime-telemetry/provenance
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.runtime.runtime_telemetry import build_runtime_telemetry, telemetry_summary_for_ui

_BANNED = ("password", "secret", "token", "api_key", "traceback", "credential", "private_key")


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    for banned in _BANNED:
        payload.pop(banned, None)
    return payload


def create_runtime_telemetry_router() -> APIRouter:
    router = APIRouter(tags=["runtime-telemetry"])

    @router.get("/api/runtime-telemetry")
    def get_runtime_telemetry() -> dict[str, Any]:
        return _scrub(build_runtime_telemetry())

    @router.get("/api/runtime-telemetry/status")
    def get_runtime_telemetry_status() -> dict[str, Any]:
        return _scrub(telemetry_summary_for_ui())

    @router.get("/api/runtime-telemetry/provenance")
    def get_runtime_telemetry_provenance() -> dict[str, Any]:
        snap = build_runtime_telemetry()
        fields = snap.get("fields") if isinstance(snap.get("fields"), dict) else {}
        provenance = {
            name: {
                "source": row.get("source"),
                "definition": row.get("definition"),
                "period": row.get("period"),
                "status": row.get("status"),
                "freshness": row.get("freshness"),
            }
            for name, row in fields.items()
            if isinstance(row, dict)
        }
        return _scrub(
            {
                "schema_version": snap.get("schema_version"),
                "provenance": provenance,
                "aliases": snap.get("compatibility_aliases"),
                "paths": snap.get("paths"),
                "generated_at": snap.get("generated_at"),
                "state_hash": snap.get("state_hash"),
            }
        )

    return router


__all__ = ["create_runtime_telemetry_router"]
