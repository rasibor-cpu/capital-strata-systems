from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.utils import advisory_response, safe_float


class OpportunityPortfolioRanker:
    """Rank already-approved opportunities by portfolio contribution."""

    def rank(
        self,
        opportunities: Iterable[Mapping[str, Any]] | None,
        *,
        existing_portfolio: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_opportunities(opportunities)
        if not normalized:
            return advisory_response(
                "DATA UNAVAILABLE",
                ranked_opportunities=[],
                reasons=["approved_opportunities_unavailable"],
                recommended_actions=["Provide already-approved opportunities before portfolio construction analysis."],
                **_safety_flags(),
            )

        base = normalize_opportunities(existing_portfolio)
        ranked = [self._rank_one(item, normalized, base) for item in normalized]
        ranked.sort(key=lambda row: (-row["portfolio_contribution_score"], row["opportunity_id"]))
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index

        return advisory_response(
            "OK",
            ranked_opportunities=ranked,
            top_opportunity=ranked[0]["opportunity_id"] if ranked else "DATA UNAVAILABLE",
            reasons=["portfolio_contribution_ranking_computed"],
            recommended_actions=["Use ranking as advisory portfolio construction evidence only."],
            **_safety_flags(),
        )

    def _rank_one(
        self,
        opportunity: Mapping[str, Any],
        universe: list[dict[str, Any]],
        existing: list[dict[str, Any]],
    ) -> dict[str, Any]:
        peers = [item for item in universe if item["opportunity_id"] != opportunity["opportunity_id"]]
        comparison = existing + peers
        average_correlation = average_pairwise_correlation([opportunity], comparison)
        concentration_after = max_bucket_share(existing + universe, "asset_class")
        factor_overlap = max_factor_overlap(opportunity, comparison)
        liquidity = safe_float(opportunity.get("liquidity_score"), 50.0)
        expected_return = safe_float(opportunity.get("expected_return"))
        expected_drawdown = safe_float(opportunity.get("expected_drawdown"))
        volatility = safe_float(opportunity.get("expected_volatility"))
        beta = abs(safe_float(opportunity.get("beta"), 1.0))

        diversification_contribution = 100.0 - max(average_correlation * 100.0, concentration_after * 100.0, factor_overlap * 100.0)
        risk_reduction = 100.0 - min(100.0, expected_drawdown * 5.0 + volatility * 3.0 + max(0.0, beta - 1.0) * 25.0)
        return_contribution = max(0.0, min(100.0, expected_return * 5.0))
        resilience = max(0.0, min(100.0, risk_reduction * 0.45 + diversification_contribution * 0.35 + liquidity * 0.20))
        score = max(
            0.0,
            min(
                100.0,
                return_contribution * 0.25
                + diversification_contribution * 0.35
                + risk_reduction * 0.20
                + resilience * 0.20,
            ),
        )

        return {
            "opportunity_id": opportunity["opportunity_id"],
            "symbol": opportunity["symbol"],
            "strategy": opportunity["strategy"],
            "asset_class": opportunity["asset_class"],
            "sector": opportunity["sector"],
            "currency": opportunity["currency"],
            "expected_return_contribution": round(return_contribution, 6),
            "portfolio_diversification_contribution": round(diversification_contribution, 6),
            "risk_reduction_contribution": round(risk_reduction, 6),
            "correlation_reduction_contribution": round((1.0 - average_correlation) * 100.0, 6),
            "expected_drawdown": round(expected_drawdown, 6),
            "portfolio_resilience_contribution": round(resilience, 6),
            "marginal_risk_contribution": round(expected_drawdown + volatility + average_correlation * 10.0, 6),
            "marginal_return_contribution": round(expected_return, 6),
            "portfolio_contribution_score": round(score, 6),
            "advisory_only": True,
            "execution_allowed": False,
        }


def normalize_opportunities(opportunities: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if opportunities is None or isinstance(opportunities, (str, bytes)):
        return []
    normalized: list[dict[str, Any]] = []
    try:
        iterator = iter(opportunities)
    except TypeError:
        return []
    for index, row in enumerate(iterator, start=1):
        if not isinstance(row, Mapping):
            continue
        payload = _flatten(row)
        opportunity_id = str(
            payload.get("opportunity_id")
            or payload.get("proposal_id")
            or payload.get("id")
            or payload.get("symbol")
            or f"opportunity_{index}"
        )
        approved = _approved(payload)
        if not approved:
            continue
        normalized.append(
            {
                "opportunity_id": opportunity_id,
                "symbol": _text(payload, "symbol", "asset", default=opportunity_id).upper(),
                "strategy": _text(payload, "strategy", "strategy_id", default="UNKNOWN"),
                "sector": _text(payload, "sector", default="UNKNOWN").upper(),
                "industry": _text(payload, "industry", default="UNKNOWN").upper(),
                "country": _text(payload, "country", default="UNKNOWN").upper(),
                "currency": _text(payload, "currency", "quote_currency", default=_currency_from_symbol(payload)).upper(),
                "asset_class": _text(payload, "asset_class", "asset_type", default="UNKNOWN").upper(),
                "regime": _text(payload, "regime", "market_regime", "regime_state", default="UNKNOWN").upper(),
                "liquidity_score": _bounded(payload.get("liquidity_score", payload.get("liquidity", 50.0)), 0.0, 100.0),
                "expected_return": safe_float(payload.get("expected_return", payload.get("expected_value", payload.get("return", 0.0)))),
                "expected_drawdown": abs(safe_float(payload.get("expected_drawdown", payload.get("expected_drawdown_pct", payload.get("drawdown", 0.0))))),
                "expected_volatility": abs(safe_float(payload.get("expected_volatility", payload.get("volatility", 0.0)))),
                "beta": safe_float(payload.get("beta", payload.get("portfolio_beta", 1.0)), 1.0),
                "weight": max(0.0, safe_float(payload.get("weight", payload.get("allocation_weight", payload.get("requested_capital", 1.0))), 1.0)),
                "factor_exposure": _factor_exposure(payload),
                "correlations": _correlations(payload),
                "raw": dict(payload),
            }
        )
    return normalized


def average_pairwise_correlation(primary: list[Mapping[str, Any]], others: list[Mapping[str, Any]]) -> float:
    values: list[float] = []
    for left in primary:
        for right in others:
            if left.get("opportunity_id") == right.get("opportunity_id"):
                continue
            values.append(pairwise_correlation(left, right))
    return max(0.0, min(1.0, sum(values) / len(values))) if values else 0.0


def pairwise_correlation(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    correlations = left.get("correlations")
    if isinstance(correlations, Mapping) and right.get("opportunity_id") in correlations:
        return _bounded(correlations.get(right.get("opportunity_id")), 0.0, 1.0)
    correlations = right.get("correlations")
    if isinstance(correlations, Mapping) and left.get("opportunity_id") in correlations:
        return _bounded(correlations.get(left.get("opportunity_id")), 0.0, 1.0)

    score = 0.05
    if left.get("asset_class") == right.get("asset_class"):
        score += 0.25
    if left.get("sector") == right.get("sector"):
        score += 0.25
    if left.get("currency") == right.get("currency"):
        score += 0.15
    if left.get("regime") == right.get("regime"):
        score += 0.10
    if left.get("strategy") == right.get("strategy"):
        score += 0.10
    return max(0.0, min(1.0, score))


def max_bucket_share(opportunities: list[Mapping[str, Any]], key: str) -> float:
    total = sum(max(0.0, safe_float(item.get("weight"), 1.0)) for item in opportunities)
    if total <= 0.0:
        return 0.0
    buckets: dict[str, float] = {}
    for item in opportunities:
        bucket = str(item.get(key, "UNKNOWN") or "UNKNOWN")
        buckets[bucket] = buckets.get(bucket, 0.0) + max(0.0, safe_float(item.get("weight"), 1.0))
    return max(buckets.values()) / total if buckets else 0.0


def exposure_percentages(opportunities: list[Mapping[str, Any]], key: str) -> dict[str, float]:
    total = sum(max(0.0, safe_float(item.get("weight"), 1.0)) for item in opportunities)
    if total <= 0.0:
        return {}
    buckets: dict[str, float] = {}
    for item in opportunities:
        bucket = str(item.get(key, "UNKNOWN") or "UNKNOWN")
        buckets[bucket] = buckets.get(bucket, 0.0) + max(0.0, safe_float(item.get("weight"), 1.0))
    return {key: round((value / total) * 100.0, 6) for key, value in sorted(buckets.items())}


def average_correlation(opportunities: list[Mapping[str, Any]]) -> float:
    values: list[float] = []
    for left_index, left in enumerate(opportunities):
        for right in opportunities[left_index + 1 :]:
            values.append(pairwise_correlation(left, right))
    return round(sum(values) / len(values), 6) if values else 0.0


def max_factor_overlap(opportunity: Mapping[str, Any], others: list[Mapping[str, Any]]) -> float:
    own = set(opportunity.get("factor_exposure", []))
    if not own or not others:
        return 0.0
    overlaps = []
    for other in others:
        peer = set(other.get("factor_exposure", []))
        if not peer:
            continue
        overlaps.append(len(own & peer) / len(own | peer))
    return max(overlaps) if overlaps else 0.0


def _flatten(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    for key in ("proposal", "normalized", "opportunity"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            payload.update({nested_key: nested_value for nested_key, nested_value in nested.items() if nested_key not in payload})
    score = payload.get("score")
    if isinstance(score, Mapping):
        for key in ("score", "quality_score", "opportunity_score", "confidence", "expected_return"):
            if score.get(key) is not None and key not in payload:
                payload[key] = score.get(key)
    return payload


def _approved(payload: Mapping[str, Any]) -> bool:
    if payload.get("approved") is not None:
        return bool(payload.get("approved"))
    status = str(payload.get("status", payload.get("decision", payload.get("portfolio_status", "APPROVED"))) or "").upper()
    return status not in {"REJECTED", "BLOCKED", "DENIED", "INVALID"}


def _text(payload: Mapping[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = str(payload.get(key, "") or "").strip()
        if value:
            return value
    return default


def _factor_exposure(payload: Mapping[str, Any]) -> list[str]:
    value = payload.get("factor_exposure", payload.get("factors", payload.get("factor_exposures", [])))
    if isinstance(value, Mapping):
        return sorted(str(key).upper() for key, score in value.items() if safe_float(score) != 0.0)
    if isinstance(value, (list, tuple, set)):
        return sorted(str(item).upper() for item in value if str(item).strip())
    text = str(value or "").strip()
    return [text.upper()] if text else []


def _correlations(payload: Mapping[str, Any]) -> dict[str, float]:
    value = payload.get("correlations", payload.get("correlation"))
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _bounded(item, 0.0, 1.0) for key, item in value.items()}


def _currency_from_symbol(payload: Mapping[str, Any]) -> str:
    symbol = str(payload.get("symbol", "") or "")
    if "-" in symbol:
        return symbol.rsplit("-", 1)[-1]
    if "_" in symbol:
        return symbol.rsplit("_", 1)[-1]
    return "USD"


def _bounded(value: Any, low: float, high: float) -> float:
    return max(low, min(high, safe_float(value, low)))


def _safety_flags() -> dict[str, bool]:
    return {
        "live_trading_blocked": True,
        "broker_execution_armed": False,
        "execution_authority_changed": False,
    }
