"""
DashboardState API bridge for the CSS institutional UI shadow console.

The route is intentionally read-only. It does not call brokers, place orders,
or alter engine state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Dict

from fastapi import APIRouter

try:
    from dashboard.runtime.dashboard_state import (
        BrokerState,
        DashboardState,
        GovernanceState,
        MarketStatePayload,
    )
except ModuleNotFoundError:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from dashboard.runtime.dashboard_state import (
        BrokerState,
        DashboardState,
        GovernanceState,
        MarketStatePayload,
    )


router = APIRouter(prefix="/api/v1", tags=["dashboard-state"])


def _sample_dashboard_state() -> DashboardState:
    now = datetime.now(timezone.utc).isoformat()
    state = DashboardState(
        session_id="CSS-SHADOW-SESSION",
        user_id="demo_user",
        role="TRADER",
        cycle_number=42,
        engine_mode="SAFE",
        live_or_paper="paper",
        cash_balance=10000.0,
        total_equity=10250.0,
        realized_pnl=0.0,
        unrealized_pnl=27.5,
        total_open_positions=2,
        open_positions_by_asset={
            "CRYPTO": 1,
            "FX": 1,
            "FUTURES": 0,
            "OPTIONS": 0,
        },
        broker_state=BrokerState(
            selected_broker="COINBASE_SIM",
            broker_mode="paper",
            connected=True,
            live_trading_enabled=False,
            last_heartbeat=now,
        ),
        governance_state=GovernanceState(
            governance_enabled=True,
            session_locked=False,
            defensive_mode_active=False,
            unified_trade_gate_active=True,
            audit_enabled=True,
            last_governance_event="Shadow API governance state hydrated",
        ),
        global_market_state=MarketStatePayload(
            trend_state="UPTREND",
            volatility_state="NORMAL",
            liquidity_state="HEALTHY",
            mean_reversion_state="NEUTRAL",
            probability_state="FAVORABLE",
            velocity_state="RISING",
            vwap_state="ABOVE_VWAP",
            vwap_distance=0.0125,
            vwap_elasticity=0.83,
            momentum_state="POSITIVE",
            pressure_state="BUY_PRESSURE",
            acceleration_state="STABLE",
            regime_state="RISK_ON",
            spread_state="TIGHT",
            execution_cost_state="ACCEPTABLE",
            signal_confluence_state="CONFIRMED",
        ),
    )

    state.last_scan_results["account_summary"] = {
        "broker": "COINBASE_SIM",
        "account_mode": "paper",
        "currency": "USD",
        "cash_balance": 10000.0,
        "total_equity": 10250.0,
        "buying_power": 5000.0,
        "margin_used": 1000.0,
        "available_margin": 4000.0,
    }
    state.last_scan_results["pnl_summary"] = {
        "realized_pnl": 0.0,
        "unrealized_pnl": 27.5,
        "net_pnl": 27.5,
        "winners": 2,
        "losers": 0,
        "win_rate": 100.0,
    }
    state.last_scan_results["risk_summary"] = {
        "risk_state": "NORMAL",
        "gate_status": "OPEN",
        "total_exposure": 4362.5,
        "exposure_utilization_pct": 42.56,
        "current_drawdown_pct": 0.35,
        "max_drawdown_pct": 2.0,
        "daily_loss_limit": 500.0,
        "position_limit": 10,
        "exposure_limit": 25000.0,
        "risk_limits_breached": [],
    }
    state.last_scan_results["execution_summary"] = {
        "execution_state": "READY",
        "accepted_trade_count": 2,
        "rejected_trade_count": 0,
        "pending_trade_count": 0,
        "total_execution_cost": 1.25,
        "slippage_cost": 0.5,
        "spread_cost": 0.45,
        "fee_cost": 0.3,
        "avg_slippage_bps": 1.2,
        "avg_spread_bps": 0.8,
        "execution_cost_state": "ACCEPTABLE",
        "last_execution_event": "Shadow API execution summary hydrated",
    }

    return state


def build_shadow_dashboard_payload() -> Dict[str, Any]:
    state = _sample_dashboard_state()
    payload = state.to_dict()
    payload["shadow_mode"] = True
    payload["source"] = "DashboardState.to_dict shadow bridge"
    payload["positions"] = [
        {
            "symbol": "BTC-USD",
            "asset_class": "CRYPTO",
            "side": "LONG",
            "qty": 0.05,
            "entry_price": 65000.0,
            "mark_price": 65500.0,
            "unrealized_pnl": 25.0,
            "exposure": 3275.0,
        },
        {
            "symbol": "EUR_USD",
            "asset_class": "FX",
            "side": "SHORT",
            "qty": 1000,
            "entry_price": 1.09,
            "mark_price": 1.0875,
            "unrealized_pnl": 2.5,
            "exposure": 1087.5,
        },
    ]
    payload["opportunities"] = [
        {
            "symbol": "ETH-USD",
            "asset_class": "CRYPTO",
            "side": "WATCH",
            "score": 82,
            "signal": "VWAP support with confirmed pressure",
        },
        {
            "symbol": "CL",
            "asset_class": "FUTURES",
            "side": "HOLD",
            "score": 64,
            "signal": "Cost state acceptable, momentum cooling",
        },
    ]
    payload["alerts"] = [
        {
            "level": "info",
            "title": "Shadow mode active",
            "detail": "UI is not authorized to route orders.",
        },
        {
            "level": "warning",
            "title": "Live order control disabled",
            "detail": "Enablement must come from CSS governance and execution gates.",
        },
    ]
    payload["equity_series"] = [
        10000,
        10022,
        10015,
        10080,
        10125,
        10210,
        10250,
    ]
    payload["risk_bands"] = [
        {"label": "Drawdown", "value": 0.35, "limit": 2.0},
        {"label": "Exposure", "value": 42.56, "limit": 100.0},
        {"label": "Positions", "value": 2, "limit": 10},
    ]
    return payload


@router.get("/dashboard-state")
def dashboard_state() -> Dict[str, Any]:
    return build_shadow_dashboard_payload()


@router.get("/operational-identity")
def operational_identity() -> Dict[str, Any]:
    return {
        "payload_version": "css.operational_identity.v1",
        "identity": "LIVE CAPITAL ACTIVE",
        "status": "active",
        "mode": "read_only",
    }
