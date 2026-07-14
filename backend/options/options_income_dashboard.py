from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.options.options_income_alerts import OptionsIncomeAlertEngine
from backend.options.options_income_dashboard_payloads import (
    DEFAULT_TIMESTAMP,
    OPTIONS_INCOME_ENGINE_NAME,
    OPTIONS_INCOME_ENGINE_VERSION,
    normalize_opportunities,
    normalize_portfolio,
    normalize_positions,
    normalize_risk,
    normalize_rolls,
    _list,
    _mapping,
    _number,
    _timestamp,
)
from backend.options.options_income_explainability import OptionsIncomeExplainabilityEngine
from backend.options.options_income_operational_intelligence import OptionsIncomeOperationalIntelligence
from backend.options.paper_position_repository import SAFE_FLAGS


class OptionsIncomeDashboardError(ValueError):
    """Raised when options-income dashboard payload generation fails closed."""


class OptionsIncomeDashboardBuilder:
    def __init__(
        self,
        *,
        operational: OptionsIncomeOperationalIntelligence | None = None,
        alerts: OptionsIncomeAlertEngine | None = None,
        explainability: OptionsIncomeExplainabilityEngine | None = None,
    ) -> None:
        self.operational = operational or OptionsIncomeOperationalIntelligence()
        self.alerts = alerts or OptionsIncomeAlertEngine()
        self.explainability = explainability or OptionsIncomeExplainabilityEngine()

    def build(
        self,
        *,
        opportunities: Sequence[Any] | None = None,
        positions: Sequence[Any] | None = None,
        health_by_position: Mapping[str, Mapping[str, Any]] | None = None,
        metrics_by_position: Mapping[str, Mapping[str, Any]] | None = None,
        rolls_by_position: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
        portfolio: Mapping[str, Any] | None = None,
        risk_assessment: Mapping[str, Any] | None = None,
        stress_report: Mapping[str, Any] | None = None,
        generated_at: str = DEFAULT_TIMESTAMP,
        now: str | None = None,
        mode: str = "PAPER",
        repository_corruption: bool = False,
        max_age_seconds: int = 900,
        execution_allowed: bool = False,
        advisory_only: bool = True,
        live_trading_blocked: bool = True,
        broker_execution_armed: bool = False,
    ) -> dict[str, Any]:
        try:
            _validate_posture(mode, execution_allowed, advisory_only, live_trading_blocked, broker_execution_armed)
            _timestamp(generated_at, "generated_at")
            opportunities_payload = normalize_opportunities(opportunities)
            positions_payload = normalize_positions(
                positions,
                health_by_position=health_by_position,
                metrics_by_position=metrics_by_position,
                rolls_by_position=rolls_by_position,
            )
            rolls_payload = normalize_rolls(rolls_by_position)
            portfolio_payload = normalize_portfolio(portfolio)
            risk_payload = normalize_risk(risk_assessment, stress_report=stress_report)
            _validate_dashboard_inputs(portfolio_payload, positions_payload, risk_payload)
            stress_payload = {
                "scenarios": list(risk_payload["stress_scenarios"]),
                "worst_stress_scenario": dict(risk_payload["worst_stress_scenario"]),
                "estimated_stressed_loss": risk_payload["estimated_stressed_loss"],
                "risk_status": risk_payload["risk_status"],
                "paper_only": True,
                **SAFE_FLAGS,
            }
            greeks_payload = {
                "portfolio_delta": risk_payload["portfolio_delta"],
                "absolute_delta": risk_payload["absolute_delta"],
                "gamma": risk_payload["gamma"],
                "theta": risk_payload["theta"],
                "vega": risk_payload["vega"],
                "rho": risk_payload["rho"],
                "greeks_by_underlying": risk_payload["greeks_by_underlying"],
                "greeks_by_strategy": risk_payload["greeks_by_strategy"],
                "greeks_by_expiry": risk_payload["greeks_by_expiry"],
                "greeks_per_collateral": risk_payload["greeks_per_collateral"],
                "paper_only": True,
                **SAFE_FLAGS,
            }
            summary = _summary(
                generated_at=generated_at,
                mode=mode,
                opportunities=opportunities_payload,
                positions=positions_payload,
                portfolio=portfolio_payload,
                risk=risk_payload,
            )
            operational_payload = self.operational.assess(
                summary=summary,
                opportunities=opportunities_payload,
                positions=positions_payload,
                rolls=rolls_payload,
                portfolio=portfolio_payload,
                risk=risk_payload,
                generated_at=generated_at,
                now=now or generated_at,
                max_age_seconds=max_age_seconds,
                repository_corruption=repository_corruption,
            )
            alert_payload = self.alerts.build_alerts(
                summary=summary,
                positions=positions_payload,
                portfolio=portfolio_payload,
                risk=risk_payload,
                operational=operational_payload,
                timestamp=generated_at,
            )
            summary = {
                **summary,
                "alert_count": len(alert_payload),
                "critical_alert_count": sum(1 for row in alert_payload if row.get("severity") == "CRITICAL"),
            }
            root = {
                "engine_name": OPTIONS_INCOME_ENGINE_NAME,
                "engine_version": OPTIONS_INCOME_ENGINE_VERSION,
                "mode": "PAPER",
                "generated_at": generated_at,
                "summary": summary,
                "opportunities": opportunities_payload,
                "positions": positions_payload,
                "rolls": rolls_payload,
                "portfolio": portfolio_payload,
                "greeks": greeks_payload,
                "risk": risk_payload,
                "stress_tests": stress_payload,
                "operational_status": operational_payload,
                "alerts": alert_payload,
                "paper_only": True,
                **SAFE_FLAGS,
            }
            root["explainability"] = self.explainability.build(root)
            return root
        except Exception as exc:
            reason = str(exc) or exc.__class__.__name__
            return fail_closed_dashboard(reason=reason, generated_at=generated_at)


