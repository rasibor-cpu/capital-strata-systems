from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from backend.analytics.opportunity_intelligence_engine import build_opportunity_intelligence_report


class CapitalAllocationOptimizerError(ValueError):
    """Fail-closed exception for advisory capital allocation inputs."""


class CapitalAllocationOptimizer:
    """Shadow-only capital allocation optimizer for Phase 155AB opportunities."""

    def optimize(
        self,
        *,
        available_capital: float,
        ranked_opportunities: Sequence[Mapping[str, Any]] | None,
        policies: Mapping[str, Any] | None = None,
        portfolio_positions: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        try:
            capital = float(available_capital)
        except (TypeError, ValueError) as exc:
            raise CapitalAllocationOptimizerError("available_capital must be numeric") from exc
        if capital < 0.0:
            raise CapitalAllocationOptimizerError("available_capital must be non-negative")
        if ranked_opportunities is not None and not isinstance(ranked_opportunities, Sequence):
            raise CapitalAllocationOptimizerError("ranked_opportunities must be a sequence")

        rows = [self._normalize_opportunity(row, index) for index, row in enumerate(ranked_opportunities or [])]
        policy = self._policy(capital, policies)
        current = self._current_exposure(portfolio_positions)
        deployable_capital = max(0.0, min(capital * policy["max_portfolio_exposure_pct"], capital - policy["cash_reserve"]))

        allocation_plan: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []
        warnings: list[str] = []
        capital_used = 0.0
        by_asset: dict[str, float] = dict(current["asset_class"])
        by_sector: dict[str, float] = dict(current["sector"])
        by_broker: dict[str, float] = {}
        by_strategy: dict[str, float] = {}

        for row in sorted(rows, key=lambda item: (int(item["rank"]), -float(item["score"]), str(item["asset"]))):
            proposed = self._proposed_allocation(row, capital, deployable_capital, policy)
            reasons = self._constraint_reasons(
                row,
                proposed,
                capital_used,
                deployable_capital,
                capital,
                policy,
                by_asset,
                by_sector,
                by_broker,
                by_strategy,
            )
            if reasons:
                recommendations.append(self._skipped(row, reasons))
                warnings.extend(reasons)
                continue

            capital_used += proposed
            by_asset[row["asset_class"]] = by_asset.get(row["asset_class"], 0.0) + proposed
            by_sector[row["sector"]] = by_sector.get(row["sector"], 0.0) + proposed
            by_broker[row["broker"]] = by_broker.get(row["broker"], 0.0) + proposed
            by_strategy[row["strategy"]] = by_strategy.get(row["strategy"], 0.0) + proposed

            plan_row = {
                "rank": row["rank"],
                "opportunity_id": row["opportunity_id"],
                "asset": row["asset"],
                "asset_class": row["asset_class"],
                "sector": row["sector"],
                "broker": row["broker"],
                "strategy": row["strategy"],
                "allocated_capital": round(proposed, 6),
                "allocation_pct": round((proposed / capital) if capital > 0.0 else 0.0, 6),
                "score": round(row["score"], 6),
                "expected_value": round(row["expected_value"], 6),
                "confidence": round(row["confidence"], 6),
                "status": row["status"],
                "rationale": self._allocation_rationale(row, proposed),
                "advisory_only": True,
                "execution_allowed": False,
            }
            allocation_plan.append(plan_row)
            recommendations.append(
                {
                    "opportunity_id": row["opportunity_id"],
                    "asset": row["asset"],
                    "decision": "ALLOCATE_SHADOW_CAPITAL",
                    "explanation": plan_row["rationale"],
                    "advisory_only": True,
                    "execution_allowed": False,
                }
            )

        cash_allocation = max(0.0, capital - capital_used)
        allocation_percentages = self._allocation_percentages(allocation_plan, capital)
        portfolio_metrics = self._portfolio_metrics(allocation_plan, cash_allocation, capital)
        summary = {
            "capital_used": round(capital_used, 6),
            "capital_remaining": round(cash_allocation, 6),
            "cash_reserve": round(policy["cash_reserve"], 6),
            "deployable_capital": round(deployable_capital, 6),
            "allocated_opportunity_count": len(allocation_plan),
            "reviewed_opportunity_count": len(rows),
            "shadow_runtime_stage": "AFTER_OPPORTUNITY_INTELLIGENCE",
        }

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "advisory_only": True,
            "execution_allowed": False,
            "live_trading_enabled": False,
            "shadow_mode": True,
            "execution_action": "NO_EXECUTION",
            "allocation_plan": allocation_plan,
            "capital_used": round(capital_used, 6),
            "capital_remaining": round(cash_allocation, 6),
            "allocation_percentages": allocation_percentages,
            "allocation_rationale": [row["rationale"] for row in allocation_plan],
            "allocation_summary": summary,
            "portfolio_metrics": portfolio_metrics,
            "recommendations": recommendations,
            "warnings": sorted(dict.fromkeys(warnings)),
            "policies": {
                key: round(value, 6) if isinstance(value, float) else value
                for key, value in policy.items()
            },
        }

    @staticmethod
    def _policy(capital: float, policies: Mapping[str, Any] | None) -> dict[str, Any]:
        source = dict(policies) if isinstance(policies, Mapping) else {}
        cash_reserve_pct = _ratio(source.get("cash_reserve_pct", 0.20))
        max_portfolio_exposure_pct = _ratio(source.get("max_portfolio_exposure_pct", 0.80))
        return {
            "cash_reserve_pct": cash_reserve_pct,
            "cash_reserve": capital * cash_reserve_pct,
            "max_portfolio_exposure_pct": max_portfolio_exposure_pct,
            "max_single_position_pct": _ratio(source.get("max_single_position_pct", 0.25)),
            "asset_class_limit_pct": _ratio(source.get("asset_class_limit_pct", 0.50)),
            "sector_limit_pct": _ratio(source.get("sector_limit_pct", 0.40)),
            "broker_limit_pct": _ratio(source.get("broker_limit_pct", 0.50)),
            "strategy_limit_pct": _ratio(source.get("strategy_limit_pct", 0.45)),
            "min_score": float(source.get("min_score", 45.0) or 45.0),
            "diversification_target_count": int(source.get("diversification_target_count", 3) or 3),
        }

    @staticmethod
    def _normalize_opportunity(row: Mapping[str, Any], index: int) -> dict[str, Any]:
        if not isinstance(row, Mapping):
            raise CapitalAllocationOptimizerError("opportunity rows must be mappings")
        asset = str(_first(row, "asset", "symbol", default="UNKNOWN")).upper()
        asset_class = str(_first(row, "asset_class", default="UNKNOWN")).upper()
        sector = str(_first(row, "sector", default=asset_class)).upper()
        return {
            "input_order": index,
            "rank": int(_number(_first(row, "rank", default=index + 1), default=index + 1)),
            "opportunity_id": str(_first(row, "opportunity_id", "proposal_id", default=f"{asset}:{index}")),
            "asset": asset,
            "asset_class": asset_class,
            "sector": sector,
            "broker": str(_first(row, "broker", default="UNKNOWN")).upper(),
            "strategy": str(_first(row, "strategy", default="UNKNOWN")),
            "score": _number(_first(row, "opportunity_score", "score", default=0.0)),
            "expected_value": _number(_first(row, "expected_value", default=0.0)),
            "confidence": _ratio(_first(row, "confidence", default=0.0)),
            "capital_efficiency": _ratio(_first(row, "capital_efficiency", default=0.0)),
            "expected_drawdown": _ratio(_first(row, "expected_drawdown", default=0.0)),
            "expected_portfolio_risk": _ratio(_first(row, "expected_risk", "portfolio_risk", default=0.0)),
            "requested_capital": _number(_first(row, "requested_capital", "capital_request", default=0.0)),
            "liquidity": _ratio(_first(row, "liquidity", "liquidity_score", default=0.5)),
            "volatility": _ratio(_first(row, "volatility", "volatility_score", default=0.5)),
            "diversification_benefit": _ratio(_first(row, "diversification_benefit", "portfolio_diversification_benefit", default=0.5)),
            "status": str(_first(row, "status", default="AMBER")).upper(),
        }

    @staticmethod
    def _proposed_allocation(
        row: Mapping[str, Any],
        capital: float,
        deployable_capital: float,
        policy: Mapping[str, Any],
    ) -> float:
        requested = float(row["requested_capital"])
        score_weight = max(0.0, min(1.0, float(row["score"]) / 100.0))
        efficiency = max(0.10, float(row["capital_efficiency"]))
        model_size = deployable_capital * float(policy["max_single_position_pct"]) * score_weight * (0.50 + efficiency)
        if requested > 0.0:
            model_size = min(model_size, requested)
        return round(min(model_size, capital * float(policy["max_single_position_pct"])), 6)

    @staticmethod
    def _constraint_reasons(
        row: Mapping[str, Any],
        proposed: float,
        capital_used: float,
        deployable_capital: float,
        capital: float,
        policy: Mapping[str, Any],
        by_asset: Mapping[str, float],
        by_sector: Mapping[str, float],
        by_broker: Mapping[str, float],
        by_strategy: Mapping[str, float],
    ) -> list[str]:
        reasons: list[str] = []
        if float(row["score"]) < float(policy["min_score"]):
            reasons.append("Score below minimum allocation threshold")
        if proposed <= 0.0:
            reasons.append("Proposed allocation is zero")
        if capital_used + proposed > deployable_capital:
            reasons.append("Cash reserve or max portfolio exposure policy prevents allocation")
        if proposed > capital * float(policy["max_single_position_pct"]):
            reasons.append("Maximum single-position allocation policy prevents allocation")
        if by_asset.get(str(row["asset_class"]), 0.0) + proposed > capital * float(policy["asset_class_limit_pct"]):
            reasons.append("Asset-class allocation limit prevents allocation")
        if by_sector.get(str(row["sector"]), 0.0) + proposed > capital * float(policy["sector_limit_pct"]):
            reasons.append("Sector allocation limit prevents allocation")
        if by_broker.get(str(row["broker"]), 0.0) + proposed > capital * float(policy["broker_limit_pct"]):
            reasons.append("Broker allocation limit prevents allocation")
        if by_strategy.get(str(row["strategy"]), 0.0) + proposed > capital * float(policy["strategy_limit_pct"]):
            reasons.append("Strategy allocation limit prevents allocation")
        if str(row["status"]) == "RED":
            reasons.append("RED opportunity status prevents allocation")
        return reasons

    @staticmethod
    def _allocation_rationale(row: Mapping[str, Any], allocation: float) -> str:
        return (
            f"{row['asset']} received shadow capital because rank {row['rank']} scored "
            f"{float(row['score']):.1f}, confidence is {float(row['confidence']):.2f}, "
            f"expected value is {float(row['expected_value']):.2f}, and allocation {allocation:.2f} "
            "fits portfolio governance constraints."
        )

    @staticmethod
    def _skipped(row: Mapping[str, Any], reasons: list[str]) -> dict[str, Any]:
        return {
            "opportunity_id": row["opportunity_id"],
            "asset": row["asset"],
            "decision": "NO_SHADOW_ALLOCATION",
            "explanation": f"{row['asset']} received no capital: {', '.join(reasons)}.",
            "constraints": reasons,
            "advisory_only": True,
            "execution_allowed": False,
        }

    @staticmethod
    def _allocation_percentages(allocation_plan: Sequence[Mapping[str, Any]], capital: float) -> dict[str, Any]:
        by_asset: dict[str, float] = {}
        by_sector: dict[str, float] = {}
        by_broker: dict[str, float] = {}
        by_strategy: dict[str, float] = {}
        for row in allocation_plan:
            amount = float(row["allocated_capital"])
            for bucket, key in (
                (by_asset, str(row["asset_class"])),
                (by_sector, str(row["sector"])),
                (by_broker, str(row["broker"])),
                (by_strategy, str(row["strategy"])),
            ):
                bucket[key] = bucket.get(key, 0.0) + amount

        def pct_map(values: Mapping[str, float]) -> dict[str, float]:
            return {
                key: round(value / capital, 6) if capital > 0.0 else 0.0
                for key, value in sorted(values.items())
            }

        return {
            "by_asset_class": pct_map(by_asset),
            "by_sector": pct_map(by_sector),
            "by_broker": pct_map(by_broker),
            "by_strategy": pct_map(by_strategy),
        }

    @staticmethod
    def _portfolio_metrics(allocation_plan: Sequence[Mapping[str, Any]], cash: float, capital: float) -> dict[str, Any]:
        used = sum(float(row["allocated_capital"]) for row in allocation_plan)
        if used <= 0.0:
            return {
                "capital_efficiency_score": 0.0,
                "expected_portfolio_return": 0.0,
                "expected_portfolio_risk": 0.0,
                "expected_drawdown": 0.0,
                "portfolio_confidence": 0.0,
                "risk_adjusted_capital_score": 0.0,
                "diversification_score": 0.0,
                "cash_allocation": round(cash, 6),
            }

        expected_return = sum(float(row["allocated_capital"]) * float(row["expected_value"]) for row in allocation_plan) / used
        confidence = sum(float(row["allocated_capital"]) * float(row["confidence"]) for row in allocation_plan) / used
        scores = sum(float(row["allocated_capital"]) * float(row["score"]) for row in allocation_plan) / used
        weights = [float(row["allocated_capital"]) / used for row in allocation_plan]
        hhi = sum(weight * weight for weight in weights)
        diversification = max(0.0, 1.0 - hhi)
        risk = max(0.0, min(1.0, (1.0 - confidence) * 0.45 + hhi * 0.35))
        drawdown = max(0.0, min(1.0, risk * 0.8))
        capital_efficiency = min(100.0, scores * (used / capital if capital > 0.0 else 0.0))
        risk_adjusted = max(0.0, min(100.0, (scores * confidence * (1.0 - risk)) + diversification * 10.0))

        return {
            "capital_efficiency_score": round(capital_efficiency, 6),
            "expected_portfolio_return": round(expected_return, 6),
            "expected_portfolio_risk": round(risk, 6),
            "expected_drawdown": round(drawdown, 6),
            "portfolio_confidence": round(confidence, 6),
            "risk_adjusted_capital_score": round(risk_adjusted, 6),
            "diversification_score": round(diversification, 6),
            "cash_allocation": round(cash, 6),
        }

    @staticmethod
    def _current_exposure(positions: Sequence[Mapping[str, Any]] | None) -> dict[str, dict[str, float]]:
        exposure = {"asset_class": {}, "sector": {}}
        if positions is None:
            return exposure
        for position in positions:
            if not isinstance(position, Mapping):
                continue
            amount = abs(_number(_first(position, "exposure", "market_value", default=0.0)))
            asset_class = str(_first(position, "asset_class", default="UNKNOWN")).upper()
            sector = str(_first(position, "sector", default=asset_class)).upper()
            exposure["asset_class"][asset_class] = exposure["asset_class"].get(asset_class, 0.0) + amount
            exposure["sector"][sector] = exposure["sector"].get(sector, 0.0) + amount
        return exposure


