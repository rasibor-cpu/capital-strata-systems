from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeStressTestingError(ValueError):
    """Raised when paper stress testing cannot be computed."""


@dataclass(frozen=True)
class StressTestingReport:
    scenarios: list[dict[str, Any]]
    max_estimated_loss: float
    max_estimated_loss_pct: float
    max_estimated_gain: float
    status: str
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, **SAFE_FLAGS}


class OptionsIncomeStressTester:
    SCENARIOS = (
        ("Underlying down 5%", -0.05, 0.0),
        ("Underlying down 10%", -0.10, 0.0),
        ("Underlying down 20%", -0.20, 0.0),
        ("Underlying up 5%", 0.05, 0.0),
        ("Underlying up 10%", 0.10, 0.0),
        ("Volatility up", 0.0, 0.20),
        ("Volatility down", 0.0, -0.20),
        ("Combined downside plus volatility expansion", -0.10, 0.25),
        ("Combined upside plus volatility contraction", 0.10, -0.20),
        ("Near-expiry adverse move", -0.08, 0.10),
        ("Assignment concentration event", -0.12, 0.15),
    )

    def run(self, portfolio: Mapping[str, Any], *, greeks: Mapping[str, Any], assignment: Mapping[str, Any], max_loss_pct_limit: float = 0.12) -> StressTestingReport:
        capital = float(portfolio.get("capital", {}).get("allocated_capital", 0.0) or 0.0)
        if capital <= 0.0:
            raise OptionsIncomeStressTestingError("Portfolio capital must be positive")
        rows = list(portfolio.get("allocations", []) or [])
        delta = float(greeks.get("portfolio", {}).get("delta", 0.0) or 0.0)
        gamma = float(greeks.get("portfolio", {}).get("gamma", 0.0) or 0.0)
        vega = float(greeks.get("portfolio", {}).get("vega", 0.0) or 0.0)
        scenarios: list[dict[str, Any]] = []
        for name, move, vol_move in self.SCENARIOS:
            premium = sum(float(row.get("expected_premium", 0.0) or 0.0) for row in rows) * (-abs(move) * 0.35 if move < 0 else abs(move) * 0.20)
            collateral = capital * abs(move) * (0.35 if move < 0 else 0.18)
            assignment_impact = float(assignment.get("assignment_notional", 0.0) or 0.0) * abs(move) * (0.40 if "Assignment" in name else 0.12)
            greeks_impact = (delta * move) + (0.5 * gamma * move * move) + (vega * vol_move)
            pnl = premium - collateral - assignment_impact + greeks_impact
            estimated_loss = max(0.0, -pnl)
            estimated_gain = max(0.0, pnl)
            status = "RED" if estimated_loss / capital > max_loss_pct_limit else ("AMBER" if estimated_loss / capital > max_loss_pct_limit * 0.75 else "GREEN")
            scenarios.append(
                {
                    "scenario_name": name,
                    "portfolio_value_impact": round(pnl, 6),
                    "premium_impact": round(premium, 6),
                    "collateral_impact": round(collateral, 6),
                    "assignment_impact": round(assignment_impact, 6),
                    "greeks_impact": round(greeks_impact, 6),
                    "estimated_loss": round(estimated_loss, 6),
                    "estimated_gain": round(estimated_gain, 6),
                    "limit_status": status,
                    "affected_positions": [row.get("allocation_id") for row in rows],
                    "advisory_reasons": [] if status == "GREEN" else ["stress loss approaches or breaches limit"],
                    "approximation_flags": ["DETERMINISTIC_LINEAR_GREEKS_APPROXIMATION"],
                    **SAFE_FLAGS,
                }
            )
        max_loss = max(row["estimated_loss"] for row in scenarios)
        max_gain = max(row["estimated_gain"] for row in scenarios)
        overall = "RED" if any(row["limit_status"] == "RED" for row in scenarios) else ("AMBER" if any(row["limit_status"] == "AMBER" for row in scenarios) else "GREEN")
        return StressTestingReport(scenarios, round(max_loss, 6), round(max_loss / capital, 8), round(max_gain, 6), overall)


__all__ = ["OptionsIncomeStressTester", "OptionsIncomeStressTestingError", "StressTestingReport"]
