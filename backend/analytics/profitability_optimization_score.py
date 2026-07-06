from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class ProfitabilityOptimizationScoreError(RuntimeError):
    """Fail-closed exception for advisory profitability optimization scoring."""


@dataclass(frozen=True)
class ProfitabilityOptimizationPolicy:
    minimum_trade_count: int = 3
    high_quality_threshold: float = 70.0
    watch_threshold: float = 45.0


CANONICAL_PROFITABILITY_SCORE_COMPONENTS = (
    "expected_edge_score",
    "win_rate_score",
    "drawdown_score",
    "realized_pnl_reliability_score",
    "trade_frequency_quality_score",
    "asset_class_concentration_score",
    "confidence_calibration_score",
    "capital_efficiency_score",
)

_WEIGHTS = {
    "expected_edge_score": 0.18,
    "win_rate_score": 0.16,
    "drawdown_score": 0.14,
    "realized_pnl_reliability_score": 0.14,
    "trade_frequency_quality_score": 0.10,
    "asset_class_concentration_score": 0.10,
    "confidence_calibration_score": 0.08,
    "capital_efficiency_score": 0.10,
}


def build_profitability_optimization_score(
    evidence: Mapping[str, Any] | None,
    *,
    policy: ProfitabilityOptimizationPolicy | None = None,
) -> dict[str, Any]:
    """Build a deterministic advisory profitability score.

    Missing evidence is intentionally conservative. This helper never returns
    execution permission and must not be used as a trade gate replacement.
    """

    if evidence is not None and not isinstance(evidence, Mapping):
        raise ProfitabilityOptimizationScoreError("profitability score evidence must be a mapping")
    policy = policy or ProfitabilityOptimizationPolicy()
    if policy.minimum_trade_count <= 0:
        raise ProfitabilityOptimizationScoreError("minimum_trade_count must be positive")
    data = dict(evidence or {})

    trade_count = _int(data.get("trade_count", data.get("sample_size", 0)))
    realized_pnl = _float(data.get("realized_pnl", data.get("pnl", 0.0)))
    average_pnl = _float(data.get("average_pnl", realized_pnl / trade_count if trade_count > 0 else 0.0))
    win_rate = _optional_ratio(data.get("win_rate"))
    confidence = _optional_ratio(data.get("confidence", data.get("probability")))
    drawdown = _optional_ratio(data.get("drawdown", data.get("max_drawdown")))
    concentration = _optional_ratio(
        data.get("asset_class_concentration", data.get("concentration", data.get("asset_concentration")))
    )

    expected_edge = _expected_edge(data, average_pnl=average_pnl)
    expected_edge_score = _positive_score(expected_edge)
    win_rate_score = win_rate if win_rate is not None else 0.0
    drawdown_score = 0.5 if drawdown is None else 1.0 - _clamp01(drawdown)
    sample_confidence = _clamp01(trade_count / float(policy.minimum_trade_count))
    pnl_quality = _clamp01(0.50 + (average_pnl / 100.0))
    realized_pnl_reliability_score = sample_confidence * pnl_quality if trade_count > 0 else 0.0
    trade_frequency_quality_score = _clamp01(trade_count / float(policy.minimum_trade_count * 3))
    asset_class_concentration_score = 0.5 if concentration is None else 1.0 - _clamp01(concentration)
    confidence_calibration_score = _confidence_calibration(data, win_rate=win_rate, confidence=confidence)
    capital_efficiency_score = _capital_efficiency(data, average_pnl=average_pnl, expected_edge=expected_edge)

    components = {
        "expected_edge_score": expected_edge_score,
        "win_rate_score": win_rate_score,
        "drawdown_score": drawdown_score,
        "realized_pnl_reliability_score": realized_pnl_reliability_score,
        "trade_frequency_quality_score": trade_frequency_quality_score,
        "asset_class_concentration_score": asset_class_concentration_score,
        "confidence_calibration_score": confidence_calibration_score,
        "capital_efficiency_score": capital_efficiency_score,
    }
    score = round(sum(components[key] * _WEIGHTS[key] for key in CANONICAL_PROFITABILITY_SCORE_COMPONENTS) * 100.0, 8)
    status = "PREFERRED" if score >= policy.high_quality_threshold else "WATCH" if score >= policy.watch_threshold else "RESTRICTED"
    return {
        "profitability_optimization_score": score,
        "profitability_quality_status": status,
        "score_components": {key: round(value, 8) for key, value in components.items()},
        "expected_edge": round(expected_edge, 8),
        "win_rate": win_rate if win_rate is not None else 0.0,
        "drawdown_penalty": round(1.0 - drawdown_score, 8),
        "trade_count": trade_count,
        "realized_pnl": realized_pnl,
        "missing_data_policy": "CONSERVATIVE",
        "advisory_only": True,
        "execution_allowed": False,
        "can_authorize_trade": False,
        "governance_note": (
            "Optimization score is advisory only; Unified Trade Gate, AntiBleedGuard, "
            "margin/capital limits, live-mode governance, and broker credential diagnostics remain authoritative."
        ),
    }