def build_options_income_dashboard(**kwargs: Any) -> dict[str, Any]:
    return OptionsIncomeDashboardBuilder().build(**kwargs)


def fail_closed_dashboard(*, reason: str, generated_at: str = DEFAULT_TIMESTAMP) -> dict[str, Any]:
    return {
        "engine_name": OPTIONS_INCOME_ENGINE_NAME,
        "engine_version": OPTIONS_INCOME_ENGINE_VERSION,
        "mode": "PAPER",
        "generated_at": generated_at,
        "summary": {
            "engine_name": OPTIONS_INCOME_ENGINE_NAME,
            "engine_version": OPTIONS_INCOME_ENGINE_VERSION,
            "mode": "PAPER",
            "paper_only": True,
            "engine_status": "FAIL_CLOSED",
            "data_status": "INVALID",
            "failure_reason": reason,
            **SAFE_FLAGS,
        },
        "opportunities": {},
        "positions": {},
        "rolls": {},
        "portfolio": {},
        "greeks": {},
        "risk": {},
        "stress_tests": {},
        "operational_status": {
            "status": "OFFLINE",
            "failure_reason": reason,
            "certification_status": "UNAVAILABLE",
            "paper_only": True,
            **SAFE_FLAGS,
        },
        "alerts": [
            {
                "alert_id": "OI008-FAIL-CLOSED",
                "severity": "CRITICAL",
                "category": "fail-closed",
                "message": "Options income dashboard failed closed",
                "reason": reason,
                "supporting_metrics": {},
                "affected_entities": ["options_income"],
                "timestamp": generated_at,
                "acknowledged": False,
                "paper_only": True,
                **SAFE_FLAGS,
            }
        ],
        "explainability": [],
        "paper_only": True,
        **SAFE_FLAGS,
    }


