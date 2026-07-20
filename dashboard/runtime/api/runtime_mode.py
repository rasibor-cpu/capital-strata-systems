"""
Phase 177A — Runtime Mode API (read-only).

GET /api/runtime-mode
GET /api/runtime-mode/resolution
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

from backend.runtime.runtime_mode import RuntimeModeResolver

_BANNED = ("password", "secret", "token", "api_key", "traceback", "credential", "private_key")


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    for banned in _BANNED:
        payload.pop(banned, None)
    return payload


def create_runtime_mode_router(
    *,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["runtime-mode"])
    resolver = RuntimeModeResolver()

    def _ctx() -> dict[str, Any]:
        if state_provider is None:
            return {}
        try:
            state = state_provider() or {}
            return state if isinstance(state, dict) else {}
        except Exception:
            return {}

    @router.get("/api/runtime-mode")
    def get_runtime_mode() -> dict[str, Any]:
        return _scrub(_resolve_from_state(_ctx(), resolver))

    @router.get("/api/runtime-mode/resolution")
    def get_runtime_mode_resolution() -> dict[str, Any]:
        return _scrub(_resolve_from_state(_ctx(), resolver))

    return router


def _resolve_from_state(state: dict[str, Any], resolver: RuntimeModeResolver) -> dict[str, Any]:
    session = state.get("session") if isinstance(state.get("session"), dict) else {}
    broker_startup = state.get("broker_startup") if isinstance(state.get("broker_startup"), dict) else {}
    if not broker_startup and isinstance(state.get("broker"), dict):
        broker_startup = state.get("broker") or {}
    evidence = state.get("live_execution_authority") if isinstance(state.get("live_execution_authority"), dict) else {}
    try:
        return resolver.as_dict(
            session=session,
            broker_startup=broker_startup,
            evidence=evidence,
            explicit_mode=state.get("runtime_mode") or state.get("operator_runtime_mode"),
        )
    except Exception:
        return resolver.as_dict()  # fail-closed empty → DISABLED