def rank_profitability_opportunities(
    opportunities: list[Mapping[str, Any]] | None,
    *,
    policy: ProfitabilityOptimizationPolicy | None = None,
) -> list[dict[str, Any]]:
    if opportunities is None:
        return []
    if not isinstance(opportunities, list):
        raise ProfitabilityOptimizationScoreError("opportunities must be a list")
    scored: list[dict[str, Any]] = []
    for index, opportunity in enumerate(opportunities):
        if not isinstance(opportunity, Mapping):
            raise ProfitabilityOptimizationScoreError("opportunity rows must be mappings")
        score = build_profitability_optimization_score(opportunity, policy=policy)
        scored.append({**dict(opportunity), **score, "_input_order": index})
    ranked = sorted(
        scored,
        key=lambda row: (
            -float(row["profitability_optimization_score"]),
            -float(row["score_components"]["expected_edge_score"]),
            -float(row.get("win_rate", 0.0) or 0.0),
            str(row.get("symbol", row.get("strategy_id", ""))),
            int(row["_input_order"]),
        ),
    )
    for row in ranked:
        row.pop("_input_order", None)
    return ranked


def _expected_edge(data: Mapping[str, Any], *, average_pnl: float) -> float:
    if "expected_edge" in data:
        return _float(data.get("expected_edge"))
    if "edge" in data:
        return _float(data.get("edge"))
    if "expectancy" in data:
        return _float(data.get("expectancy")) * 100.0
    if "expected_value" in data:
        return max(0.0, _float(data.get("expected_value")) - _float(data.get("cost", 0.0)))
    return average_pnl


def _confidence_calibration(data: Mapping[str, Any], *, win_rate: float | None, confidence: float | None) -> float:
    for key in ("confidence_calibration", "confidence_calibration_score", "calibration_score"):
        if key in data:
            return _clamp01(_ratio(_float(data.get(key))))
    if confidence is not None and win_rate is not None:
        return 1.0 - min(1.0, abs(confidence - win_rate))
    return 0.5


def _capital_efficiency(data: Mapping[str, Any], *, average_pnl: float, expected_edge: float) -> float:
    for key in ("capital_efficiency", "capital_efficiency_score"):
        if key in data:
            return _clamp01(_ratio(_float(data.get(key))))
    capital_at_risk = _float(data.get("capital_at_risk", data.get("risk", data.get("allocation_amount", 0.0))))
    if capital_at_risk > 0.0:
        return _clamp01(max(0.0, expected_edge) / capital_at_risk)
    return _positive_score(average_pnl)


def _positive_score(value: float) -> float:
    return _clamp01(max(0.0, value) / 100.0)


def _optional_ratio(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _clamp01(_ratio(_float(value)))


def _ratio(value: float) -> float:
    return value / 100.0 if abs(value) > 1.0 else value


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


__all__ = [
    "CANONICAL_PROFITABILITY_SCORE_COMPONENTS",
    "ProfitabilityOptimizationPolicy",
    "ProfitabilityOptimizationScoreError",
    "build_profitability_optimization_score",
    "rank_profitability_opportunities",
]
