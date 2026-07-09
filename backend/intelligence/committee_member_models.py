from __future__ import annotations

from typing import Any, Mapping
from backend.common.numeric_utils import safe_float


class CommitteeMember:
    """Base class for investment committee members with specific institutional viewpoints."""

    def __init__(self, name: str, role: str) -> None:
        self.name = name
        self.role = role

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        """Score the 9 dimensions of a portfolio scenario."""
        raise NotImplementedError

    def vote(self, scores: dict[str, float]) -> str:
        """Cast a vote based on the scoring profiles."""
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        if avg_score >= 92.0:
            return "Strong Approve"
        elif avg_score >= 75.0:
            return "Approve"
        elif avg_score >= 60.0:
            return "Conditional Approve"
        elif avg_score >= 45.0:
            return "Needs Review"
        else:
            return "Reject"


class ChiefInvestmentOfficer(CommitteeMember):
    """Chief Investment Officer (CIO) - Cares about portfolio quality and capital efficiency."""

    def __init__(self) -> None:
        super().__init__("Chief Investment Officer", "CIO")

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        ctx = context or {}
        confidence = safe_float(ctx.get("confidence", 80.0))
        ret = safe_float(portfolio.get("expected_return", 0.0))
        dd = safe_float(portfolio.get("expected_drawdown", 0.0))
        con = safe_float(portfolio.get("concentration_score", 0.0))

        return {
            "Expected return": max(0.0, min(100.0, ret * 4.0)),
            "Risk": max(0.0, min(100.0, 100.0 - dd * 3.0)),
            "Diversification": safe_float(portfolio.get("diversification_score", 50.0)),
            "Portfolio quality": safe_float(portfolio.get("portfolio_quality_score", 50.0)),
            "Capital efficiency": safe_float(portfolio.get("capital_efficiency_score", 50.0)),
            "Resilience": safe_float(portfolio.get("resilience_score", 50.0)),
            "Confidence": confidence,
            "Liquidity": max(0.0, min(100.0, 100.0 - con * 0.5)),
            "Governance": 100.0 if bool(portfolio.get("advisory_only", True)) else 50.0,
        }


class ChiefRiskOfficer(CommitteeMember):
    """Chief Risk Officer (CRO) - Focuses on drawdown, concentration, and resilience."""

    def __init__(self) -> None:
        super().__init__("Chief Risk Officer", "CRO")

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        ctx = context or {}
        confidence = safe_float(ctx.get("confidence", 80.0))
        ret = safe_float(portfolio.get("expected_return", 0.0))
        vol = safe_float(portfolio.get("expected_volatility", 0.0))
        dd = safe_float(portfolio.get("expected_drawdown", 0.0))
        con = safe_float(portfolio.get("concentration_score", 0.0))

        # Check for extreme risk flags in context
        risk_penalty = 0.0
        if ctx.get("broker_health") == "RED":
            risk_penalty = 50.0

        return {
            "Expected return": max(0.0, min(100.0, ret * 3.0)),
            "Risk": max(0.0, min(100.0, 100.0 - dd * 4.0 - vol * 1.5 - risk_penalty)),
            "Diversification": safe_float(portfolio.get("diversification_score", 50.0)),
            "Portfolio quality": safe_float(portfolio.get("portfolio_quality_score", 50.0)) * 0.9,
            "Capital efficiency": safe_float(portfolio.get("capital_efficiency_score", 50.0)) * 0.8,
            "Resilience": max(0.0, min(100.0, safe_float(portfolio.get("resilience_score", 50.0)) * 1.1)),
            "Confidence": confidence * 0.9,
            "Liquidity": max(0.0, min(100.0, 100.0 - con * 1.2)),
            "Governance": 100.0 if (bool(portfolio.get("advisory_only", True)) and not bool(portfolio.get("execution_allowed", False))) else 0.0,
        }


