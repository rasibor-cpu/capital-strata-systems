from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from backend.options.options_greeks_aggregator import OptionsGreeksAggregator
from backend.options.options_income_assignment_risk import OptionsIncomeAssignmentRiskAnalyzer
from backend.options.options_income_constraints import SUPPORTED_INCOME_STRATEGIES
from backend.options.options_income_risk_budget import OptionsIncomeRiskBudgetConfig, OptionsIncomeRiskBudgetEngine
from backend.options.options_income_risk_limits import OptionsIncomeRiskLimitEngine
from backend.options.options_income_stress_testing import OptionsIncomeStressTester
from backend.options.options_income_volatility_risk import OptionsIncomeVolatilityRiskAnalyzer
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeRiskGovernanceError(ValueError):
    """Raised when options income risk governance fails closed."""


@dataclass(frozen=True)
class OptionsIncomeRiskGovernanceAssessment:
    assessment_id: str
    portfolio_risk_status: str
    approval_status: str
    risk_score: float
    limit_breaches: list[str]
    warnings: list[str]
    unavailable_data: list[str]
    stress_summary: dict[str, Any]
    assignment_summary: dict[str, Any]
    greeks_summary: dict[str, Any]
    volatility_summary: dict[str, Any]
    risk_budgets: dict[str, Any]
    advisory_recommendations: list[dict[str, Any]]
    paper_only: bool = True
    advisory_only: bool = True
    execution_allowed: bool = False
    live_trading_blocked: bool = True
    broker_execution_armed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, **SAFE_FLAGS}


class OptionsIncomeRiskGovernanceEngine:
    def __init__(
        self,
        *,
        config: OptionsIncomeRiskBudgetConfig | None = None,
        greeks: OptionsGreeksAggregator | None = None,
        assignment: OptionsIncomeAssignmentRiskAnalyzer | None = None,
        volatility: OptionsIncomeVolatilityRiskAnalyzer | None = None,
        stress: OptionsIncomeStressTester | None = None,
    ) -> None:
        self.config = config or OptionsIncomeRiskBudgetConfig()
        self.greeks = greeks or OptionsGreeksAggregator()
        self.assignment = assignment or OptionsIncomeAssignmentRiskAnalyzer()
        self.volatility = volatility or OptionsIncomeVolatilityRiskAnalyzer()
        self.stress = stress or OptionsIncomeStressTester()
        self.budgets = OptionsIncomeRiskBudgetEngine(self.config)
        self.limits = OptionsIncomeRiskLimitEngine(self.config)

    def assess(
        self,
        portfolio: Mapping[str, Any],
        *,
        greeks_by_symbol: Mapping[str, Mapping[str, Any]] | None,
        iv_by_symbol: Mapping[str, Any] | None,
        market_data_by_underlying: Mapping[str, Mapping[str, Any]] | None = None,
        volatility_regime: str = "UNKNOWN",
    ) -> OptionsIncomeRiskGovernanceAssessment:
        _validate_portfolio(portfolio)
        capital = float(portfolio.get("capital", {}).get("allocated_capital", 0.0) or 0.0)
        greeks = self.greeks.aggregate(portfolio, greeks_by_symbol=greeks_by_symbol, total_capital=capital).to_dict()
        assignment = self.assignment.analyze(portfolio, market_data_by_underlying=market_data_by_underlying).to_dict()
        volatility = self.volatility.analyze(portfolio, iv_by_symbol=iv_by_symbol, greeks=greeks, volatility_regime=volatility_regime).to_dict()
        stress = self.stress.run(portfolio, greeks=greeks, assignment=assignment, max_loss_pct_limit=self.config.max_stressed_loss_pct).to_dict()
        budgets = self.budgets.evaluate(
            greeks=greeks,
            diversification=portfolio.get("diversification", {}),
            capital=portfolio.get("capital", {}),
            assignment=assignment,
            volatility=volatility,
            stress=stress,
        )
        limits = self.limits.evaluate(budgets).to_dict()
        unavailable = sorted(set(greeks.get("unavailable", []) + volatility.get("unavailable", [])))
        warnings = []
        if limits["advisory_breaches"]:
            warnings.extend(limits["advisory_breaches"])
        if unavailable:
            warnings.append("Insufficient data")
        if limits["hard_breaches"]:
            approval = "REJECTED_RISK_LIMIT"
        elif unavailable:
            approval = "REJECTED_INVALID_DATA"
        elif warnings:
            approval = "APPROVED_WITH_WARNINGS"
        else:
            approval = "APPROVED_PAPER"
        status = "RED" if approval.startswith("REJECTED") else ("AMBER" if warnings else "GREEN")
        risk_score = _risk_score(limits["status"], stress["max_estimated_loss_pct"], assignment["portfolio_assignment_ratio"], warnings)
        recommendations = _recommendations(limits, assignment, volatility, stress, warnings)
        return OptionsIncomeRiskGovernanceAssessment(
            assessment_id=_assessment_id(portfolio),
            portfolio_risk_status=status,
            approval_status=approval,
            risk_score=risk_score,
            limit_breaches=limits["hard_breaches"],
            warnings=sorted(set(warnings)),
            unavailable_data=unavailable,
            stress_summary={"status": stress["status"], "max_estimated_loss": stress["max_estimated_loss"], "max_estimated_loss_pct": stress["max_estimated_loss_pct"]},
            assignment_summary=assignment,
            greeks_summary=greeks,
            volatility_summary=volatility,
            risk_budgets=budgets,
            advisory_recommendations=recommendations,
        )


