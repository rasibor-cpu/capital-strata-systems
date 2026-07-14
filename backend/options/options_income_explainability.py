from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from backend.options.options_income_dashboard_payloads import _list, _mapping, _number
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeExplainabilityError(ValueError):
    """Raised when explainability generation must fail closed."""


class OptionsIncomeExplainabilityEngine:
    def build(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        root = _mapping(payload)
        explanations: list[dict[str, Any]] = []
        opportunities = _mapping(root.get("opportunities"))
        positions = _mapping(root.get("positions"))
        rolls = _mapping(root.get("rolls"))
        portfolio = _mapping(root.get("portfolio"))
        risk = _mapping(root.get("risk"))
        alerts = _list(root.get("alerts"))

        for row in _list(opportunities.get("accepted_candidates")):
            item = _mapping(row)
            explanations.append(
                _explain(
                    "OPPORTUNITY_ACCEPTED",
                    f"{item.get('underlying')} {item.get('strategy_type')} accepted for paper monitoring.",
                    ["scanner validation passed", "ranking score available", "collateral requirement calculated"],
                    {"ranking_score": item.get("ranking_score"), "yield": item.get("yield"), "spread": item.get("spread")},
                    ["OI-002 strategy validation", "OI-003 liquidity and ranking"],
                    source_modules=["OI-002", "OI-003"],
                    entity=str(item.get("option_symbol", "")),
                )
            )
        for row in _list(opportunities.get("rejected_candidates")):
            item = _mapping(row)
            reasons = _list(item.get("rejection_reasons")) or ["scanner validation failed"]
            explanations.append(
                _explain(
                    "OPPORTUNITY_REJECTED",
                    f"{item.get('underlying')} {item.get('strategy_type')} rejected for paper monitoring.",
                    reasons,
                    {"ranking_score": item.get("ranking_score"), "yield": item.get("yield")},
                    ["OI-002 strategy validation", "OI-003 fail-closed candidate screening"],
                    warnings=reasons,
                    source_modules=["OI-002", "OI-003"],
                    entity=str(item.get("option_symbol", "")),
                )
            )
        for row in _list(positions.get("active_positions")) + _list(positions.get("completed_positions")):
            item = _mapping(row)
            healthy = _number(item.get("health_score")) >= 70.0
            explanations.append(
                _explain(
                    "POSITION_HEALTHY" if healthy else "POSITION_UNHEALTHY",
                    f"{item.get('position_id')} health is {'acceptable' if healthy else 'degraded'} for paper monitoring.",
                    ["health score threshold evaluated", "premium capture reviewed", "assignment exposure reviewed"],
                    {
                        "health_score": item.get("health_score"),
                        "premium_capture_percentage": item.get("premium_capture_percentage"),
                        "days_remaining": item.get("days_remaining"),
                    },
                    ["OI-004 lifecycle state", "OI-005 position health"],
                    warnings=[] if healthy else ["health score below advisory threshold"],
                    source_modules=["OI-004", "OI-005"],
                    entity=str(item.get("position_id", "")),
                )
            )
        for row in _list(rolls.get("recommendations")):
            item = _mapping(row)
            explanations.append(
                _explain(
                    "ROLL_RECOMMENDED" if item.get("recommendation") != "NO_ROLL" else "NO_ROLL_RECOMMENDED",
                    f"{item.get('recommendation')} selected for {item.get('position_id')} as advisory paper action.",
                    [str(item.get("reason", "rolling rule evaluated"))],
                    {
                        "confidence": item.get("confidence"),
                        "expected_premium_impact": item.get("expected_premium_impact"),
                        "capital_impact": item.get("capital_impact"),
                    },
                    ["OI-005 rolling candidate generation", "OI-005 roll decision"],
                    source_modules=["OI-005"],
                    entity=str(item.get("position_id", "")),
                )
            )
        if portfolio:
            explanations.append(
                _explain(
                    "PORTFOLIO_ALLOCATION_SELECTED",
                    "Paper portfolio allocation was selected from available options-income candidates and positions.",
                    ["capital allocation completed", "diversification evaluated", "income target evaluated"],
                    {
                        "portfolio_utilization": portfolio.get("portfolio_utilization"),
                        "expected_premium": portfolio.get("expected_premium"),
                        "ladder_quality_score": portfolio.get("ladder_quality_score"),
                    },
                    ["OI-006 allocation", "OI-006 diversification", "OI-006 laddering", "OI-006 targets"],
                    warnings=_list(portfolio.get("warnings")),
                    source_modules=["OI-006"],
                    entity=str(portfolio.get("portfolio_id", "")),
                )
            )
        for breach in _list(portfolio.get("constraint_breaches")):
            explanations.append(
                _explain(
                    "CONSTRAINT_BREACHED",
                    str(breach),
                    [str(breach)],
                    {"constraint_status": portfolio.get("constraint_status")},
                    ["OI-006 constraints"],
                    warnings=[str(breach)],
                    source_modules=["OI-006"],
                    entity=str(portfolio.get("portfolio_id", "")),
                )
            )
        if risk:
            explanations.append(
                _explain(
                    "RISK_STATUS_ASSIGNED",
                    f"Risk status {risk.get('risk_status')} assigned with approval {risk.get('approval_status')}.",
                    ["risk budgets evaluated", "risk limits evaluated", "stress scenarios evaluated"],
                    {"risk_score": risk.get("risk_score"), "estimated_stressed_loss": risk.get("estimated_stressed_loss")},
                    ["OI-007 Greeks", "OI-007 budgets", "OI-007 limits", "OI-007 stress tests"],
                    warnings=_list(risk.get("advisory_limit_breaches")),
                    unavailable_inputs=_list(risk.get("unavailable_risk_data")),
                    source_modules=["OI-007"],
                    entity="risk-governance",
                )
            )
            explanations.append(
                _explain(
                    "PAPER_PORTFOLIO_APPROVED" if str(risk.get("approval_status", "")).startswith("APPROVED") else "PAPER_PORTFOLIO_REJECTED",
                    f"Paper portfolio approval state is {risk.get('approval_status')}.",
                    _list(risk.get("hard_limit_breaches")) or ["no hard risk-limit breach detected"],
                    {"approval_status": risk.get("approval_status"), "risk_status": risk.get("risk_status")},
                    ["OI-007 risk-governance assessment"],
                    warnings=_list(risk.get("advisory_recommendations")),
                    source_modules=["OI-007"],
                    entity="risk-governance",
                )
            )
        for row in alerts:
            item = _mapping(row)
            explanations.append(
                _explain(
                    "ALERT_RAISED",
                    str(item.get("message", "Options income alert raised.")),
                    [str(item.get("reason", ""))],
                    _mapping(item.get("supporting_metrics")),
                    ["OI-008 alert rules"],
                    warnings=[str(item.get("severity", ""))],
                    source_modules=["OI-008"],
                    entity=str(item.get("alert_id", "")),
                )
            )
        explanations.sort(key=lambda row: (row["decision"], row["entity"], row["explanation_id"]))
        return explanations


def _explain(
    decision: str,
    summary: str,
    primary_reasons: list[str],
    supporting_metrics: Mapping[str, Any],
    rules_evaluated: list[str],
    *,
    warnings: list[Any] | None = None,
    unavailable_inputs: list[Any] | None = None,
    source_modules: list[str] | None = None,
    entity: str = "",
) -> dict[str, Any]:
    identity = f"{decision}|{entity}|{'|'.join(str(item) for item in primary_reasons)}"
    return {
        "explanation_id": f"OI008-EXP-{sha256(identity.encode('utf-8')).hexdigest()[:12]}",
        "entity": entity,
        "decision": decision,
        "summary": summary,
        "primary_reasons": [str(item) for item in primary_reasons],
        "supporting_metrics": dict(supporting_metrics),
        "rules_evaluated": [str(item) for item in rules_evaluated],
        "warnings": [str(item) for item in (warnings or [])],
        "unavailable_inputs": [str(item) for item in (unavailable_inputs or [])],
        "advisory_flags": dict(SAFE_FLAGS),
        "source_modules": list(source_modules or []),
        "paper_only": True,
        **SAFE_FLAGS,
    }


__all__ = ["OptionsIncomeExplainabilityEngine", "OptionsIncomeExplainabilityError"]