class PortfolioManager(CommitteeMember):
    """Portfolio Manager (PM) - Focuses on expected returns and opportunity quality."""

    def __init__(self) -> None:
        super().__init__("Portfolio Manager", "PM")

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        ctx = context or {}
        confidence = safe_float(ctx.get("confidence", 80.0))
        ret = safe_float(portfolio.get("expected_return", 0.0))
        dd = safe_float(portfolio.get("expected_drawdown", 0.0))

        return {
            "Expected return": max(0.0, min(100.0, ret * 4.5)),
            "Risk": max(0.0, min(100.0, 100.0 - dd * 2.0)),
            "Diversification": max(0.0, min(100.0, safe_float(portfolio.get("diversification_score", 50.0)) * 1.05)),
            "Portfolio quality": max(0.0, min(100.0, safe_float(portfolio.get("portfolio_quality_score", 50.0)) * 1.05)),
            "Capital efficiency": safe_float(portfolio.get("capital_efficiency_score", 50.0)),
            "Resilience": safe_float(portfolio.get("resilience_score", 50.0)),
            "Confidence": max(0.0, min(100.0, confidence * 1.05)),
            "Liquidity": 85.0,
            "Governance": 90.0 if bool(portfolio.get("advisory_only", True)) else 40.0,
        }


class HeadOfTrading(CommitteeMember):
    """Head of Trading - Cares about execution practicality, liquidity, and slippage."""

    def __init__(self) -> None:
        super().__init__("Head of Trading", "Trading")

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        ctx = context or {}
        ret = safe_float(portfolio.get("expected_return", 0.0))

        # Check broker status
        broker_status = str(ctx.get("broker_health", "GREEN")).upper()
        broker_score = 100.0 if broker_status == "GREEN" else (60.0 if broker_status == "AMBER" else 20.0)

        # Average liquidity score of constituent opportunities
        opps = portfolio.get("opportunities", [])
        liq_sum = 0.0
        count = 0
        for opp in opps:
            liq_sum += safe_float(opp.get("liquidity_score", 70.0))
            count += 1
        avg_liq = (liq_sum / count) if count > 0 else 75.0

        return {
            "Expected return": max(0.0, min(100.0, ret * 3.0)),
            "Risk": broker_score,
            "Diversification": safe_float(portfolio.get("diversification_score", 50.0)),
            "Portfolio quality": safe_float(portfolio.get("portfolio_quality_score", 50.0)),
            "Capital efficiency": safe_float(portfolio.get("capital_efficiency_score", 50.0)),
            "Resilience": safe_float(portfolio.get("resilience_score", 50.0)),
            "Confidence": 75.0,
            "Liquidity": avg_liq,
            "Governance": 100.0 if bool(portfolio.get("advisory_only", True)) else 50.0,
        }


class QuantitativeResearchLead(CommitteeMember):
    """Quantitative Research Lead - Cares about statistical edge and confidence."""

    def __init__(self) -> None:
        super().__init__("Quantitative Research Lead", "Quant")

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        ctx = context or {}
        confidence = safe_float(ctx.get("confidence", 80.0))
        ret = safe_float(portfolio.get("expected_return", 0.0))
        vol = safe_float(portfolio.get("expected_volatility", 0.0))

        return {
            "Expected return": max(0.0, min(100.0, ret * 3.5)),
            "Risk": max(0.0, min(100.0, 100.0 - vol * 2.0)),
            "Diversification": safe_float(portfolio.get("diversification_score", 50.0)),
            "Portfolio quality": safe_float(portfolio.get("portfolio_quality_score", 50.0)),
            "Capital efficiency": safe_float(portfolio.get("capital_efficiency_score", 50.0)),
            "Resilience": safe_float(portfolio.get("resilience_score", 50.0)),
            "Confidence": confidence,
            "Liquidity": 80.0,
            "Governance": 100.0 if bool(portfolio.get("advisory_only", True)) else 50.0,
        }


class GovernanceCompliance(CommitteeMember):
    """Governance & Compliance - Verifies policy boundaries and execution gates."""

    def __init__(self) -> None:
        super().__init__("Governance & Compliance", "Compliance")

    def score_portfolio(
        self,
        portfolio: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, float]:
        # Cares strictly about advisory status
        advisory_only = bool(portfolio.get("advisory_only", True))
        execution_allowed = bool(portfolio.get("execution_allowed", False))

        gov_score = 100.0 if (advisory_only and not execution_allowed) else 0.0

        return {
            "Expected return": gov_score,
            "Risk": gov_score,
            "Diversification": gov_score,
            "Portfolio quality": gov_score,
            "Capital efficiency": gov_score,
            "Resilience": gov_score,
            "Confidence": gov_score,
            "Liquidity": gov_score,
            "Governance": gov_score,
        }
