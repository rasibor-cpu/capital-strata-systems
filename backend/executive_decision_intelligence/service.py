"""Phase 179 — Executive Decision Intelligence service facade."""

from __future__ import annotations

from typing import Any

from backend.executive_decision_intelligence.decision_engine import ExecutiveDecisionEngine
from backend.executive_decision_intelligence.decision_models import SCHEMA_VERSION
from backend.financial_reporting.models import deep_freeze_dict

__all__ = ["ExecutiveDecisionIntelligenceService", "SCHEMA_VERSION"]


class ExecutiveDecisionIntelligenceService:
    """Read-only EDI service — delegates to ExecutiveDecisionEngine."""

    def __init__(self, *, engine: ExecutiveDecisionEngine | None = None) -> None:
        self.engine = engine or ExecutiveDecisionEngine()

    def generate(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self.engine.generate(state)
        except Exception:
            return self.degraded()

    def summary(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        freshness = state.get("data_freshness") if isinstance(state.get("data_freshness"), dict) else {}
        runtime = state.get("runtime") if isinstance(state.get("runtime"), dict) else {}
        stale_evidence = (
            str(freshness.get("overall_freshness") or "").strip().upper()
            in {"STALE", "EXPIRED", "UNAVAILABLE", "UNKNOWN"}
            or bool(freshness.get("stale_mandatory_data"))
            or str(runtime.get("heartbeat_status") or "").strip().upper()
            in {"STALE", "OFFLINE", "UNAVAILABLE", "UNKNOWN"}
        )
        full = self.generate(state)
        if stale_evidence:
            generated_at = full.get("generated_at")
            return deep_freeze_dict(
                {
                    "schema_version": full.get("schema_version"),
                    "generated_at": generated_at,
                    "executive_state": "NOT_READY",
                    "recommended_executive_focus": "Refresh or validate stale source evidence before relying on executive conclusions.",
                    "recommended_next_action": {
                        "code": "rec:refresh_source_evidence",
                        "title": "Refresh or validate stale source evidence before relying on executive conclusions.",
                        "priority": "CRITICAL",
                        "advisory_only": True,
                        "trading_impact": False,
                    },
                    "top_five_priorities": [
                        {
                            "code": "priority:refresh_source_evidence",
                            "title": "Refresh or validate stale source evidence.",
                            "priority": "CRITICAL",
                            "advisory_only": True,
                            "trading_impact": False,
                        }
                    ],
                    "top_risks": [
                        {
                            "code": "risk:stale_evidence",
                            "title": "Executive risk conclusions are withheld because mandatory evidence is stale or unavailable.",
                            "priority": "HIGH",
                            "advisory_only": True,
                            "trading_impact": False,
                        }
                    ],
                    "top_opportunities": [],
                    "confidence": {
                        "overall_confidence": 0.0,
                        "confidence_band": "VERY_LOW",
                        "reasons": ["stale_or_unavailable_mandatory_evidence"],
                    },
                    "upstream": {
                        **(full.get("upstream") if isinstance(full.get("upstream"), dict) else {}),
                        "freshness_gate": "STALE_OR_UNAVAILABLE",
                    },
                    "disclaimer": full.get("disclaimer"),
                    "advisory_only": True,
                    "trading_impact": False,
                }
            )
        return deep_freeze_dict(
            {
                "schema_version": full.get("schema_version"),
                "generated_at": full.get("generated_at"),
                "executive_state": full.get("executive_state"),
                "recommended_executive_focus": full.get("recommended_executive_focus"),
                "recommended_next_action": full.get("recommended_next_action"),
                "top_five_priorities": full.get("top_five_priorities"),
                "top_risks": full.get("top_risks")[:3] if isinstance(full.get("top_risks"), list) else [],
                "top_opportunities": full.get("top_opportunities")[:3]
                if isinstance(full.get("top_opportunities"), list)
                else [],
                "confidence": full.get("confidence"),
                "upstream": full.get("upstream"),
                "disclaimer": full.get("disclaimer"),
                "advisory_only": True,
                "trading_impact": False,
            }
        )

    def priorities(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "priorities": full.get("priorities") or [],
                "immediate_actions": full.get("immediate_actions") or [],
                "escalations": full.get("escalations") or [],
                "advisory_only": True,
                "trading_impact": False,
            }
        )

    def risks(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "risks": full.get("risks") or [],
                "advisory_only": True,
                "trading_impact": False,
            }
        )

    def opportunities(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "opportunities": full.get("opportunities") or [],
                "advisory_only": True,
                "trading_impact": False,
            }
        )

    def recommendations(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "recommendations": full.get("recommendations") or [],
                "resource_priorities": full.get("resource_priorities") or [],
                "recommended_next_action": full.get("recommended_next_action"),
                "advisory_only": True,
                "trading_impact": False,
            }
        )

    def scorecard(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "executive_state": full.get("executive_state"),
                "scorecard": full.get("scorecard") or {},
                "confidence": full.get("confidence") or {},
                "advisory_only": True,
                "trading_impact": False,
            }
        )

    def degraded(self) -> dict[str, Any]:
        return self.engine.degraded()
