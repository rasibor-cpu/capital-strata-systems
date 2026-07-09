from __future__ import annotations

from typing import Any


class BrokerOperationalRecommendations:
    """Computes operational actions and staging gate decisions for the broker certification framework."""

    def evaluate_recommendations(
        self,
        *,
        overall_state: str,
        safety_rating: str,
        scorecard: dict[str, Any],
        blockers: list[str],
    ) -> dict[str, Any]:
        # Determine overall_recommendation based on decision matrix
        rec = "NO_GO"
        if overall_state == "GREEN" and safety_rating == "GREEN":
            rec = "GO"
        elif overall_state == "AMBER" and safety_rating == "GREEN":
            rec = "GO_READ_ONLY"
        elif overall_state == "AMBER" and safety_rating == "AMBER":
            rec = "AMBER"
        else:
            rec = "NO_GO"

        # Generate standard actions list
        actions = []
        next_action = "Staging validations complete. Proceed to read-only pilot deployment."

        if rec == "NO_GO":
            next_action = "Return to engineering to resolve critical broker failures and blockers."
            actions.append("Resolve credentials or bootstrap blocker warnings before staging pilot.")
        elif rec == "GO_READ_ONLY":
            next_action = "Elevated latency detected. Staging is authorized for read-only advisory monitoring."
            actions.append("Broker operational but latency is elevated; continue read-only monitoring before live validation.")
        elif rec == "AMBER":
            next_action = "Review safety and firewalls. Verify marginal latency metrics."
            actions.append("Verify sandbox firewall bounds before staging validation.")
        else:
            actions.append("Proceed to operational broker staging pilot validation.")

        return {
            "overall_recommendation": rec,
            "recommendations": actions,
            "next_recommended_action": next_action,
        }
