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
        if strategy == "COVERED_CALL":
            return self._covered_call(strategy_payload)

        if strategy == "CASH_SECURED_PUT":
            return self._cash_secured_put(strategy_payload)

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

    def _covered_call(self, payload: Dict) -> Dict:
        max_profit = float(payload.get("maximum_profit", payload.get("max_profit", 0)) or 0)
        downside = float(payload.get("downside_exposure", 0) or 0)
        rr_ratio = round(max_profit / downside, 4) if downside > 0 else 0
        return {
            "strategy": "COVERED_CALL",
            "risk_reward_ratio": rr_ratio,
            "capped_risk": False,
            "capped_profit": True,
            "strategy_risk_grade": self._grade_strategy(rr_ratio, downside),
            "collateral_type": payload.get("collateral_type", "UNDERLYING_SHARES"),
            "assignment_exposure": payload.get("assignment_exposure", {}),
            "advisory_only": True,
            "execution_allowed": False,
        }

    def _cash_secured_put(self, payload: Dict) -> Dict:
        max_profit = float(payload.get("maximum_profit", payload.get("max_profit", 0)) or 0)
        max_loss = float(payload.get("maximum_loss", payload.get("max_loss", 0)) or 0)
        rr_ratio = round(max_profit / max_loss, 4) if max_loss > 0 else 0
        return {
            "strategy": "CASH_SECURED_PUT",
            "risk_reward_ratio": rr_ratio,
            "capped_risk": True,
            "capped_profit": True,
            "strategy_risk_grade": self._grade_strategy(rr_ratio, max_loss),
            "collateral_type": payload.get("collateral_type", "CASH"),
            "assignment_exposure": payload.get("assignment_exposure", {}),
            "advisory_only": True,
            "execution_allowed": False,
        }
