from __future__ import annotations

from typing import Any, Mapping


class BrokerOperationalScorecard:
    """Calculates weighted operational readiness scorecard ratings for configured brokers."""

    # Weights sum to 100%
    WEIGHTS = {
        "credentials": 10.0,
        "bootstrap": 10.0,
        "authentication": 15.0,
        "account_access": 10.0,
        "market_data": 15.0,
        "latency": 15.0,
        "health": 10.0,
        "availability_reliability": 5.0,
        "safety": 10.0,
    }

    def compute_score(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        scores = {}
        
        # Helper to convert PASS/GREEN to 100, AMBER to 50, FAIL/RED/UNKNOWN to 0
        def get_val_score(status: str | None) -> float:
            if not status:
                return 0.0
            status_str = str(status).upper()
            if status_str in {"PASS", "GREEN", "OK"}:
                return 100.0
            if status_str in {"AMBER", "PARTIAL", "WARNING", "CONDITIONAL"}:
                return 50.0
            return 0.0

        # Score individual components
        scores["credentials"] = get_val_score(evidence.get("credentials"))
        scores["bootstrap"] = get_val_score(evidence.get("bootstrap"))
        scores["authentication"] = get_val_score(evidence.get("authentication"))
        scores["account_access"] = get_val_score(evidence.get("account_access"))
        scores["market_data"] = get_val_score(evidence.get("market_data"))
        scores["latency"] = get_val_score(evidence.get("latency"))
        scores["health"] = get_val_score(evidence.get("health"))
        scores["availability_reliability"] = get_val_score(evidence.get("availability_reliability"))
        scores["safety"] = get_val_score(evidence.get("safety"))

        # Compute weighted sum
        total_score = 0.0
        for key, weight in self.WEIGHTS.items():
            total_score += (scores.get(key, 0.0) * weight) / 100.0

        # Compute derived dimensional ratings
        technical_score = (scores["credentials"] + scores["bootstrap"]) / 2.0
        technical_rating = self._rating_for_score(technical_score)

        operational_score = (scores["authentication"] + scores["account_access"] + scores["market_data"] + scores["latency"]) / 4.0
        operational_rating = self._rating_for_score(operational_score)

        health_score = (scores["health"] + scores["availability_reliability"]) / 2.0
        health_rating = self._rating_for_score(health_score)

        safety_score = scores["safety"]
        safety_rating = self._rating_for_score(safety_score)

        # Derived production readiness rating
        production_rating = self._rating_for_score(total_score)
        if safety_rating == "RED" or technical_rating == "RED":
            production_rating = "NOT_READY"

        return {
            "overall_score": round(total_score, 1),
            "technical_readiness": technical_rating,
            "operational_readiness": operational_rating,
            "health_readiness": health_rating,
            "safety_readiness": safety_rating,
            "production_readiness": production_rating,
            "component_scores": scores,
        }

    @staticmethod
    def _rating_for_score(score: float) -> str:
        if score >= 90.0:
            return "GREEN"
        if score >= 60.0:
            return "AMBER"
        return "RED"