def _summary(
    *,
    generated_at: str,
    mode: str,
    opportunities: Mapping[str, Any],
    positions: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    risk: Mapping[str, Any],
) -> dict[str, Any]:
    monthly_target = _number(portfolio.get("monthly_premium_target"))
    expected = _number(portfolio.get("expected_premium"))
    realized = _number(portfolio.get("realized_premium"))
    blockers = _list(portfolio.get("constraint_breaches"))
    unavailable = _list(risk.get("unavailable_risk_data"))
    status = "DEGRADED" if blockers or unavailable or risk.get("risk_status") in {"RED", "UNAVAILABLE"} else "ONLINE"
    data_status = "DEGRADED" if unavailable else "VALID"
    return {
        "engine_name": OPTIONS_INCOME_ENGINE_NAME,
        "engine_version": OPTIONS_INCOME_ENGINE_VERSION,
        "mode": str(mode).strip().upper(),
        "paper_only": True,
        **SAFE_FLAGS,
        "engine_status": status,
        "data_status": data_status,
        "last_update": generated_at,
        "portfolio_count": 1 if portfolio.get("portfolio_id") else 0,
        "active_position_count": int(_number(positions.get("active_position_count"))),
        "completed_position_count": int(_number(positions.get("completed_position_count"))),
        "accepted_opportunity_count": int(_number(opportunities.get("accepted_opportunity_count"))),
        "rejected_opportunity_count": int(_number(opportunities.get("rejected_opportunity_count"))),
        "monthly_income_target": monthly_target,
        "expected_monthly_income": expected,
        "realized_income": realized,
        "remaining_income_target": round(max(0.0, monthly_target - expected - realized), 8),
        "capital_allocated": _number(portfolio.get("capital_allocated")),
        "capital_available": _number(portfolio.get("available_capital")),
        "collateral_reserved": _number(portfolio.get("collateral_reserved")),
        "portfolio_utilization": _number(portfolio.get("portfolio_utilization")),
        "portfolio_yield": _number(portfolio.get("yield_on_collateral")),
        "annualized_yield": _number(portfolio.get("annualized_yield")),
        "risk_status": str(risk.get("risk_status", "UNAVAILABLE")),
        "risk_score": _number(risk.get("risk_score")),
        "approval_status": str(risk.get("approval_status", "REJECTED_INVALID_DATA")),
        "alert_count": 0,
        "critical_alert_count": 0,
    }


def _validate_posture(
    mode: str,
    execution_allowed: bool,
    advisory_only: bool,
    live_trading_blocked: bool,
    broker_execution_armed: bool,
) -> None:
    if str(mode or "").strip().upper() != "PAPER":
        raise OptionsIncomeDashboardError("live mode is rejected")
    if advisory_only is not True or execution_allowed is not False or live_trading_blocked is not True or broker_execution_armed is not False:
        raise OptionsIncomeDashboardError("unsafe execution posture")


def _validate_dashboard_inputs(portfolio: Mapping[str, Any], positions: Mapping[str, Any], risk: Mapping[str, Any]) -> None:
    if not portfolio.get("portfolio_id"):
        raise OptionsIncomeDashboardError("missing portfolio")
    if _number(portfolio.get("capital_allocated")) < 0.0 or _number(portfolio.get("collateral_reserved")) < 0.0:
        raise OptionsIncomeDashboardError("negative capital or collateral")
    seen: set[str] = set()
    for row in _list(positions.get("active_positions")) + _list(positions.get("completed_positions")):
        item = _mapping(row)
        position_id = str(item.get("position_id", "")).strip()
        if not position_id:
            raise OptionsIncomeDashboardError("missing position identifier")
        if position_id in seen:
            raise OptionsIncomeDashboardError("duplicate position identifier")
        seen.add(position_id)
        if item.get("strategy_type") not in {"COVERED_CALL", "CASH_SECURED_PUT"}:
            raise OptionsIncomeDashboardError("unsupported strategy")
        if item.get("state") not in {"CREATED", "APPROVED", "OPEN", "ACTIVE", "EXPIRING", "ASSIGNED", "EXERCISED", "EXPIRED_WORTHLESS", "CLOSED_EARLY", "COMPLETED"}:
            raise OptionsIncomeDashboardError("invalid lifecycle state")
        if _number(item.get("premium_received")) < 0.0 or _number(item.get("premium_remaining")) < 0.0:
            raise OptionsIncomeDashboardError("negative premium")
    if not risk.get("greeks_by_underlying"):
        raise OptionsIncomeDashboardError("missing Greeks")
    if risk.get("iv_availability") == "UNAVAILABLE":
        raise OptionsIncomeDashboardError("missing IV")


__all__ = [
    "OptionsIncomeDashboardBuilder",
    "OptionsIncomeDashboardError",
    "build_options_income_dashboard",
    "fail_closed_dashboard",
]
