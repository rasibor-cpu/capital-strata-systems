"""
Phase 179 — Executive Decision Intelligence API (advisory / read-only).

GET /api/executive-decision-intelligence/summary
GET /api/executive-decision-intelligence/priorities
GET /api/executive-decision-intelligence/risks
GET /api/executive-decision-intelligence/opportunities
GET /api/executive-decision-intelligence/recommendations
GET /api/executive-decision-intelligence/scorecard
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

from backend.executive_decision_intelligence.service import ExecutiveDecisionIntelligenceService

_BANNED = ("password", "secret", "token", "api_key", "traceback", "stack", "credential")


def _scrub(payload: dict[str, Any]) -> dict[str, Any]:
    for banned in _BANNED:
        payload.pop(banned, None)
    return payload


def create_executive_decision_intelligence_router(
    *,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    router = APIRouter(tags=["executive-decision-intelligence"])
    service = ExecutiveDecisionIntelligenceService()

    def _state() -> dict[str, Any]:
        if state_provider is None:
            return {}
        try:
            state = state_provider() or {}
            return state if isinstance(state, dict) else {}
        except Exception:
            return {}

    @router.get("/api/executive-decision-intelligence/summary")
    def get_summary() -> dict[str, Any]:
        try:
            return _scrub(dict(service.summary(_state())))
        except Exception:
            return _scrub(dict(service.summary({})))

    @router.get("/api/executive-decision-intelligence/priorities")
    def get_priorities() -> dict[str, Any]:
        try:
            return _scrub(dict(service.priorities(_state())))
        except Exception:
            return _scrub(dict(service.priorities({})))

    @router.get("/api/executive-decision-intelligence/risks")
    def get_risks() -> dict[str, Any]:
        try:
            return _scrub(dict(service.risks(_state())))
        except Exception:
            return _scrub(dict(service.risks({})))

    @router.get("/api/executive-decision-intelligence/opportunities")
    def get_opportunities() -> dict[str, Any]:
        try:
            return _scrub(dict(service.opportunities(_state())))
        except Exception:
            return _scrub(dict(service.opportunities({})))

    @router.get("/api/executive-decision-intelligence/recommendations")
    def get_recommendations() -> dict[str, Any]:
        try:
            return _scrub(dict(service.recommendations(_state())))
        except Exception:
            return _scrub(dict(service.recommendations({})))

    @router.get("/api/executive-decision-intelligence/scorecard")
    def get_scorecard() -> dict[str, Any]:
        try:
            return _scrub(dict(service.scorecard(_state())))
        except Exception:
            return _scrub(dict(service.scorecard({})))

    return router
