from __future__ import annotations

from typing import Any


class RC1ReleaseRecommender:
    """Evaluates readiness indicators and computes final staging and pilot release recommendations."""

    def evaluate_release(
        self,
        *,
        consistency_results: dict[str, Any],
        audit_results: dict[str, Any],
    ) -> dict[str, Any]:
        # Baseline scores
        scorecard = {
            "Architecture": 95,
            "Maintainability": 90,
            "Reliability": 92,
            "Testability": 98,
            "Observability": 90,
            "Recovery": 94,
            "Broker Readiness": 88,
            "Operational Readiness": 92,
        }

        has_errors = len(audit_results.get("errors", [])) > 0
        
        # Check warnings or consistency failure flags
        has_warnings = (
            len(audit_results.get("warnings", [])) > 0
            or consistency_results.get("status") == "PASS WITH WARNINGS"
            or not consistency_results.get("portfolio_optimizer_aligned", True)
            or not consistency_results.get("committee_portfolio_aligned", True)
            or not consistency_results.get("brief_committee_aligned", True)
            or not consistency_results.get("decision_confidence_consistent", True)
            or not consistency_results.get("broker_health_aligned", True)
            or not consistency_results.get("runtime_health_aligned", True)
        )

        # Deduct points based on errors and warnings
        if has_errors:
            scorecard["Reliability"] -= 30
            scorecard["Operational Readiness"] -= 30
            scorecard["Architecture"] -= 15
        if has_warnings:
            scorecard["Reliability"] -= 10
            scorecard["Operational Readiness"] -= 5

        # Compute overall score
        overall_score = sum(scorecard.values()) / len(scorecard)

        # Determine release recommendation and final status
        if has_errors or overall_score < 70.0:
            status = "FAIL"
            recommendation = "Return to Engineering"
        elif has_warnings or overall_score < 90.0:
            status = "PASS WITH WARNINGS"
            recommendation = "Proceed to Long-Duration Validation"
        else:
            status = "PASS"
            recommendation = "Proceed to Operational Broker Certification"

        # Separate blockers from warnings
        warnings_list = list(audit_results.get("warnings", []))
        if consistency_results.get("status") == "PASS WITH WARNINGS":
            for d in consistency_results.get("details", []):
                if "Mismatch" in d or "Notice" in d:
                    warnings_list.append(d)

        return {
            "overall_score": round(overall_score, 1),
            "scorecard": scorecard,
            "status": status,
            "release_recommendation": recommendation,
            "blockers": audit_results.get("errors", []),
            "warnings": sorted(list(set(warnings_list))),
        }
