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

    @staticmethod
    def _stale_evidence(state: dict[str, Any] | None) -> bool:
        state = state if isinstance(state, dict) else {}
        freshness = state.get("data_freshness") if isinstance(state.get("data_freshness"), dict) else {}
        runtime = state.get("runtime") if isinstance(state.get("runtime"), dict) else {}
        platform = state.get("platform") if isinstance(state.get("platform"), dict) else {}
        return (
            str(freshness.get("overall_freshness") or "").strip().upper()
            in {"STALE", "EXPIRED", "UNAVAILABLE", "UNKNOWN"}
            or bool(freshness.get("stale_mandatory_data"))
            or str(runtime.get("heartbeat_status") or "").strip().upper()
            in {"STALE", "OFFLINE", "UNAVAILABLE", "UNKNOWN"}
            or str(platform.get("runtime_mode") or "").strip().upper() == "DISABLED"
        )

    @staticmethod
    def _freshness_metadata(stale: bool) -> dict[str, Any]:
        return {
            "freshness_gate": "STALE_OR_UNAVAILABLE" if stale else "CURRENT",
            "evidence_current": not stale,
            "advisory_only": True,
            "trading_impact": False,
        }

    @staticmethod
    def _withheld_items(kind: str) -> list[dict[str, Any]]:
        return [
            {
                "code": f"{kind}:withheld_stale_evidence",
                "title": "Withheld until mandatory executive evidence is current.",
                "priority": "CRITICAL",
                "advisory_only": True,
                "trading_impact": False,
            }
        ]

    def generate(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self.engine.generate(state)
        except Exception:
            return self.degraded()

    def summary(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        stale_evidence = self._stale_evidence(state)
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
        state = state if isinstance(state, dict) else {}
        stale = self._stale_evidence(state)
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "executive_state": "NOT_READY" if stale else full.get("executive_state"),
                "priorities": self._withheld_items("priority") if stale else (full.get("priorities") or []),
                "immediate_actions": self._withheld_items("action") if stale else (full.get("immediate_actions") or []),
                "escalations": self._withheld_items("escalation") if stale else (full.get("escalations") or []),
                **self._freshness_metadata(stale),
            }
        )

    def risks(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        stale = self._stale_evidence(state)
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "executive_state": "NOT_READY" if stale else full.get("executive_state"),
                "risks": self._withheld_items("risk") if stale else (full.get("risks") or []),
                **self._freshness_metadata(stale),
            }
        )

    def opportunities(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        stale = self._stale_evidence(state)
        full = self.generate(state)
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "executive_state": "NOT_READY" if stale else full.get("executive_state"),
                "opportunities": [] if stale else (full.get("opportunities") or []),
                **self._freshness_metadata(stale),
            }
        )

    def recommendations(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        stale = self._stale_evidence(state)
        full = self.generate(state)
        if stale:
            withheld = self._withheld_items("recommendation")
            next_action = withheld[0]
            resource_priorities: list[dict[str, Any]] = []
        else:
            withheld = full.get("recommendations") or []
            next_action = full.get("recommended_next_action")
            resource_priorities = full.get("resource_priorities") or []
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "executive_state": "NOT_READY" if stale else full.get("executive_state"),
                "recommendations": withheld,
                "resource_priorities": resource_priorities,
                "recommended_next_action": next_action,
                **self._freshness_metadata(stale),
            }
        )

    def scorecard(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        stale = self._stale_evidence(state)
        full = self.generate(state)
        confidence = (
            {
                "overall_confidence": 0.0,
                "confidence_band": "VERY_LOW",
                "reasons": ["stale_or_unavailable_mandatory_evidence"],
            }
            if stale
            else (full.get("confidence") or {})
        )
        scorecard = (
            {
                "status": "NOT_READY",
                "reason": "Mandatory executive evidence is stale or unavailable.",
            }
            if stale
            else (full.get("scorecard") or {})
        )
        return deep_freeze_dict(
            {
                "schema_version": SCHEMA_VERSION,
                "generated_at": full.get("generated_at"),
                "executive_state": "NOT_READY" if stale else full.get("executive_state"),
                "scorecard": scorecard,
                "confidence": confidence,
                **self._freshness_metadata(stale),
            }
        )

    def degraded(self) -> dict[str, Any]:
        return self.engine.degraded()
