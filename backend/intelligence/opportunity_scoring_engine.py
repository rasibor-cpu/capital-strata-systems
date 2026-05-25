from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


SCORING_VERSION = "56B.1"


@dataclass(frozen=True)
class OpportunityScoreResult:
    total_score: float = 0.0
    adjusted_edge: float = 0.0
    confidence_weighted_edge: float = 0.0
    execution_quality: float = 0.0
    survivability_score: float = 0.0
    regime_alignment: float = 0.5
    liquidity_quality: float = 0.0
    volatility_penalty: float = 0.0
    spread_penalty: float = 0.0
    risk_penalty: float = 0.0
    diagnostics: dict[str, Any] = field(default_factory=dict)
    scoring_version: str = SCORING_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OpportunityScoringEngine:
    """Safe-mode, passive opportunity scoring intelligence layer."""

    def score_opportunity(self, candidate: Mapping[str, Any] | None) -> OpportunityScoreResult:
        payload = candidate if isinstance(candidate, Mapping) else {}

        signal_strength = self._n01(payload.get("signal_strength", payload.get("score", 0.0)))
        confidence = self._n01(payload.get("confidence", 0.0))
        expected_edge = self._n_signed(payload.get("expected_edge", 0.0), scale=0.05)
        estimated_cost = self._n01(payload.get("estimated_cost", payload.get("execution_cost", 0.0)), scale=0.02)
        estimated_slippage = self._n01(payload.get("estimated_slippage", payload.get("slippage_bps", 0.0)), scale=25.0)
        liquidity_quality = self._n01(payload.get("liquidity_score", payload.get("liquidity", 0.0)))
        volatility_score = self._n01(payload.get("volatility_score", payload.get("volatility_pct", 0.0)), scale=0.05)
        spread_score = self._n01(payload.get("spread_score", payload.get("spread_bps", 0.0)), scale=25.0)

        execution_viable = self._truthy(payload.get("execution_viable", True))
        regime_alignment = self._extract_regime_alignment(payload)

        survivability = self._clamp01((liquidity_quality + (1.0 - volatility_score) + (1.0 - spread_score)) / 3.0)
        execution_quality = self._clamp01((1.0 - estimated_cost + 1.0 - estimated_slippage + survivability) / 3.0)

        confidence_weighted_edge = expected_edge * confidence
        adjusted_edge = confidence_weighted_edge - (estimated_cost * 0.6) - (estimated_slippage * 0.4)

        volatility_penalty = volatility_score * 0.25
        spread_penalty = spread_score * 0.20
        risk_penalty = 0.0 if execution_viable else 0.35

        positive = (
            signal_strength * 0.28
            + confidence * 0.22
            + self._clamp01((adjusted_edge + 1.0) / 2.0) * 0.20
            + liquidity_quality * 0.15
            + survivability * 0.15
        )
        negative = volatility_penalty + spread_penalty + risk_penalty
        total_score = self._clamp01(positive - negative)

        diagnostics = {
            "positive_components": {
                "signal_strength": signal_strength,
                "confidence": confidence,
                "adjusted_edge_component": self._clamp01((adjusted_edge + 1.0) / 2.0),
                "liquidity_quality": liquidity_quality,
                "survivability": survivability,
            },
            "negative_components": {
                "volatility_penalty": volatility_penalty,
                "spread_penalty": spread_penalty,
                "risk_penalty": risk_penalty,
                "estimated_cost": estimated_cost,
                "estimated_slippage": estimated_slippage,
            },
            "execution_viable": execution_viable,
        }

        return OpportunityScoreResult(
            total_score=total_score,
            adjusted_edge=adjusted_edge,
            confidence_weighted_edge=confidence_weighted_edge,
            execution_quality=execution_quality,
            survivability_score=survivability,
            regime_alignment=regime_alignment,
            liquidity_quality=liquidity_quality,
            volatility_penalty=volatility_penalty,
            spread_penalty=spread_penalty,
            risk_penalty=risk_penalty,
            diagnostics=diagnostics,
        )

    def score_batch(self, candidates: list[Mapping[str, Any]] | None) -> list[OpportunityScoreResult]:
        rows = candidates if isinstance(candidates, list) else []
        return [self.score_opportunity(row) for row in rows]

    def rank_opportunities(self, candidates: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        rows = candidates if isinstance(candidates, list) else []

        for idx, row in enumerate(rows):
            raw = row if isinstance(row, Mapping) else {}
            score = self.score_opportunity(raw)
            merged = dict(raw)
            merged["scoring_summary"] = score.to_dict()
            merged["composite_score"] = score.total_score
            merged["_input_index"] = idx
            ranked.append(merged)

        ranked.sort(key=lambda item: (float(item.get("composite_score", 0.0)), -int(item.get("_input_index", 0))), reverse=True)
        for item in ranked:
            item.pop("_input_index", None)
        return ranked

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _n01(self, value: Any, scale: float = 1.0) -> float:
        v = self._to_float(value, 0.0)
        if scale <= 0:
            scale = 1.0
        return self._clamp01(v / scale)

    def _n_signed(self, value: Any, scale: float = 1.0) -> float:
        v = self._to_float(value, 0.0)
        if scale <= 0:
            scale = 1.0
        return max(-1.0, min(1.0, v / scale))

    @staticmethod
    def _truthy(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)

    def _extract_regime_alignment(self, payload: Mapping[str, Any]) -> float:
        regime = payload.get("regime")
        regime_score = payload.get("regime_alignment")
        if regime_score is not None:
            return self._n01(regime_score)
        if isinstance(regime, str):
            normalized = regime.upper()
            if normalized in {"TREND", "BREAKOUT"}:
                return 0.7
            if normalized in {"RANGE", "MEAN_REVERSION"}:
                return 0.6
        return 0.5

    @staticmethod
    def _clamp01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
