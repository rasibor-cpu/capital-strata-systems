from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from dashboard.runtime._utils import safe_float, safe_int


def build_account_payload(
    *,
    cash_balance: Any = 0.0,
    total_equity: Any = 0.0,
    buying_power: Any = 0.0,
    margin_used: Any = 0.0,
    available_margin: Any = 0.0,
    currency: Any = "USD",
    broker: Any = "NONE",
    account_mode: Any = "paper",
) -> Dict[str, Any]:
    return {
        "cash_balance": safe_float(cash_balance),
        "total_equity": safe_float(total_equity),
        "buying_power": safe_float(buying_power),
        "margin_used": safe_float(margin_used),
        "available_margin": safe_float(available_margin),
        "currency": str(currency or "USD"),
        "broker": str(broker or "NONE"),
        "account_mode": str(account_mode or "paper"),
    }


def build_broker_payload(
    *,
    selected_broker: Any = "NONE",
    broker_mode: Any = "paper",
    connected: Any = False,
    live_trading_enabled: Any = False,
    last_heartbeat: Any = "",
) -> Dict[str, Any]:
    return {
        "selected_broker": str(selected_broker or "NONE"),
        "broker_mode": str(broker_mode or "paper"),
        "connected": bool(connected),
        "live_trading_enabled": bool(live_trading_enabled),
        "last_heartbeat": str(last_heartbeat or ""),
    }


def build_positions_payload(
    positions: Iterable[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    normalized = []

    for position in positions or []:
        normalized.append(
            {
                "symbol": str(position.get("symbol", "UNKNOWN")),
                "asset_class": str(position.get("asset_class", "UNKNOWN")),
                "side": str(position.get("side", "UNKNOWN")),
                "qty": safe_float(position.get("qty", position.get("quantity", 0.0))),
                "entry_price": safe_float(
                    position.get("entry_price", position.get("entry", 0.0))
                ),
                "current_price": safe_float(
                    position.get(
                        "current_price",
                        position.get("mark_price", position.get("entry_price", 0.0)),
                    )
                ),
                "unrealized_pnl": safe_float(position.get("unrealized_pnl", 0.0)),
                "realized_pnl": safe_float(position.get("realized_pnl", 0.0)),
            }
        )

    return {"positions": normalized}


def build_market_payload(**values: Any) -> Dict[str, Any]:
    payload = {
        "trend_state": "UNKNOWN",
        "volatility_state": "UNKNOWN",
        "liquidity_state": "UNKNOWN",
        "mean_reversion_state": "UNKNOWN",
        "probability_state": "UNKNOWN",
        "velocity_state": "UNKNOWN",
        "vwap_state": "UNKNOWN",
        "vwap_distance": 0.0,
        "vwap_elasticity": 0.0,
        "momentum_state": "UNKNOWN",
        "pressure_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
        "regime_state": "UNKNOWN",
        "spread_state": "UNKNOWN",
        "execution_cost_state": "UNKNOWN",
        "signal_confluence_state": "UNKNOWN",
    }
    payload.update(values)
    payload["vwap_distance"] = safe_float(payload.get("vwap_distance"))
    payload["vwap_elasticity"] = safe_float(payload.get("vwap_elasticity"))
    return payload


def build_governance_payload(**values: Any) -> Dict[str, Any]:
    payload = {
        "governance_enabled": True,
        "session_locked": False,
        "defensive_mode_active": False,
        "unified_trade_gate_active": True,
        "audit_enabled": True,
        "last_governance_event": "",
    }
    payload.update(values)
    return payload


def build_risk_payload(**values: Any) -> Dict[str, Any]:
    payload = {
        "risk_state": "NORMAL",
        "gate_status": "OPEN",
        "total_exposure": 0.0,
        "exposure_utilization_pct": 0.0,
        "current_drawdown_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "daily_loss_limit": 0.0,
        "position_limit": 0,
        "exposure_limit": 0.0,
        "risk_limits_breached": [],
    }
    payload.update(values)

    for key in [
        "total_exposure",
        "exposure_utilization_pct",
        "current_drawdown_pct",
        "max_drawdown_pct",
        "daily_loss_limit",
        "exposure_limit",
    ]:
        payload[key] = safe_float(payload.get(key))

    payload["position_limit"] = safe_int(payload.get("position_limit"))
    return payload


def build_execution_payload(**values: Any) -> Dict[str, Any]:
    payload = {
        "execution_state": "IDLE",
        "accepted_trade_count": 0,
        "rejected_trade_count": 0,
        "pending_trade_count": 0,
        "total_execution_cost": 0.0,
        "slippage_cost": 0.0,
        "spread_cost": 0.0,
        "fee_cost": 0.0,
        "avg_slippage_bps": 0.0,
        "avg_spread_bps": 0.0,
        "execution_cost_state": "UNKNOWN",
        "last_execution_event": "",
    }
    payload.update(values)

    for key in [
        "total_execution_cost",
        "slippage_cost",
        "spread_cost",
        "fee_cost",
        "avg_slippage_bps",
        "avg_spread_bps",
    ]:
        payload[key] = safe_float(payload.get(key))

    for key in [
        "accepted_trade_count",
        "rejected_trade_count",
        "pending_trade_count",
    ]:
        payload[key] = safe_int(payload.get(key))

    return payload


def build_session_payload(**values: Any) -> Dict[str, Any]:
    payload = {
        "session_id": "",
        "user_id": "",
        "role": "TRADER",
        "cycle_number": 0,
        "engine_mode": "SAFE",
        "live_or_paper": "paper",
    }
    payload.update(values)
    payload["cycle_number"] = safe_int(payload.get("cycle_number"))
    return payload


def build_diagnostics_payload(
    *,
    message: Any = "Runtime diagnostics payload received",
    **values: Any,
) -> Dict[str, Any]:
    payload = {"message": str(message)}
    payload.update(values)
    return payload


def build_dashboard_payloads(
    *,
    account_payload: Mapping[str, Any] | None = None,
    broker_payload: Mapping[str, Any] | None = None,
    positions_payload: Mapping[str, Any] | None = None,
    market_payload: Mapping[str, Any] | None = None,
    governance_payload: Mapping[str, Any] | None = None,
    risk_payload: Mapping[str, Any] | None = None,
    execution_payload: Mapping[str, Any] | None = None,
    session_payload: Mapping[str, Any] | None = None,
    diagnostics_payload: Mapping[str, Any] | None = None,
) -> Dict[str, Dict[str, Any]]:
    return {
        "account_payload": build_account_payload(**dict(account_payload or {})),
        "broker_payload": build_broker_payload(**dict(broker_payload or {})),
        "positions_payload": build_positions_payload(
            dict(positions_payload or {}).get("positions", [])
        ),
        "market_payload": build_market_payload(**dict(market_payload or {})),
        "governance_payload": build_governance_payload(
            **dict(governance_payload or {})
        ),
        "risk_payload": build_risk_payload(**dict(risk_payload or {})),
        "execution_payload": build_execution_payload(**dict(execution_payload or {})),
        "session_payload": build_session_payload(**dict(session_payload or {})),
        "diagnostics_payload": build_diagnostics_payload(
            **dict(diagnostics_payload or {})
        ),
    }
