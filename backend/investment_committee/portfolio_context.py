from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def build_portfolio_context(dashboard_payload: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _mapping(dashboard_payload)
    account = _mapping(payload.get("account_summary"))
    risk = _mapping(payload.get("risk_summary"))
    position_state = _mapping(payload.get("position_state"))
    portfolio = _mapping(payload.get("portfolio_summary"))
    market = _mapping(payload.get("market_summary"))
    broker = _mapping(payload.get("broker_summary"))
    positions = _list(position_state.get("positions"))

    available_capital = _number(
        _first(account, "buying_power", "available_margin", "cash_balance", default=portfolio.get("available_capital", 0.0))
    )
    equity = _number(_first(account, "total_equity", default=portfolio.get("equity", available_capital)))
    exposure = _number(_first(position_state, "total_exposure", default=portfolio.get("total_exposure", 0.0)))
    max_portfolio_exposure_pct = _ratio(risk.get("max_portfolio_exposure_pct", 0.80))
    cash_reserve_pct = _ratio(risk.get("cash_reserve_pct", 0.20))
    deployable_capital = max(0.0, min(available_capital * max_portfolio_exposure_pct, available_capital * (1.0 - cash_reserve_pct)))

    return {
        "available_capital": round(max(0.0, available_capital), 6),
        "deployable_capital": round(deployable_capital, 6),
        "equity": round(max(0.0, equity), 6),
        "current_exposure": round(max(0.0, exposure), 6),
        "cash_reserve_pct": cash_reserve_pct,
        "max_portfolio_exposure_pct": max_portfolio_exposure_pct,
        "max_single_position_pct": _ratio(risk.get("max_single_position_pct", 0.25)),
        "max_expected_drawdown": _ratio(risk.get("max_expected_drawdown", 0.08)),
        "max_risk_budget_consumption": _ratio(risk.get("max_risk_budget_consumption", 0.35)),
        "max_sector_concentration": _ratio(risk.get("max_sector_concentration", risk.get("sector_limit_pct", 0.40))),
        "max_portfolio_correlation": _ratio(risk.get("max_portfolio_correlation", 0.75)),
        "min_committee_score": _number(risk.get("min_committee_score", 60.0), default=60.0),
        "min_approval_score": _number(risk.get("min_committee_approval_score", 75.0), default=75.0),
        "min_low_priority_score": _number(risk.get("min_committee_low_priority_score", 65.0), default=65.0),
        "max_approved_opportunities": int(_number(risk.get("max_committee_approved_opportunities", 3), default=3)),
        "market_regime": str(market.get("regime_state", market.get("trend_state", "UNKNOWN"))),
        "market_health": _market_health(market),
        "operational_readiness": _operational_readiness(broker),
        "exposure_by_asset_class": _exposure_by(positions, "asset_class"),
        "exposure_by_sector": _exposure_by(positions, "sector"),
        "advisory_only": True,
        "execution_allowed": False,
        "live_trading_blocked": True,
        "broker_execution_armed": False,
    }


def _exposure_by(positions: Sequence[Any], field: str) -> dict[str, float]:
    exposure: dict[str, float] = {}
    for row in positions:
        item = _mapping(row)
        key = str(item.get(field) or item.get("asset_class") or "UNKNOWN").upper()
        amount = abs(_number(_first(item, "exposure", "market_value", "notional", default=0.0)))
        exposure[key] = round(exposure.get(key, 0.0) + amount, 6)
    return exposure


def _market_health(market: Mapping[str, Any]) -> float:
    states = [
        str(market.get("liquidity_state", "")).upper(),
        str(market.get("spread_state", "")).upper(),
        str(market.get("volatility_state", "")).upper(),
        str(market.get("regime_state", "")).upper(),
    ]
    if any(state in {"RED", "STRESSED", "RISK_OFF", "LOW"} for state in states):
        return 0.35
    if any(state in {"GREEN", "RISK_ON", "HIGH", "HEALTHY"} for state in states):
        return 0.85
    return 0.60


def _operational_readiness(broker: Mapping[str, Any]) -> float:
    if broker.get("execution_allowed") is True or broker.get("can_live_execute") is True:
        return 0.0
    health = str(broker.get("broker_health", broker.get("api_health", "UNKNOWN"))).upper()
    if health in {"GREEN", "OPERATIONAL"}:
        return 0.90
    if health in {"AMBER", "DEGRADED", "UNKNOWN"}:
        return 0.65
    return 0.30


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
        numeric /= 100.0
    return max(0.0, min(1.0, numeric))
