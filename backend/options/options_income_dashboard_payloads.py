from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

from backend.options.paper_position_repository import PaperIncomePosition, SAFE_FLAGS


OPTIONS_INCOME_ENGINE_NAME = "CSS Options Income Engine"
OPTIONS_INCOME_ENGINE_VERSION = "OI-008"
DEFAULT_TIMESTAMP = "1970-01-01T00:00:00+00:00"


class OptionsIncomeDashboardPayloadError(ValueError):
    """Raised when dashboard payload generation must fail closed."""


def safety_flags() -> dict[str, bool]:
    return dict(SAFE_FLAGS)


def envelope(section: str, data: Mapping[str, Any], *, generated_at: str = DEFAULT_TIMESTAMP) -> dict[str, Any]:
    _timestamp(generated_at, "generated_at")
    return {
        "section": section,
        "generated_at": generated_at,
        "data": _json_safe(dict(data)),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def normalize_opportunities(opportunities: Sequence[Any] | None) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in opportunities or []:
        row = _mapping(item.to_dict() if hasattr(item, "to_dict") else item)
        payload = _opportunity_payload(row)
        if row.get("validation_status") == "PASS":
            accepted.append(payload)
        else:
            rejected.append(payload)
    accepted.sort(key=lambda row: (-row["ranking_score"], row["underlying"], row["expiry"], row["strike"], row["option_symbol"]))
    rejected.sort(key=lambda row: (row["underlying"], row["expiry"], row["strike"], row["option_symbol"]))
    return {
        "accepted_candidates": accepted,
        "rejected_candidates": rejected,
        "accepted_opportunity_count": len(accepted),
        "rejected_opportunity_count": len(rejected),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def normalize_positions(
    positions: Sequence[Any] | None,
    *,
    health_by_position: Mapping[str, Mapping[str, Any]] | None = None,
    metrics_by_position: Mapping[str, Mapping[str, Any]] | None = None,
    rolls_by_position: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    health = {str(key): _mapping(value) for key, value in dict(health_by_position or {}).items()}
    metrics = {str(key): _mapping(value) for key, value in dict(metrics_by_position or {}).items()}
    rolls = {str(key): [_mapping(row) for row in value] for key, value in dict(rolls_by_position or {}).items()}
    active: list[dict[str, Any]] = []
    completed: list[dict[str, Any]] = []
    for item in positions or []:
        row = _position_mapping(item)
        payload = _position_payload(
            row,
            health=health.get(str(row.get("position_id"))),
            metrics=metrics.get(str(row.get("position_id"))),
            rolls=rolls.get(str(row.get("position_id")), []),
        )
        if payload["state"] == "COMPLETED":
            completed.append(payload)
        else:
            active.append(payload)
    active.sort(key=lambda row: (row["expiry"], row["underlying"], row["option_symbol"], row["position_id"]))
    completed.sort(key=lambda row: (row["expiry"], row["underlying"], row["option_symbol"], row["position_id"]))
    return {
        "active_positions": active,
        "completed_positions": completed,
        "active_position_count": len(active),
        "completed_position_count": len(completed),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def normalize_rolls(rolls_by_position: Mapping[str, Sequence[Mapping[str, Any]]] | None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for position_id, recommendations in dict(rolls_by_position or {}).items():
        for recommendation in recommendations:
            row = _mapping(recommendation)
            rows.append(
                {
                    "position_id": str(position_id),
                    "recommendation": _roll_action(row.get("recommendation")),
                    "reason": str(row.get("reason", "")),
                    "expected_premium_impact": _number(row.get("expected_premium")),
                    "capital_impact": _number(row.get("capital_impact")),
                    "yield_impact": _number(row.get("yield_impact")),
                    "risk_impact": str(row.get("risk_impact", "")),
                    "confidence": _number(row.get("confidence")),
                    "current_contract": str(row.get("current_contract", row.get("position_id", position_id))),
                    "proposed_paper_candidate": {
                        "target_expiry": row.get("target_expiry"),
                        "target_strike": row.get("target_strike"),
                    },
                    **SAFE_FLAGS,
                    "paper_only": True,
                }
            )
    rows.sort(key=lambda row: (row["position_id"], row["recommendation"], -row["confidence"]))
    return {"recommendations": rows, "roll_recommendation_count": len(rows), **SAFE_FLAGS, "paper_only": True}


def normalize_portfolio(portfolio: Mapping[str, Any] | None) -> dict[str, Any]:
    row = _mapping(portfolio)
    if "capital_allocated" in row and "portfolio_utilization" in row:
        return {
            "portfolio_id": str(row.get("portfolio_id", "")),
            "capital_allocated": _number(row.get("capital_allocated")),
            "available_capital": _number(row.get("available_capital")),
            "collateral_reserved": _number(row.get("collateral_reserved")),
            "unused_collateral": _number(row.get("unused_collateral")),
            "portfolio_utilization": _number(row.get("portfolio_utilization")),
            "covered_call_allocation": _number(row.get("covered_call_allocation")),
            "cash_secured_put_allocation": _number(row.get("cash_secured_put_allocation")),
            "underlying_concentration": _mapping(row.get("underlying_concentration")),
            "expiry_concentration": _mapping(row.get("expiry_concentration")),
            "strategy_concentration": _mapping(row.get("strategy_concentration")),
            "sector_concentration": _mapping(row.get("sector_concentration")),
            "assignment_concentration": _mapping(row.get("assignment_concentration")),
            "expiry_ladder": _mapping(row.get("expiry_ladder")),
            "ladder_quality_score": _number(row.get("ladder_quality_score")),
            "monthly_premium_target": _number(row.get("monthly_premium_target")),
            "annual_premium_target": _number(row.get("annual_premium_target")),
            "expected_premium": _number(row.get("expected_premium")),
            "realized_premium": _number(row.get("realized_premium")),
            "yield_on_collateral": _number(row.get("yield_on_collateral")),
            "annualized_yield": _number(row.get("annualized_yield")),
            "capital_efficiency": _number(row.get("capital_efficiency")),
            "rebalancing_recommendation": _mapping(row.get("rebalancing_recommendation")),
            "constraint_status": str(row.get("constraint_status", "PASS")),
            "constraint_breaches": _list(row.get("constraint_breaches")),
            "warnings": _list(row.get("warnings")),
            "allocations": [_mapping(item) for item in _list(row.get("allocations"))],
            **SAFE_FLAGS,
            "paper_only": True,
        }
    capital = _mapping(row.get("capital"))
    diversification = _mapping(row.get("diversification"))
    ladder = _mapping(row.get("ladder"))
    targets = _mapping(row.get("income_targets"))
    rebalance = _mapping(row.get("rebalance"))
    allocations = [_mapping(item) for item in _list(row.get("allocations"))]
    by_strategy = _mapping(diversification.get("by_strategy"))
    return {
        "portfolio_id": str(row.get("portfolio_id", "")),
        "capital_allocated": _number(capital.get("allocated_capital")),
        "available_capital": _number(capital.get("available_capital")),
        "collateral_reserved": _number(capital.get("reserved_collateral")),
        "unused_collateral": _number(capital.get("unused_collateral")),
        "portfolio_utilization": _number(capital.get("portfolio_utilization")),
        "covered_call_allocation": _number(by_strategy.get("COVERED_CALL")),
        "cash_secured_put_allocation": _number(by_strategy.get("CASH_SECURED_PUT")),
        "underlying_concentration": _mapping(diversification.get("by_underlying")),
        "expiry_concentration": _mapping(diversification.get("by_expiry")),
        "strategy_concentration": by_strategy,
        "sector_concentration": _mapping(diversification.get("by_sector")),
        "assignment_concentration": _mapping(diversification.get("assignment_concentration")),
        "expiry_ladder": ladder,
        "ladder_quality_score": _number(ladder.get("ladder_quality_score")),
        "monthly_premium_target": _number(targets.get("monthly_premium_target")),
        "annual_premium_target": _number(targets.get("annual_premium_target")),
        "expected_premium": _number(targets.get("expected_premium")),
        "realized_premium": sum(_number(item.get("premium_realized")) for item in allocations),
        "yield_on_collateral": _number(targets.get("yield_on_collateral")),
        "annualized_yield": _number(targets.get("portfolio_yield")),
        "capital_efficiency": _number(targets.get("capital_efficiency")),
        "rebalancing_recommendation": rebalance,
        "constraint_status": "BLOCKED" if row.get("blockers") else "PASS",
        "constraint_breaches": _list(row.get("blockers")),
        "warnings": _list(row.get("warnings")),
        "allocations": allocations,
        **SAFE_FLAGS,
        "paper_only": True,
    }


def normalize_risk(assessment: Mapping[str, Any] | None, *, stress_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row = _mapping(assessment)
    if "portfolio_delta" in row and "greeks_by_underlying" in row and "risk_status" in row:
        stress = _mapping(stress_report)
        scenarios = [_mapping(item) for item in _list(stress.get("scenarios", row.get("stress_scenarios")))]
        scenarios.sort(key=lambda item: str(item.get("scenario_name", "")))
        worst = max(scenarios, key=lambda item: _number(item.get("estimated_loss")), default=_mapping(row.get("worst_stress_scenario")))
        return {
            "portfolio_delta": _number(row.get("portfolio_delta")),
            "absolute_delta": _number(row.get("absolute_delta")),
            "gamma": _number(row.get("gamma")),
            "theta": _number(row.get("theta")),
            "vega": _number(row.get("vega")),
            "rho": _number(row.get("rho")),
            "greeks_by_underlying": _mapping(row.get("greeks_by_underlying")),
            "greeks_by_strategy": _mapping(row.get("greeks_by_strategy")),
            "greeks_by_expiry": _mapping(row.get("greeks_by_expiry")),
            "greeks_per_collateral": _mapping(row.get("greeks_per_collateral")),
            "risk_budget_utilization": _mapping(row.get("risk_budget_utilization")),
            "risk_limit_status": str(row.get("risk_limit_status", "UNAVAILABLE")),
            "hard_limit_breaches": _list(row.get("hard_limit_breaches")),
            "advisory_limit_breaches": _list(row.get("advisory_limit_breaches")),
            "assignment_exposure": _mapping(row.get("assignment_exposure")),
            "volatility_regime": str(row.get("volatility_regime", "UNKNOWN")),
            "iv_availability": str(row.get("iv_availability", "UNAVAILABLE")),
            "vega_concentration": _mapping(row.get("vega_concentration")),
            "stress_test_summary": _mapping(row.get("stress_test_summary")),
            "stress_scenarios": [_stress_scenario_payload(item) for item in scenarios],
            "worst_stress_scenario": _stress_scenario_payload(worst) if worst else {},
            "estimated_stressed_loss": _number(row.get("estimated_stressed_loss", stress.get("max_estimated_loss"))),
            "risk_score": _number(row.get("risk_score")),
            "risk_status": str(row.get("risk_status", "UNAVAILABLE")),
            "approval_status": str(row.get("approval_status", "REJECTED_INVALID_DATA")),
            "unavailable_risk_data": _list(row.get("unavailable_risk_data")),
            "advisory_recommendations": _list(row.get("advisory_recommendations")),
            **SAFE_FLAGS,
            "paper_only": True,
        }
    greeks = _mapping(row.get("greeks_summary"))
    risk_budgets = _mapping(row.get("risk_budgets"))
    assignment = _mapping(row.get("assignment_summary"))
    volatility = _mapping(row.get("volatility_summary"))
    stress = _mapping(stress_report) if stress_report else _mapping(row.get("stress_summary"))
    portfolio_greeks = _mapping(greeks.get("portfolio"))
    scenarios = [_mapping(item) for item in _list(stress.get("scenarios"))]
    scenarios.sort(key=lambda item: str(item.get("scenario_name", "")))
    worst = max(scenarios, key=lambda item: _number(item.get("estimated_loss")), default={})
    return {
        "portfolio_delta": _number(portfolio_greeks.get("delta")),
        "absolute_delta": _number(portfolio_greeks.get("absolute_delta_exposure")),
        "gamma": _number(portfolio_greeks.get("gamma")),
        "theta": _number(portfolio_greeks.get("theta")),
        "vega": _number(portfolio_greeks.get("vega")),
        "rho": _number(portfolio_greeks.get("rho")),
        "greeks_by_underlying": _mapping(greeks.get("by_underlying")),
        "greeks_by_strategy": _mapping(greeks.get("by_strategy")),
        "greeks_by_expiry": _mapping(greeks.get("by_expiry")),
        "greeks_per_collateral": _mapping(portfolio_greeks.get("greeks_per_unit_collateral")),
        "risk_budget_utilization": _mapping(risk_budgets.get("budgets")),
        "risk_limit_status": str(row.get("portfolio_risk_status", "UNAVAILABLE")),
        "hard_limit_breaches": _list(row.get("limit_breaches")),
        "advisory_limit_breaches": _list(row.get("warnings")),
        "assignment_exposure": assignment,
        "volatility_regime": str(volatility.get("volatility_regime", "UNKNOWN")),
        "iv_availability": str(volatility.get("status", "UNAVAILABLE")),
        "vega_concentration": _mapping(volatility.get("vega_concentration")),
        "stress_test_summary": _mapping(row.get("stress_summary")),
        "stress_scenarios": [_stress_scenario_payload(item) for item in scenarios],
        "worst_stress_scenario": _stress_scenario_payload(worst) if worst else {},
        "estimated_stressed_loss": _number(stress.get("max_estimated_loss")),
        "risk_score": _number(row.get("risk_score")),
        "risk_status": str(row.get("portfolio_risk_status", "UNAVAILABLE")),
        "approval_status": str(row.get("approval_status", "REJECTED_INVALID_DATA")),
        "unavailable_risk_data": _list(row.get("unavailable_data")),
        "advisory_recommendations": _list(row.get("advisory_recommendations")),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def fail_closed_payload(reason: str, *, section: str = "options_income") -> dict[str, Any]:
    return envelope(
        section,
        {
            "status": "FAIL_CLOSED",
            "error": str(reason),
            "reason": str(reason),
            "data_status": "INVALID",
        },
    )


def _opportunity_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    identity = _mapping(row.get("option_contract_identity"))
    return {
        "ranking_score": _number(row.get("ranking_score")),
        "strategy_type": str(row.get("strategy", "")),
        "underlying": str(row.get("underlying_symbol", identity.get("underlying_symbol", ""))).upper(),
        "option_symbol": str(identity.get("option_symbol", "")),
        "expiry": str(row.get("expiry", "")),
        "strike": _number(row.get("strike")),
        "delta": _number(row.get("delta")),
        "bid": _number(row.get("bid")),
        "ask": _number(row.get("ask")),
        "midpoint": _number(row.get("midpoint")),
        "spread": _number(row.get("spread")),
        "volume": int(_number(row.get("volume"))),
        "open_interest": int(_number(row.get("open_interest"))),
        "premium": _number(row.get("total_premium")),
        "yield": _number(row.get("annualized_premium_yield")),
        "collateral_requirement": _number(row.get("collateral_required")),
        "assignment_exposure": _mapping(row.get("assignment_exposure")),
        "rejection_reasons": _list(row.get("rejection_reasons")),
        "oi002_builder_status": _mapping(row.get("strategy_summary")).get("validation_status", "UNAVAILABLE"),
        "validation_status": str(row.get("validation_status", "FAIL")),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _position_payload(row: Mapping[str, Any], *, health: Mapping[str, Any] | None, metrics: Mapping[str, Any] | None, rolls: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    h = _mapping(health)
    m = _mapping(metrics)
    return {
        "position_id": str(row.get("position_id", "")),
        "strategy_id": str(row.get("strategy_id", "")),
        "underlying": str(row.get("underlying", "")).upper(),
        "option_symbol": str(row.get("option_symbol", "")),
        "strategy_type": str(row.get("strategy_type", "")),
        "state": str(row.get("current_state", "")),
        "entry_date": str(row.get("entry_date", "")),
        "expiry": str(row.get("expiry", "")),
        "days_remaining": int(_number(h.get("days_remaining"))),
        "strike": _number(row.get("strike")),
        "quantity": _number(row.get("quantity")),
        "premium_received": _number(row.get("premium_received")),
        "premium_realized": _number(row.get("premium_realized")),
        "premium_remaining": _number(row.get("premium_remaining")),
        "premium_capture_percentage": _number(m.get("premium_capture_pct", h.get("premium_capture_pct"))),
        "collateral_reserved": _number(row.get("collateral_reserved")),
        "collateral_released": _number(row.get("collateral_released")),
        "yield": _number(m.get("yield_per_collateral")),
        "annualized_yield": _number(m.get("annualized_yield")),
        "capital_efficiency": _number(m.get("capital_efficiency")),
        "assignment_status": str(row.get("assignment_status", "NONE")),
        "health_score": _number(h.get("health_score")),
        "early_close_eligibility": bool(h.get("early_close_eligible", False)),
        "roll_eligibility": bool(h.get("roll_eligible", False)),
        "rolling_history": _list(m.get("rolling_history")) or [dict(item) for item in rolls],
        "lifecycle_events": _lifecycle_events(row.get("lifecycle_events")),
        "advisory_flags": _mapping(row.get("advisory_flags")) or dict(SAFE_FLAGS),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _stress_scenario_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scenario_name": str(row.get("scenario_name", "")),
        "description": str(row.get("description", row.get("scenario_name", ""))),
        "portfolio_value_impact": _number(row.get("portfolio_value_impact")),
        "premium_impact": _number(row.get("premium_impact")),
        "collateral_impact": _number(row.get("collateral_impact")),
        "assignment_impact": _number(row.get("assignment_impact")),
        "greeks_impact": _number(row.get("greeks_impact")),
        "estimated_loss": _number(row.get("estimated_loss")),
        "estimated_gain": _number(row.get("estimated_gain")),
        "limit_status": str(row.get("limit_status", "UNAVAILABLE")),
        "affected_positions": _list(row.get("affected_positions")),
        "advisory_reasons": _list(row.get("advisory_reasons")),
        "approximation_flags": _list(row.get("approximation_flags")),
        **SAFE_FLAGS,
        "paper_only": True,
    }


def _lifecycle_events(value: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, event in enumerate(_list(value), start=1):
        row = _mapping(event)
        events.append(
            {
                "event_id": f"OI008-EVENT-{index:04d}",
                "event_type": str(row.get("event_type", "")),
                "timestamp": str(row.get("timestamp", "")),
                "state": str(row.get("state", "")),
                "details": _mapping(row.get("details")),
            }
        )
    return events


def _position_mapping(item: Any) -> dict[str, Any]:
    if isinstance(item, PaperIncomePosition):
        return item.to_dict()
    return _mapping(item)


def _roll_action(value: Any) -> str:
    normalized = str(value or "NO_ROLL").strip().upper().replace(" ", "_")
    return normalized if normalized in {"ROLL_FORWARD", "ROLL_UP", "ROLL_DOWN", "ROLL_OUT", "NO_ROLL"} else "NO_ROLL"


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return _mapping(value.to_dict())
    raise OptionsIncomeDashboardPayloadError("Expected mapping payload")


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
        return list(value)
    return []


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeDashboardPayloadError("Invalid numeric value") from exc
    if not isfinite(number):
        raise OptionsIncomeDashboardPayloadError("Invalid numeric value")
    return round(number, 8)


def _timestamp(value: Any, field: str) -> None:
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise OptionsIncomeDashboardPayloadError(f"Invalid timestamp: {field}") from exc


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "DEFAULT_TIMESTAMP",
    "OPTIONS_INCOME_ENGINE_NAME",
    "OPTIONS_INCOME_ENGINE_VERSION",
    "OptionsIncomeDashboardPayloadError",
    "envelope",
    "fail_closed_payload",
    "normalize_opportunities",
    "normalize_portfolio",
    "normalize_positions",
    "normalize_risk",
    "normalize_rolls",
    "safety_flags",
]
