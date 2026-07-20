"""Phase 179 — Executive Decision Intelligence engine (orchestration only)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.executive_decision_intelligence.adapters import (
    extract_brief_readiness,
    extract_financial_package_safe,
    extract_operational_signals,
)
from backend.executive_decision_intelligence.decision_confidence import compute_decision_confidence
from backend.executive_decision_intelligence.decision_models import DISCLAIMER, SCHEMA_VERSION
from backend.executive_decision_intelligence.executive_priorities import build_executive_priorities
from backend.executive_decision_intelligence.executive_scorecard import build_executive_scorecard
from backend.executive_decision_intelligence.management_recommendations import (
    build_management_recommendations,
)
from backend.executive_decision_intelligence.opportunity_priorities import build_opportunity_priorities
from backend.executive_decision_intelligence.resource_allocator import build_resource_priorities
from backend.executive_decision_intelligence.risk_priorities import build_risk_priorities
from backend.financial_reporting.models import deep_freeze_dict


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def derive_executive_state(
    *,
    financial_summary: dict[str, Any],
    operational: dict[str, Any],
    brief_readiness: dict[str, Any],
    input_errors: list[str],
) -> str:
    if input_errors and not financial_summary:
        return "DEGRADED"
    ready = str(financial_summary.get("reporting_readiness") or "NOT_READY").upper()
    light = str(financial_summary.get("profitability_traffic_light") or "NOT_AVAILABLE").upper()
    brief = str(brief_readiness.get("overall_state") or "").upper()
    if operational.get("runtime_offline") or ready == "NOT_READY" or brief == "NOT_READY":
        return "NOT_READY"
    if light == "RED" or ready == "RED" or brief == "RED" or str(operational.get("risk_state") or "").upper() in {
        "RED",
        "CRITICAL",
    }:
        return "STRESSED"
    if light == "AMBER" or ready == "AMBER" or brief == "AMBER" or (operational.get("alert_count") or 0) > 0:
        return "ATTENTION"
    if light == "GREEN" and ready == "GREEN":
        return "STABLE"
    return "ATTENTION"


class ExecutiveDecisionEngine:
    """Canonical EDI orchestrator — consumes upstream packages; no financial math."""

    def generate(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state if isinstance(state, dict) else {}
        package, errors = extract_financial_package_safe(state)
        summary = package.get("financial_summary") if isinstance(package.get("financial_summary"), dict) else {}
        actions = list(package.get("management_actions") or []) if isinstance(package, dict) else []
        operational = extract_operational_signals(state)
        brief = extract_brief_readiness(state)

        confidence = compute_decision_confidence(
            financial_summary=summary,
            brief_readiness=brief,
            operational=operational,
            input_errors=errors,
        )
        priorities = build_executive_priorities(
            management_actions=actions,
            operational=operational,
            financial_summary=summary,
        )
        risks = build_risk_priorities(
            financial_summary=summary,
            operational=operational,
            brief_readiness=brief,
        )
        opportunities = build_opportunity_priorities(
            financial_summary=summary,
            operational=operational,
        )
        recommendations = build_management_recommendations(
            priorities=priorities,
            risks=risks,
            opportunities=opportunities,
        )
        resources = build_resource_priorities(priorities=priorities, risks=risks)
        scorecard = build_executive_scorecard(
            financial_summary=summary,
            operational=operational,
            brief_readiness=brief,
            confidence=confidence,
        )
        executive_state = derive_executive_state(
            financial_summary=summary,
            operational=operational,
            brief_readiness=brief,
            input_errors=errors,
        )
        recommended_next = (
            recommendations[0]
            if recommendations
            else {
                "code": "rec:none",
                "title": "No recommendation available.",
                "advisory_only": True,
                "trading_impact": False,
            }
        )

        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _utc_now(),
            "executive_state": executive_state,
            "recommended_executive_focus": recommended_next.get("title"),
            "recommended_next_action": recommended_next,
            "priorities": priorities,
            "immediate_actions": [p for p in priorities if p.get("priority") in {"CRITICAL", "HIGH"}][:5],
            "escalations": [r for r in risks if r.get("priority") in {"CRITICAL", "HIGH"}][:5],
            "risks": risks,
            "opportunities": opportunities,
            "recommendations": recommendations,
            "resource_priorities": resources,
            "scorecard": scorecard,
            "confidence": confidence,
            "top_five_priorities": priorities[:5],
            "top_risks": risks[:5],
            "top_opportunities": opportunities[:5],
            "upstream": {
                "phase178_report_id": package.get("report_id") if isinstance(package, dict) else None,
                "phase178_readiness": summary.get("reporting_readiness"),
                "phase178_traffic_light": summary.get("profitability_traffic_light"),
                "phase176j_state": brief.get("overall_state"),
                "phase176j_source": brief.get("source"),
                "input_errors": list(errors),
            },
            "limitations": [
                "Orchestration / decision-support only — does not recalculate Phase 177 statements.",
                "Does not duplicate Phase 178 packaging math.",
                "Does not read brokers or live execution engines directly.",
                "Management recommendations are advisory and non-executing.",
            ],
            "disclaimer": DISCLAIMER,
            "advisory_only": True,
            "trading_impact": False,
        }
        return deep_freeze_dict(payload)

    def degraded(self) -> dict[str, Any]:
        return self.generate({})
