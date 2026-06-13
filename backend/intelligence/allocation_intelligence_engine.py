from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


GOVERNANCE_VERSION = "58.1"


@dataclass(frozen=True)
class AllocationGuidanceResult:
    recommended_weight: float = 0.0
    survivability_weight: float = 0.0
    confidence_weight: float = 0.0
    regime_weight: float = 0.0
    diversification_score: float = 0.0
    concentration_risk: float = 0.0
    correlation_risk: float = 0.0
    portfolio_pressure: float = 0.0
    deployment_tier: str = "HOLD"
    diagnostics: dict[str, Any] = field(default_factory=dict)
    governance_version: str = GOVERNANCE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AllocationIntelligenceEngine:
    """Passive allocation observer. Advisory only, non-executional."""

    def analyze_candidate(self, candidate: Mapping[str, Any] | None, portfolio_state: Mapping[str, Any] | None = None) -> AllocationGuidanceResult:
        row = candidate if isinstance(candidate, Mapping) else {}
        portfolio = portfolio_state if isinstance(portfolio_state, Mapping) else {}

        composite_score = self._n01(row.get("composite_score", row.get("score", 0.0)))
        adjusted_edge = self._signed(row.get("adjusted_edge", 0.0), scale=0.05)
        survivability_score = self._n01(row.get("survivability_score", 0.0))
        regime_confidence = self._n01(row.get("regime_confidence", row.get("confidence", 0.0)))
        execution_quality = self._n01(row.get("execution_quality", 0.0))
        liquidity_score = self._n01(row.get("liquidity_score", row.get("liquidity", 0.0)))
        volatility_score = self._n01(row.get("volatility_score", row.get("volatility_pct", 0.0)), scale=0.05)

        asset_class = str(row.get("asset_class", "UNKNOWN"))
        exposure_by_asset = portfolio.get("exposure_by_asset_class", {})
        pressure = self._portfolio_pressure(asset_class, exposure_by_asset)

        diversification_score = self._clamp01((1.0 - pressure + liquidity_score + (1.0 - volatility_score)) / 3.0)
        concentration_risk = pressure
        correlation_risk = self._clamp01((volatility_score + (1.0 - diversification_score)) / 2.0)

        survivability_weight = survivability_score * 0.30
        confidence_weight = regime_confidence * 0.20
        regime_weight = self._regime_weight(row) * 0.15
        score_weight = composite_score * 0.25
        edge_weight = self._clamp01((adjusted_edge + 1.0) / 2.0) * 0.10

        recommended_weight = self._clamp01(
            score_weight
            + edge_weight
            + survivability_weight
            + confidence_weight
            + regime_weight
            - concentration_risk * 0.15
            - correlation_risk * 0.10
        )

        return AllocationGuidanceResult(
            recommended_weight=recommended_weight,
            survivability_weight=survivability_weight,
            confidence_weight=confidence_weight,
            regime_weight=regime_weight,
            diversification_score=diversification_score,
            concentration_risk=concentration_risk,
            correlation_risk=correlation_risk,
            portfolio_pressure=pressure,
            deployment_tier=self._tier(recommended_weight),
            diagnostics={
                "asset_class": asset_class,
                "portfolio_pressure": pressure,
            },
        )

    def analyze_portfolio(self, candidates: list[Mapping[str, Any]] | None) -> dict[str, Any]:
        rows = candidates if isinstance(candidates, list) else []
        exposure: dict[str, float] = {}
        total = float(len(rows)) if rows else 1.0

        for row in rows:
            item = row if isinstance(row, Mapping) else {}
            key = str(item.get("asset_class", "UNKNOWN"))
            exposure[key] = exposure.get(key, 0.0) + (1.0 / total)

        pressure = max(exposure.values(), default=0.0)

        return {
            "exposure_by_asset_class": exposure,
            "portfolio_pressure": self._clamp01(pressure),
        }

    def analyze_batch(self, candidates: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
        rows = candidates if isinstance(candidates, list) else []
        portfolio_state = self.analyze_portfolio(rows)
        return [self.analyze_candidate(row, portfolio_state).to_dict() for row in rows]

    def _regime_weight(self, row: Mapping[str, Any]) -> float:
        regime = str(row.get("regime_state", row.get("regime", "UNKNOWN"))).upper()
        if regime in {"RISK_ON", "TRENDING", "BREAKOUT", "CALM"}:
            return 0.9
        if regime in {"RISK_OFF", "PANIC", "LOW_LIQUIDITY"}:
            return 0.2
        return 0.5

    def _portfolio_pressure(self, asset_class: str, exposure: Any) -> float:
        if not isinstance(exposure, Mapping):
            return 0.0
        return self._clamp01(self._to_float(exposure.get(asset_class, 0.0), 0.0))

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

    def _signed(self, value: Any, scale: float = 1.0) -> float:
        v = self._to_float(value, 0.0)
        if scale <= 0:
            scale = 1.0
        return self._clamp(-1.0, 1.0, v / scale)

    @staticmethod
    def _clamp(low: float, high: float, value: float) -> float:
        return max(low, min(high, float(value)))

    def _clamp01(self, value: float) -> float:
        return self._clamp(0.0, 1.0, value)

    def _tier(self, weight: float) -> str:
        if weight >= 0.75:
            return "PRIORITY"
        if weight >= 0.5:
            return "STANDARD"
        if weight >= 0.25:
            return "LIGHT"
        return "HOLD"
