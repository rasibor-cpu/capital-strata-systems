from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

from analytics.portfolio_optimizer import (
    PortfolioAllocationPlan,
    StrategyAllocation,
)


class PortfolioOptimizerEngine:
    """
    Phase 129B/129C Portfolio Optimizer Engine.

    Level 1:
        Deterministic equal-weight allocation.

    Level 2:
        Risk-profile-aware allocation using ordered strategy IDs.

    Level 3:
        Market-regime-aware allocation using deterministic strategy
        label matching.

    Level 4:
        Confidence-weighted allocation using strategy payloads.

    This engine recommends allocations only. It does not authorize
    trade execution. Downstream governance remains responsible for
    validation and approval.
    """

    _PROFILE_TOP_WEIGHT = {
        "DEFENSIVE": 1.00,
        "CONSERVATIVE": 1.15,
        "BALANCED": 1.00,
        "GROWTH": 1.35,
        "OPPORTUNISTIC": 1.60,
    }

    _REGIME_KEYWORDS = {
        "TRENDING": ("trend", "momentum", "breakout"),
        "RANGE": ("mean", "reversion", "range", "carry"),
        "RANGE_BOUND": ("mean", "reversion", "range", "carry"),
        "VOLATILE": ("defensive", "hedge", "volatility", "cash"),
        "RISK_OFF": ("defensive", "hedge", "cash"),
        "RISK_ON": ("growth", "momentum", "trend"),
    }

    def build_equal_weight_plan(
        self,
        strategy_ids: Iterable[str],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        ids = self._clean_strategy_ids(strategy_ids)
        return self._build_plan_from_weights(
            ids,
            [1.0 for _ in ids],
            total_capital=total_capital,
            market_regime=market_regime,
            risk_profile=risk_profile,
            rationale="Equal-weight deterministic allocation",
        )

    def build_risk_profile_plan(
        self,
        strategy_ids: Iterable[str],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        ids = self._clean_strategy_ids(strategy_ids)
        profile = self._normalize_label(risk_profile, fallback="BALANCED")

        if profile == "BALANCED":
            return self.build_equal_weight_plan(
                ids,
                total_capital=total_capital,
                market_regime=market_regime,
                risk_profile=profile,
            )

        top_weight = self._PROFILE_TOP_WEIGHT.get(profile, 1.0)
        weights = self._profile_weights(len(ids), top_weight)

        return self._build_plan_from_weights(
            ids,
            weights,
            total_capital=total_capital,
            market_regime=market_regime,
            risk_profile=profile,
            rationale=f"Risk-profile-aware allocation: {profile}",
        )

    def build_market_regime_plan(
        self,
        strategy_ids: Iterable[str],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        ids = self._clean_strategy_ids(strategy_ids)
        regime = self._normalize_label(market_regime, fallback="UNKNOWN")
        profile = self._normalize_label(risk_profile, fallback="BALANCED")

        if not ids:
            return self._build_plan_from_weights(
                ids,
                [],
                total_capital=total_capital,
                market_regime=regime,
                risk_profile=profile,
                rationale=f"Market-regime-aware allocation: {regime}",
            )

        weights = self._regime_weights(ids, regime)

        if profile != "BALANCED":
            profile_weights = self._profile_weights(
                len(ids),
                self._PROFILE_TOP_WEIGHT.get(profile, 1.0),
            )
            weights = [
                round(regime_weight * profile_weight, 8)
                for regime_weight, profile_weight in zip(weights, profile_weights)
            ]

        return self._build_plan_from_weights(
            ids,
            weights,
            total_capital=total_capital,
            market_regime=regime,
            risk_profile=profile,
            rationale=f"Market-regime-aware allocation: {regime}",
        )

    def build_confidence_weighted_plan(
        self,
        strategies: Iterable[dict[str, Any]],
        *,
        total_capital: float,
        market_regime: str = "UNKNOWN",
        risk_profile: str = "BALANCED",
    ) -> PortfolioAllocationPlan:
        parsed = self._parse_strategy_payloads(strategies)
        ids = [item["strategy_id"] for item in parsed]
        regime = self._normalize_label(market_regime, fallback="UNKNOWN")
        profile = self._normalize_label(risk_profile, fallback="BALANCED")

        if not ids:
            return self._build_plan_from_weights(
                [],
                [],
                total_capital=total_capital,
                market_regime=regime,
                risk_profile=profile,
                rationale="Confidence-weighted allocation",
            )

        confidence_weights = [item["confidence"] for item in parsed]
        regime_weights = self._regime_weights(ids, regime)
        weights = [
            round(confidence * regime_weight, 8)
            for confidence, regime_weight in zip(confidence_weights, regime_weights)
        ]

        if profile != "BALANCED":
            profile_weights = self._profile_weights(
                len(ids),
                self._PROFILE_TOP_WEIGHT.get(profile, 1.0),
            )
            weights = [
                round(weight * profile_weight, 8)
                for weight, profile_weight in zip(weights, profile_weights)
            ]

        plan = self._build_plan_from_weights(
            ids,
            weights,
            total_capital=total_capital,
            market_regime=regime,
            risk_profile=profile,
            rationale="Confidence-weighted allocation",
        )

        confidence_lookup = {
            item["strategy_id"]: item["confidence"]
            for item in parsed
        }
        for allocation in plan.allocations:
            allocation.confidence = confidence_lookup.get(allocation.strategy_id, 1.0)

        return plan

    @staticmethod
    def _clean_strategy_ids(strategy_ids: Iterable[str]) -> list[str]:
        return [str(s).strip() for s in strategy_ids if str(s).strip()]

    @staticmethod
    def _normalize_label(value: str, *, fallback: str) -> str:
        text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        return text or fallback

    @staticmethod
    def _safe_confidence(value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 1.0

        if confidence <= 0:
            return 1.0

        return min(confidence, 1.0)

    def _parse_strategy_payloads(
        self,
        strategies: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []

        for strategy in strategies:
            if not isinstance(strategy, dict):
                continue

            strategy_id = str(strategy.get("strategy_id") or strategy.get("strategy") or "").strip()
            if not strategy_id:
                continue

            parsed.append(
                {
                    "strategy_id": strategy_id,
                    "confidence": self._safe_confidence(strategy.get("confidence", 1.0)),
                }
            )

        return parsed

    @staticmethod
    def _profile_weights(count: int, top_weight: float) -> list[float]:
        if count <= 0:
            return []

        if count == 1:
            return [1.0]

        if top_weight <= 1.0:
            return [1.0 for _ in range(count)]

        step = (top_weight - 1.0) / max(count - 1, 1)
        return [round(top_weight - (i * step), 8) for i in range(count)]

    def _regime_weights(self, strategy_ids: list[str], market_regime: str) -> list[float]:
        keywords = self._REGIME_KEYWORDS.get(market_regime)
        if not keywords:
            return [1.0 for _ in strategy_ids]

        weights: list[float] = []
        for strategy_id in strategy_ids:
            label = strategy_id.lower()
            matched = any(keyword in label for keyword in keywords)
            if matched:
                weights.append(1.35)
            elif market_regime in {"VOLATILE", "RISK_OFF"}:
                weights.append(0.90)
            else:
                weights.append(1.0)

        return weights

    def _build_plan_from_weights(
        self,
        strategy_ids: list[str],
        weights: list[float],
        *,
        total_capital: float,
        market_regime: str,
        risk_profile: str,
        rationale: str,
    ) -> PortfolioAllocationPlan:
        plan = PortfolioAllocationPlan(
            generated_at=datetime.now(UTC).isoformat(),
            market_regime=market_regime,
            risk_profile=risk_profile,
            total_capital=total_capital,
        )

        if not strategy_ids:
            return plan

        total_weight = sum(weights)
        if total_weight <= 0:
            weights = [1.0 for _ in strategy_ids]
            total_weight = sum(weights)

        allocated_percent = 0.0
        allocated_amount = 0.0

        for i, strategy_id in enumerate(strategy_ids):
            if i == len(strategy_ids) - 1:
                allocation_percent = round(100.0 - allocated_percent, 4)
                allocation_amount = round(total_capital - allocated_amount, 2)
            else:
                allocation_percent = round((weights[i] / total_weight) * 100.0, 4)
                allocation_amount = round(total_capital * allocation_percent / 100.0, 2)
                allocated_percent += allocation_percent
                allocated_amount += allocation_amount

            plan.allocations.append(
                StrategyAllocation(
                    strategy_id=strategy_id,
                    allocation_percent=allocation_percent,
                    allocation_amount=allocation_amount,
                    confidence=1.0,
                    expected_risk=0.0,
                    rationale=rationale,
                )
            )

        plan.diversification_metrics = {
            "strategy_count": len(strategy_ids),
            "max_allocation_percent": max(
                item.allocation_percent for item in plan.allocations
            ),
            "min_allocation_percent": min(
                item.allocation_percent for item in plan.allocations
            ),
        }

        return plan