def build_capital_allocation_intelligence_report(dashboard_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(dashboard_payload)
    account = _mapping(payload.get("account_summary"))
    risk = _mapping(payload.get("risk_summary"))
    positions = _mapping(payload.get("position_state"))
    opportunity_report = build_opportunity_intelligence_report(payload)

    available_capital = _number(
        _first(
            account,
            "buying_power",
            "available_margin",
            "cash_balance",
            default=0.0,
        )
    )
    policies = {
        "cash_reserve_pct": _ratio(risk.get("cash_reserve_pct", 0.20)),
        "max_portfolio_exposure_pct": _portfolio_exposure_policy(risk, available_capital),
        "max_single_position_pct": _ratio(risk.get("max_single_position_pct", 0.25)),
        "asset_class_limit_pct": _ratio(risk.get("asset_class_limit_pct", 0.50)),
        "sector_limit_pct": _ratio(risk.get("sector_limit_pct", 0.40)),
        "broker_limit_pct": _ratio(risk.get("broker_limit_pct", 0.50)),
        "strategy_limit_pct": _ratio(risk.get("strategy_limit_pct", 0.45)),
        "min_score": float(risk.get("min_allocation_score", 45.0) or 45.0),
    }
    return CapitalAllocationOptimizer().optimize(
        available_capital=available_capital,
        ranked_opportunities=opportunity_report["opportunities"],
        policies=policies,
        portfolio_positions=_list(positions.get("positions")),
    )


def _portfolio_exposure_policy(risk: Mapping[str, Any], available_capital: float) -> float:
    exposure_limit = _number(risk.get("exposure_limit"))
    if exposure_limit > 0.0 and available_capital > 0.0:
        return max(0.0, min(1.0, exposure_limit / available_capital))
    return _ratio(risk.get("max_portfolio_exposure_pct", 0.80))


def _first(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return value
    return default


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, *, default: float = 0.0) -> float:
    try:
        if value is None or isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _ratio(value: Any) -> float:
    numeric = _number(value)
    if abs(numeric) > 1.0:
        numeric = numeric / 100.0
    return max(0.0, min(1.0, numeric))


__all__ = [
    "CapitalAllocationOptimizer",
    "CapitalAllocationOptimizerError",
    "build_capital_allocation_intelligence_report",
]
