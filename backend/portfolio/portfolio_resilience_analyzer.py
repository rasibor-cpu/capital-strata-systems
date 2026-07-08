from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.opportunity_portfolio_ranker import (
    average_correlation,
    exposure_percentages,
    max_bucket_share,
    normalize_opportunities,
)
from backend.portfolio.utils import advisory_response, safe_float


class PortfolioResilienceAnalyzer:
    """Analyze portfolio-level resilience for approved opportunity sets."""

    def analyze(self, opportunities: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
        normalized = normalize_opportunities(opportunities)
        if not normalized:
            return advisory_response(
                "DATA UNAVAILABLE",
                portfolio_quality=0.0,
                resilience=0.0,
                diversification=0.0,
                reasons=["approved_opportunities_unavailable"],
                recommended_actions=["Provide approved opportunities before portfolio resilience analysis."],
                **_empty_payload(),
                **_safety_flags(),
            )

        correlation = average_correlation(normalized)
        exposures = {
            "sector": exposure_percentages(normalized, "sector"),
            "industry": exposure_percentages(normalized, "industry"),
            "country": exposure_percentages(normalized, "country"),
            "currency": exposure_percentages(normalized, "currency"),
            "asset_class": exposure_percentages(normalized, "asset_class"),
            "regime": exposure_percentages(normalized, "regime"),
        }
        factor_exposure = _factor_exposure(normalized)
        liquidity_share = _liquidity_concentration(normalized)
        concentration = max(
            max_bucket_share(normalized, "sector"),
            max_bucket_share(normalized, "industry"),
            max_bucket_share(normalized, "country"),
            max_bucket_share(normalized, "currency"),
            max_bucket_share(normalized, "asset_class"),
            max_bucket_share(normalized, "regime"),
            liquidity_share,
            max(factor_exposure.values()) / 100.0 if factor_exposure else 0.0,
        )
        expected_return = _weighted_average(normalized, "expected_return")
        expected_drawdown = _weighted_average(normalized, "expected_drawdown")
        expected_volatility = _weighted_average(normalized, "expected_volatility")
        beta = _weighted_average(normalized, "beta")

        breadth_bonus = min(
            20.0,
            max(0, len(exposures["asset_class"]) - 1) * 4.0
            + max(0, len(exposures["sector"]) - 1) * 3.0
            + max(0, len(exposures["currency"]) - 1) * 3.0
            + max(0, len(exposures["regime"]) - 1) * 3.0,
        )
        diversification = round(min(100.0, _score_from_penalties(concentration * 45.0 + correlation * 25.0) + breadth_bonus), 6)
        concentration_score = round(max(0.0, min(100.0, concentration * 100.0)), 6)
        resilience = _score_from_penalties(expected_drawdown * 2.0 + expected_volatility * 1.0 + correlation * 20.0 + max(0.0, beta - 1.0) * 20.0)
        expected_stability = _score_from_penalties(expected_volatility * 1.5 + expected_drawdown * 2.0 + correlation * 15.0)
        portfolio_quality = round(
            max(
                0.0,
                min(
                    100.0,
                    diversification * 0.30
                    + resilience * 0.30
                    + expected_stability * 0.20
                    + max(0.0, min(100.0, expected_return * 8.0)) * 0.20,
                ),
            ),
            6,
        )

        return advisory_response(
            "OK",
            portfolio_quality=portfolio_quality,
            resilience=resilience,
            diversification=diversification,
            concentration_score=concentration_score,
            expected_stability=expected_stability,
            overall_portfolio_intelligence_score=portfolio_quality,
            expected_return=round(expected_return, 6),
            expected_drawdown=round(expected_drawdown, 6),
            expected_volatility=round(expected_volatility, 6),
            portfolio_beta=round(beta, 6),
            portfolio_correlation=correlation,
            liquidity_concentration=round(liquidity_share * 100.0, 6),
            exposures=exposures,
            factor_exposure=factor_exposure,
            portfolio_diversification={
                "opportunity_count": len(normalized),
                "asset_class_count": len(exposures["asset_class"]),
                "sector_count": len(exposures["sector"]),
                "currency_count": len(exposures["currency"]),
                "regime_count": len(exposures["regime"]),
            },
            recommendations=_recommendations(concentration, correlation, exposures, factor_exposure, diversification),
            reasons=["portfolio_resilience_metrics_computed"],
            **_safety_flags(),
        )


def _weighted_average(opportunities: list[Mapping[str, Any]], key: str) -> float:
    total_weight = sum(max(0.0, safe_float(item.get("weight"), 1.0)) for item in opportunities)
    if total_weight <= 0.0:
        return 0.0
    return sum(safe_float(item.get(key)) * max(0.0, safe_float(item.get("weight"), 1.0)) for item in opportunities) / total_weight


def _factor_exposure(opportunities: list[Mapping[str, Any]]) -> dict[str, float]:
    total_weight = sum(max(0.0, safe_float(item.get("weight"), 1.0)) for item in opportunities)
    if total_weight <= 0.0:
        return {}
    factors: dict[str, float] = {}
    for item in opportunities:
        weight = max(0.0, safe_float(item.get("weight"), 1.0))
        for factor in item.get("factor_exposure", []):
            factors[factor] = factors.get(factor, 0.0) + weight
    return {key: round((value / total_weight) * 100.0, 6) for key, value in sorted(factors.items())}


def _liquidity_concentration(opportunities: list[Mapping[str, Any]]) -> float:
    total_weight = sum(max(0.0, safe_float(item.get("weight"), 1.0)) for item in opportunities)
    if total_weight <= 0.0:
        return 0.0
    low_liquidity = sum(
        max(0.0, safe_float(item.get("weight"), 1.0))
        for item in opportunities
        if safe_float(item.get("liquidity_score"), 50.0) < 40.0
    )
    return low_liquidity / total_weight


def _score_from_penalties(penalty: float) -> float:
    return round(max(0.0, min(100.0, 100.0 - penalty)), 6)


def _recommendations(
    concentration: float,
    correlation: float,
    exposures: Mapping[str, Mapping[str, float]],
    factor_exposure: Mapping[str, float],
    diversification: float,
) -> list[str]:
    recommendations: list[str] = []
    for label, values in exposures.items():
        if values:
            top_name, top_value = max(values.items(), key=lambda item: item[1])
            if top_value > 60.0:
                recommendations.append(f"Reduce {top_name} {label.replace('_', ' ')} exposure")
    if factor_exposure:
        factor_name, factor_value = max(factor_exposure.items(), key=lambda item: item[1])
        if factor_value > 60.0:
            recommendations.append(f"Reduce {factor_name} factor concentration")
    if correlation > 0.60:
        recommendations.append("Reduce correlation")
    if concentration > 0.60:
        recommendations.append("Over-concentrated portfolio")
    if diversification < 55.0:
        recommendations.append("Insufficient diversification")
    if not recommendations:
        recommendations.append("Preferred portfolio has institutional-quality diversification.")
    return sorted(dict.fromkeys(recommendations))


def _empty_payload() -> dict[str, Any]:
    return {
        "concentration_score": 0.0,
        "expected_stability": 0.0,
        "overall_portfolio_intelligence_score": 0.0,
        "expected_return": 0.0,
        "expected_drawdown": 0.0,
        "expected_volatility": 0.0,
        "portfolio_beta": 0.0,
        "portfolio_correlation": 0.0,
        "liquidity_concentration": 0.0,
        "exposures": {},
        "factor_exposure": {},
        "portfolio_diversification": {},
    }


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
    }