def _validate_portfolio(portfolio: Mapping[str, Any]) -> None:
    if not isinstance(portfolio, Mapping) or not portfolio.get("allocations"):
        raise OptionsIncomeRiskGovernanceError("Missing portfolio")
    if portfolio.get("execution_allowed") is not False or portfolio.get("live_trading_blocked") is not True:
        raise OptionsIncomeRiskGovernanceError("Execution-enabled posture is invalid")
    seen: set[str] = set()
    for row in portfolio.get("allocations", []):
        allocation_id = str(row.get("allocation_id") or "").strip()
        if not allocation_id:
            raise OptionsIncomeRiskGovernanceError("Allocation missing identifier")
        if allocation_id in seen:
            raise OptionsIncomeRiskGovernanceError("Duplicate allocation")
        seen.add(allocation_id)
        if str(row.get("strategy") or "").strip().upper() not in SUPPORTED_INCOME_STRATEGIES:
            raise OptionsIncomeRiskGovernanceError("Unsupported strategy")
        if float(row.get("collateral", 0.0) or 0.0) < 0.0:
            raise OptionsIncomeRiskGovernanceError("Negative collateral")
        if str(row.get("current_state") or "").strip().upper() == "COMPLETED":
            raise OptionsIncomeRiskGovernanceError("Completed positions cannot be assessed as active")


def _risk_score(limit_status: str, stressed_loss_pct: float, assignment_ratio: float, warnings: list[str]) -> float:
    base = 92.0
    if limit_status == "RED":
        base -= 45.0
    elif limit_status == "AMBER":
        base -= 18.0
    base -= min(25.0, stressed_loss_pct * 100.0)
    base -= min(15.0, assignment_ratio * 20.0)
    base -= min(10.0, len(warnings) * 2.5)
    return round(max(0.0, min(100.0, base)), 6)


def _recommendations(limits: Mapping[str, Any], assignment: Mapping[str, Any], volatility: Mapping[str, Any], stress: Mapping[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    breaches = set(limits.get("hard_breaches", []) + limits.get("advisory_breaches", []))
    if "single_underlying_exposure" in breaches:
        recs.append(_rec("Reduce underlying concentration", "Underlying concentration is above budget."))
    if "single_expiry_exposure" in breaches:
        recs.append(_rec("Reduce expiry concentration", "Expiry concentration is above budget."))
    if "assignment_exposure" in breaches or float(assignment.get("portfolio_assignment_ratio", 0.0) or 0.0) > 0.45:
        recs.append(_rec("Reduce assignment exposure", "Assignment exposure is elevated."))
    if "collateral_utilization" in breaches:
        recs.append(_rec("Reduce collateral utilization", "Collateral utilization breached hard limit."))
    if "theta" in breaches:
        recs.append(_rec("Increase theta efficiency", "Theta income is below minimum."))
    if volatility.get("status") == "UNAVAILABLE":
        recs.append(_rec("Insufficient data", "Implied volatility is unavailable."))
    elif "volatility_exposure" in breaches:
        recs.append(_rec("Reduce vega exposure", "Volatility exposure is above budget."))
    if stress.get("status") == "RED":
        recs.append(_rec("Decrease portfolio size", "Stress loss breached limit."))
    if warnings and not recs:
        recs.append(_rec("Rebalance portfolio", "Warnings require paper portfolio rebalance review."))
    if not recs:
        recs.append(_rec("Maintain portfolio", "Risk governance is within paper limits."))
    return recs


def _rec(action: str, reason: str) -> dict[str, Any]:
    return {"action": action, "reason": reason, **SAFE_FLAGS}


def _assessment_id(portfolio: Mapping[str, Any]) -> str:
    portfolio_id = str(portfolio.get("portfolio_id") or "UNKNOWN").strip()
    allocation_ids = "-".join(sorted(str(row.get("allocation_id") or "") for row in portfolio.get("allocations", [])))
    digest = sha256(allocation_ids.encode("utf-8")).hexdigest()[:16]
    return f"OI007-{portfolio_id}-{digest}"


__all__ = ["OptionsIncomeRiskGovernanceAssessment", "OptionsIncomeRiskGovernanceEngine", "OptionsIncomeRiskGovernanceError"]
