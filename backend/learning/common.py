from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from backend.portfolio.utils import advisory_response, safe_float


FACTORS = ("technical", "fundamental", "sentiment", "quantitative")
SCORE_KEYS = {
    "technical": "technical_score",
    "fundamental": "fundamental_quality_score",
    "sentiment": "sentiment_score",
    "quantitative": "alpha_score",
}
BALANCED_WEIGHTS = {factor: 25.0 for factor in FACTORS}


def rows(history: Iterable[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    if history is None or isinstance(history, (str, bytes)):
        return []
    try:
        return [row for row in history if isinstance(row, Mapping)]
    except TypeError:
        return []


def outcome(row: Mapping[str, Any]) -> float | None:
    outcome_payload = row.get("outcome")
    if isinstance(outcome_payload, Mapping):
        for key in ("realized_return", "forward_return", "return", "realized_pnl", "pnl"):
            if outcome_payload.get(key) is not None:
                return safe_float(outcome_payload.get(key))
    for key in ("realized_return", "forward_return", "return", "realized_pnl", "pnl"):
        if row.get(key) is not None:
            return safe_float(row.get(key))
    return None


def confidence(row: Mapping[str, Any]) -> float | None:
    value = row.get("confidence", row.get("recommendation_confidence"))
    if value is None and isinstance(row.get("multi_factor_signal"), Mapping):
        value = row["multi_factor_signal"].get("confidence")
    if value is None:
        return None
    numeric = safe_float(value, -1.0)
    if numeric < 0.0:
        return None
    if numeric > 1.0:
        numeric /= 100.0
    return max(0.0, min(1.0, numeric))


def regime(row: Mapping[str, Any]) -> str:
    for key in ("market_regime", "regime", "detected_regime"):
        value = str(row.get(key, "")).strip().upper()
        if value:
            return value
    for key in ("market_regime_intelligence", "regime_learning", "multi_factor_signal"):
        payload = row.get(key)
        if isinstance(payload, Mapping):
            value = str(payload.get("detected_regime", payload.get("regime", ""))).strip().upper()
            if value:
                return value
    return "UNKNOWN"


def factor_scores(row: Mapping[str, Any]) -> dict[str, float]:
    payloads = [
        row.get("factor_scores"),
        row.get("component_scores"),
        (row.get("multi_factor_signal") or {}).get("component_scores") if isinstance(row.get("multi_factor_signal"), Mapping) else None,
    ]
    scores: dict[str, float] = {}
    for payload in payloads:
        if isinstance(payload, Mapping):
            for factor in FACTORS:
                if payload.get(factor) is not None:
                    scores[factor] = _bounded_score(payload.get(factor))
    for factor, key in SCORE_KEYS.items():
        if row.get(key) is not None:
            scores[factor] = _bounded_score(row.get(key))
        component = row.get(f"{factor}_analysis")
        if isinstance(component, Mapping) and component.get(key) is not None:
            scores[factor] = _bounded_score(component.get(key))
    return scores


def factor_weights(row: Mapping[str, Any]) -> dict[str, float]:
    payload = row.get("regime_weights", row.get("weights"))
    if isinstance(row.get("multi_factor_signal"), Mapping):
        payload = row["multi_factor_signal"].get("regime_weights", payload)
    if isinstance(payload, Mapping):
        return normalize_weights({factor: safe_float(payload.get(factor), 0.0) for factor in FACTORS})
    return dict(BALANCED_WEIGHTS)


def hit(score: float, realized: float) -> bool:
    if score >= 50.0:
        return realized >= 0.0
    return realized <= 0.0


def normalize_weights(weights: Mapping[str, Any] | None) -> dict[str, float]:
    positive = {factor: max(0.0, safe_float((weights or {}).get(factor), 0.0)) for factor in FACTORS}
    total = sum(positive.values())
    if total <= 0.0:
        positive = dict(BALANCED_WEIGHTS)
        total = 100.0
    normalized = {factor: round((value / total) * 100.0, 6) for factor, value in positive.items()}
    residual = round(100.0 - sum(normalized.values()), 6)
    if residual:
        target = max(normalized, key=normalized.get)
        normalized[target] = round(normalized[target] + residual, 6)
    return normalized


def unavailable(reason: str, **payload: Any) -> dict[str, Any]:
    return advisory_response("DATA UNAVAILABLE", reasons=[reason], **payload)


def _bounded_score(value: Any) -> float:
    return max(0.0, min(100.0, safe_float(value, 0.0)))
