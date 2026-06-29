from __future__ import annotations

from typing import Any, Mapping


class ExplainabilityEngineError(RuntimeError):
    """Fail-closed exception for advisory explanation generation."""


class ExplainabilityEngine:
    """Generate human-readable traceability for portfolio advisory decisions."""

    def explain(
        self,
        portfolio_intelligence: Mapping[str, Any] | None = None,
        adaptive_portfolio: Mapping[str, Any] | None = None,
        risk_committee: Mapping[str, Any] | None = None,
        quantitative_metrics: Mapping[str, Any] | None = None,
        market_regime: Mapping[str, Any] | None = None,
        policy_profile: Mapping[str, Any] | None = None,
        validation: Mapping[str, Any] | None = None,
        consistency: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        explanations: list[str] = []

        if isinstance(adaptive_portfolio, Mapping):
            recommendation = adaptive_portfolio.get("adaptive_recommendation", "UNKNOWN")
            explanations.append(f"Adaptive portfolio recommendation is {recommendation}.")
            for driver in adaptive_portfolio.get("primary_drivers", []) if isinstance(adaptive_portfolio.get("primary_drivers", []), list) else []:
                explanations.append(str(driver))

        if isinstance(portfolio_intelligence, Mapping):
            status = portfolio_intelligence.get("portfolio_status", "UNKNOWN")
            score = portfolio_intelligence.get("intelligence_score", "N/A")
            explanations.append(f"Portfolio intelligence status is {status} with score {score}.")
            for item in portfolio_intelligence.get("explainability", []) if isinstance(portfolio_intelligence.get("explainability", []), list) else []:
                explanations.append(str(item))

        if isinstance(risk_committee, Mapping):
            explanations.append(
                f"Risk committee decision is {risk_committee.get('committee_decision', 'UNKNOWN')} "
                f"with status {risk_committee.get('committee_status', 'UNKNOWN')}."
            )
            for concern in risk_committee.get("concerns", []) if isinstance(risk_committee.get("concerns", []), list) else []:
                explanations.append(f"Committee concern: {concern}.")

        if isinstance(quantitative_metrics, Mapping) and quantitative_metrics.get("status") == "OK":
            metrics = quantitative_metrics.get("metrics", {})
            if isinstance(metrics, Mapping):
                explanations.append(
                    "Quantitative summary: "
                    f"Sharpe={metrics.get('rolling_sharpe')}, "
                    f"Sortino={metrics.get('rolling_sortino')}, "
                    f"MaxDrawdown={metrics.get('max_drawdown')}."
                )

        if isinstance(market_regime, Mapping):
            explanations.append(
                f"Market regime is {market_regime.get('detected_regime', 'UNKNOWN')} "
                f"with {market_regime.get('risk_bias', 'UNKNOWN')} risk bias."
            )

        if isinstance(policy_profile, Mapping):
            explanations.append(f"Active policy profile is {policy_profile.get('active_profile', 'UNKNOWN')}.")

        if isinstance(validation, Mapping) and validation.get("validation_status") != "PASS":
            for violation in validation.get("violations", []) if isinstance(validation.get("violations", []), list) else []:
                explanations.append(f"Validation violation: {violation}.")
            for warning in validation.get("warnings", []) if isinstance(validation.get("warnings", []), list) else []:
                explanations.append(f"Validation warning: {warning}.")

        if isinstance(consistency, Mapping) and consistency.get("consistent") is False:
            for conflict in consistency.get("conflicts", []) if isinstance(consistency.get("conflicts", []), list) else []:
                explanations.append(f"Conflicting signal: {conflict}.")

        if not explanations:
            explanations.append("Advisory evidence is unavailable; fail closed.")

        return {
            "status": "OK",
            "explanation": explanations,
            "primary_explanation": explanations[0],
            "advisory_only": True,
        }
