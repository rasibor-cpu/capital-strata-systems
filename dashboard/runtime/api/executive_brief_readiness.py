"""
Phase 176J — Executive Brief readiness API (advisory / read-only).

GET /api/executive-brief/readiness
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter

from backend.reporting.executive_brief_readiness_orchestrator import (
    STATE_NOT_READY,
    ExecutiveBriefReadinessOrchestrator,
    evidence_from_mission_control_state,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_SAFE_EMPTY_RESPONSE: dict[str, Any] = {
    "schema_version": "css.executive_brief_readiness_report.v1",
    "timestamp": None,
    "overall_state": STATE_NOT_READY,
    "overall_readiness_score": 0.0,
    "score": 0.0,
    "blocking_items": ["Readiness evaluation unavailable"],
    "warning_items": [],
    "advisories": [],
    "recommended_actions": [
        "Re-check Executive Brief readiness after the next runtime snapshot.",
        "This readiness layer is advisory-only and does not alter trading or execution.",
    ],
    "estimated_generation_time": "unknown",
    "estimated_generation_seconds": 0,
    "missing_datasets": [],
    "outdated_datasets": [],
    "components": [],
    "advisory_only": True,
    "trading_impact": False,
}


def create_executive_brief_readiness_router(
    *,
    state_provider: Callable[[], dict[str, Any]] | None = None,
) -> APIRouter:
    """
    Expose advisory Executive Brief readiness.

    Optional state_provider supplies Mission Control–shaped state for evidence
    mapping. When omitted, the orchestrator evaluates empty evidence
    (fail-closed / NOT_READY) without touching brokers or runtime.
    """

    router = APIRouter(tags=["executive-brief-readiness"])
    orchestrator = ExecutiveBriefReadinessOrchestrator()

    @router.get("/api/executive-brief/readiness")
    def get_executive_brief_readiness() -> dict[str, Any]:
        evidence: dict[str, Any] = {}
        try:
            if state_provider is not None:
                try:
                    state = state_provider() or {}
                except Exception:
                    state = {}
                if isinstance(state, dict):
                    if isinstance(state.get("executive_brief_readiness_evidence"), dict):
                        evidence = dict(state["executive_brief_readiness_evidence"])
                    else:
                        try:
                            evidence = evidence_from_mission_control_state(state)
                        except Exception:
                            evidence = {}
            report = orchestrator.generate_report(evidence=evidence)
            payload = report.to_dict()
            payload["get_readiness"] = orchestrator.get_readiness(evidence=evidence)
            for banned in ("password", "secret", "token", "api_key", "traceback", "stack"):
                payload.pop(banned, None)
            return payload
        except Exception:
            safe = dict(_SAFE_EMPTY_RESPONSE)
            safe["timestamp"] = _utc_now_iso()
            safe["get_readiness"] = {
                "overall_state": STATE_NOT_READY,
                "score": 0.0,
                "overall_readiness_score": 0.0,
                "advisory_only": True,
                "trading_impact": False,
            }
            return safe

    return router


__all__ = ["create_executive_brief_readiness_router"]
