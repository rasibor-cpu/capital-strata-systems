from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def committee_dashboard_section(report: Mapping[str, Any]) -> dict[str, Any]:
    evaluations = report.get("evaluations") if isinstance(report.get("evaluations"), list) else []
    top = evaluations[0] if evaluations and isinstance(evaluations[0], Mapping) else {}
    opportunity = top.get("opportunity") if isinstance(top.get("opportunity"), Mapping) else {}
    scorecard = top.get("scorecard") if isinstance(top.get("scorecard"), Mapping) else {}
    consensus = top.get("consensus") if isinstance(top.get("consensus"), Mapping) else report.get("consensus_summary", {})
    consensus = consensus if isinstance(consensus, Mapping) else {}
    votes = top.get("committee_votes") if isinstance(top.get("committee_votes"), list) else []
    return {
        "generated_at": report.get("generated_at"),
        "committee_score": report.get("committee_score", 0.0),
        "decision": report.get("decision", "WAIT"),
        "capital_rank": top.get("capital_rank", 0),
        "expected_return": opportunity.get("expected_return", 0.0),
        "expected_drawdown": opportunity.get("expected_drawdown", 0.0),
        "confidence": opportunity.get("decision_confidence", 0.0),
        "capital_efficiency": opportunity.get("capital_efficiency", 0.0),
        "opportunity_rank": top.get("opportunity_rank", 0),
        "committee_recommendation": top.get("recommendation", "No committee recommendation available."),
        "consensus_score": consensus.get("consensus_score", 0.0),
        "weighted_committee_confidence": consensus.get("weighted_committee_confidence", 0.0),
        "consensus": consensus.get("consensus", "NO_VOTES"),
        "veto_reasons": consensus.get("veto_reasons", []),
        "committee_votes": votes,
        "committee_explanations": [
            {
                "committee": item.get("committee", "UNKNOWN"),
                "vote": item.get("vote", "ABSTAIN"),
                "confidence": item.get("confidence", 0.0),
                "reason": item.get("reason", ""),
            }
            for item in votes
            if isinstance(item, Mapping)
        ],
        "top_opportunities": [
            {
                "capital_rank": item.get("capital_rank"),
                "opportunity_rank": item.get("opportunity_rank"),
                "symbol": (item.get("opportunity") or {}).get("symbol") if isinstance(item.get("opportunity"), Mapping) else "UNKNOWN",
                "decision": item.get("decision"),
                "committee_score": (item.get("scorecard") or {}).get("committee_score") if isinstance(item.get("scorecard"), Mapping) else 0.0,
                "recommended_capital": item.get("recommended_capital", 0.0),
                "recommendation": item.get("recommendation", ""),
            }
            for item in evaluations[:5]
            if isinstance(item, Mapping)
        ],
        "capital_plan": report.get("capital_plan", []),
        "blockers": report.get("blockers", []),
        "recommendations": report.get("recommendations", []),
        "scorecard": scorecard,
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }
