from __future__ import annotations
from typing import Dict


class OptionRiskProfileEngine:
    """
    Computes risk profile metrics for options strategies.

    Metrics:
    - risk_reward_ratio
    - capped_risk
    - capped_profit
    - strategy_risk_grade
    """

    def __init__(self):
        pass

    def evaluate(self, strategy_payload: Dict) -> Dict:
        strategy = strategy_payload.get("strategy")
        max_profit = strategy_payload.get("max_profit", 0)
        max_loss = strategy_payload.get("max_loss", 0)

        # Unlimited profit normalization
        if max_profit == "UNLIMITED":
            rr_ratio = 9.99
            capped_profit = False
        else:
            rr_ratio = (
                round(max_profit / max_loss, 4)
                if max_loss > 0 else 0
            )
            capped_profit = True

        capped_risk = True

        grade = self._grade_strategy(rr_ratio, max_loss)

        return {
            "strategy": strategy,
            "risk_reward_ratio": rr_ratio,
            "capped_risk": capped_risk,
            "capped_profit": capped_profit,
            "strategy_risk_grade": grade
        }

    def _grade_strategy(self, rr_ratio: float, max_loss: float) -> str:
        """
        Assign strategy grade.
        """

        if rr_ratio >= 3.0:
            return "ELITE"

        if rr_ratio >= 1.8:
            return "STRONG"

        if rr_ratio >= 1.0:
            return "MODERATE"

        return "DEFENSIVE"