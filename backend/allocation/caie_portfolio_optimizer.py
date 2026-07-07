from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class CAIEPortfolioOptimizer:
    """Shadow-only portfolio optimizer for validated and scored CAIE opportunities."""

    def optimize(
        self,
        opportunities: Sequence[Mapping[str, Any]] | None,
        available_capital: float,
        *,
        asset_class_caps: Mapping[str, float] | None = None,
        broker_caps: Mapping[str, float] | None = None,
        min_quality_score: float = 50.0,
        concentration_penalty_weight: float = 20.0,
        diversification_bonus: float = 2.0,
    ) -> dict[str, Any]:
        try:
            capital = float(available_capital)
        except (TypeError, ValueError):
            return self._fail_closed("available_capital_invalid")

        if capital < 0.0:
            return self._fail_closed("available_capital_negative")

        if not isinstance(opportunities, Sequence):
            return self._fail_closed("opportunities_must_be_sequence")

        normalized_asset_caps = self._normalize_caps(asset_class_caps, "asset_class")
        if normalized_asset_caps is None:
            return self._fail_closed("asset_class_caps_invalid")

        normalized_broker_caps = self._normalize_caps(broker_caps, "broker")
        if normalized_broker_caps is None:
            return self._fail_closed("broker_caps_invalid")

        candidates: list[dict[str, Any]] = []
        for index, opportunity in enumerate(opportunities):
            parsed = self._parse_opportunity(opportunity, index)
            if parsed is None:
                return self._fail_closed("invalid_or_unscored_opportunity")
            candidates.append(parsed)

        ranked = sorted(
            candidates,
            key=lambda item: (-item["score"], item["proposal_id"], item["original_index"]),
        )

        ranked_payload = [self._ranked_item_payload(item, rank + 1) for rank, item in enumerate(ranked)]

        selected: list[dict[str, Any]] = []
        allocations: list[dict[str, Any]] = []
        used_capital = 0.0
        by_asset_class: dict[str, float] = {}
        by_broker: dict[str, float] = {}

        remaining = list(ranked)
        while remaining:
            feasible = [
                item
                for item in remaining
                if self._is_feasible(
                    item,
                    used_capital,
                    capital,
                    by_asset_class,
                    by_broker,
                    normalized_asset_caps,
                    normalized_broker_caps,
                    min_quality_score,
                )
            ]

            if not feasible:
                break

            chosen = max(
                feasible,
                key=lambda item: (
                    self._selection_objective(
                        item,
                        used_capital,
                        by_asset_class,
                        by_broker,
                        concentration_penalty_weight,
                        diversification_bonus,
                    ),
                    item["score"],
                    -item["original_index"],
                    item["proposal_id"],
                ),
            )

            remaining = [item for item in remaining if item is not chosen]

            allocation = chosen["requested_capital"]
            used_capital += allocation
            by_asset_class[chosen["asset_class"]] = by_asset_class.get(chosen["asset_class"], 0.0) + allocation
            by_broker[chosen["broker"]] = by_broker.get(chosen["broker"], 0.0) + allocation

            selected_item = {
                "proposal_id": chosen["proposal_id"],
                "symbol": chosen["symbol"],
                "asset_class": chosen["asset_class"],
                "broker": chosen["broker"],
                "score": round(chosen["score"], 6),
                "requested_capital": round(chosen["requested_capital"], 6),
            }
            selected.append(selected_item)
            allocations.append(
                {
                    "proposal_id": chosen["proposal_id"],
                    "allocated_capital": round(allocation, 6),
                    "asset_class": chosen["asset_class"],
                    "broker": chosen["broker"],
                    "score": round(chosen["score"], 6),
                }
            )

        concentration_metrics = self._concentration_metrics(allocations, used_capital)
        concentration_penalty = concentration_metrics["hhi"] * concentration_penalty_weight

        if used_capital > 0.0:
            weighted_score = sum(item["allocated_capital"] * item["score"] for item in allocations) / used_capital
        else:
            weighted_score = 0.0

        diversification_score = max(0.0, 1.0 - concentration_metrics["hhi"])
        portfolio_score = max(0.0, weighted_score - concentration_penalty + (diversification_score * diversification_bonus))

        return {
            "valid": True,
            "ranked_opportunities": ranked_payload,
            "selected_opportunities": selected,
            "recommended_capital_allocations": allocations,
            "unused_capital": round(max(0.0, capital - used_capital), 6),
            "portfolio_score": round(portfolio_score, 6),
            "diversification_score": round(diversification_score, 6),
            "concentration_metrics": {
                **concentration_metrics,
                "concentration_penalty": round(concentration_penalty, 6),
            },
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
            "reason": "portfolio_recommendation_computed",
        }

    def _parse_opportunity(self, opportunity: Mapping[str, Any], index: int) -> dict[str, Any] | None:
        if not isinstance(opportunity, Mapping):
            return None

        proposal = opportunity.get("proposal")
        score_result = opportunity.get("score")
        broker = str(opportunity.get("broker") or "").strip().upper()

        if not isinstance(proposal, Mapping) or not isinstance(score_result, Mapping) or not broker:
            return None

        if bool(proposal.get("valid")) is not True:
            return None
        normalized = proposal.get("normalized")
        if not isinstance(normalized, Mapping):
            return None

        if bool(score_result.get("valid")) is not True:
            return None
        try:
            score_value = float(score_result["score"])
        except (KeyError, TypeError, ValueError):
            return None

        try:
            requested_capital = float(normalized["requested_capital"])
            probability = float(normalized["probability"])
            confidence = float(normalized["confidence"])
            expected_drawdown_pct = float(normalized["expected_drawdown_pct"])
            risk_score = float(normalized["risk_score"])
        except (KeyError, TypeError, ValueError):
            return None

        if requested_capital <= 0.0:
            return None
        if not 0.0 <= probability <= 1.0:
            return None
        if not 0.0 <= confidence <= 1.0:
            return None
        if not 0.0 <= expected_drawdown_pct <= 1.0:
            return None
        if not 0.0 <= risk_score <= 100.0:
            return None

        proposal_id = str(normalized.get("proposal_id") or "").strip()
        symbol = str(normalized.get("symbol") or "").strip().upper()
        asset_class = str(normalized.get("asset_class") or "").strip().upper()

        if not proposal_id or not symbol or not asset_class:
            return None

        return {
            "proposal_id": proposal_id,
            "symbol": symbol,
            "asset_class": asset_class,
            "broker": broker,
            "score": score_value,
            "requested_capital": requested_capital,
            "original_index": index,
        }

    @staticmethod
    def _ranked_item_payload(item: Mapping[str, Any], rank: int) -> dict[str, Any]:
        return {
            "rank": rank,
            "proposal_id": item["proposal_id"],
            "symbol": item["symbol"],
            "asset_class": item["asset_class"],
            "broker": item["broker"],
            "score": round(float(item["score"]), 6),
            "requested_capital": round(float(item["requested_capital"]), 6),
        }

    @staticmethod
    def _normalize_caps(caps: Mapping[str, float] | None, label: str) -> dict[str, float] | None:
        if caps is None:
            return {}
        if not isinstance(caps, Mapping):
            return None

        normalized: dict[str, float] = {}
        for key, value in caps.items():
            text_key = str(key or "").strip().upper()
            if not text_key:
                return None
            try:
                cap_value = float(value)
            except (TypeError, ValueError):
                return None
            if cap_value < 0.0:
                return None
            normalized[text_key] = cap_value
        _ = label
        return normalized

    @staticmethod
    def _is_feasible(
        item: Mapping[str, Any],
        used_capital: float,
        available_capital: float,
        by_asset_class: Mapping[str, float],
        by_broker: Mapping[str, float],
        asset_class_caps: Mapping[str, float],
        broker_caps: Mapping[str, float],
        min_quality_score: float,
    ) -> bool:
        required = float(item["requested_capital"])
        if float(item["score"]) < float(min_quality_score):
            return False
        if used_capital + required > available_capital:
            return False

        asset_class = str(item["asset_class"])
        broker = str(item["broker"])

        class_cap = asset_class_caps.get(asset_class, available_capital)
        broker_cap = broker_caps.get(broker, available_capital)

        if by_asset_class.get(asset_class, 0.0) + required > class_cap:
            return False
        if by_broker.get(broker, 0.0) + required > broker_cap:
            return False
        return True

    @staticmethod
    def _selection_objective(
        item: Mapping[str, Any],
        used_capital: float,
        by_asset_class: Mapping[str, float],
        by_broker: Mapping[str, float],
        concentration_penalty_weight: float,
        diversification_bonus: float,
    ) -> float:
        required = float(item["requested_capital"])
        total_after = used_capital + required
        if total_after <= 0.0:
            return float(item["score"])

        asset_weight_after = (by_asset_class.get(str(item["asset_class"]), 0.0) + required) / total_after
        broker_weight_after = (by_broker.get(str(item["broker"]), 0.0) + required) / total_after

        projected_hhi = max(asset_weight_after, broker_weight_after) ** 2

        asset_bonus = diversification_bonus if by_asset_class.get(str(item["asset_class"]), 0.0) == 0.0 else 0.0
        broker_bonus = diversification_bonus if by_broker.get(str(item["broker"]), 0.0) == 0.0 else 0.0

        return float(item["score"]) - (projected_hhi * concentration_penalty_weight) + asset_bonus + broker_bonus

    @staticmethod
    def _concentration_metrics(allocations: Sequence[Mapping[str, Any]], used_capital: float) -> dict[str, Any]:
        if used_capital <= 0.0:
            return {
                "hhi": 0.0,
                "max_position_weight": 0.0,
                "asset_class_weights": {},
                "broker_weights": {},
            }

        asset_totals: dict[str, float] = {}
        broker_totals: dict[str, float] = {}
        max_weight = 0.0

        for row in allocations:
            capital = float(row["allocated_capital"])
            asset_class = str(row["asset_class"])
            broker = str(row["broker"])
            asset_totals[asset_class] = asset_totals.get(asset_class, 0.0) + capital
            broker_totals[broker] = broker_totals.get(broker, 0.0) + capital
            max_weight = max(max_weight, capital / used_capital)

        asset_weights = {
            key: round(value / used_capital, 6)
            for key, value in sorted(asset_totals.items(), key=lambda item: item[0])
        }
        broker_weights = {
            key: round(value / used_capital, 6)
            for key, value in sorted(broker_totals.items(), key=lambda item: item[0])
        }

        hhi = sum(weight * weight for weight in asset_weights.values())
        hhi += sum(weight * weight for weight in broker_weights.values())
        hhi = hhi / 2.0

        return {
            "hhi": round(hhi, 6),
            "max_position_weight": round(max_weight, 6),
            "asset_class_weights": asset_weights,
            "broker_weights": broker_weights,
        }

    @staticmethod
    def _fail_closed(reason: str) -> dict[str, Any]:
        return {
            "valid": False,
            "ranked_opportunities": [],
            "selected_opportunities": [],
            "recommended_capital_allocations": [],
            "unused_capital": None,
            "portfolio_score": None,
            "diversification_score": None,
            "concentration_metrics": None,
            "advisory_only": True,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
            "reason": reason,
        }


def optimize_portfolio_shadow(
    opportunities: Sequence[Mapping[str, Any]] | None,
    available_capital: float,
    *,
    asset_class_caps: Mapping[str, float] | None = None,
    broker_caps: Mapping[str, float] | None = None,
    min_quality_score: float = 50.0,
    concentration_penalty_weight: float = 20.0,
    diversification_bonus: float = 2.0,
) -> dict[str, Any]:
    return CAIEPortfolioOptimizer().optimize(
        opportunities,
        available_capital,
        asset_class_caps=asset_class_caps,
        broker_caps=broker_caps,
        min_quality_score=min_quality_score,
        concentration_penalty_weight=concentration_penalty_weight,
        diversification_bonus=diversification_bonus,
    )
