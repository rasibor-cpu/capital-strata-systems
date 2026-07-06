from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import Any

from dashboard.runtime.dashboard_state import (
    DASHBOARD_PAYLOAD_SCHEMA,
    DASHBOARD_PAYLOAD_VERSION,
    DashboardState,
)
from dashboard.runtime.broker_balance_reconciliation import (
    build_broker_reconciliation_payload,
)
from backend.runtime.broker_parity_validator import broker_parity_payload
from backend.analytics.portfolio_correlation_engine import (
    PortfolioCorrelationEngine,
    PortfolioCorrelationEngineError,
)
from backend.runtime.live_micro_pilot_governor import live_micro_pilot_status
from backend.validation.live_readiness_certification import (
    live_readiness_certification_status,
)

try:
    from backend.scanner.unified_market_scanner import UnifiedMarketScanner
except Exception:
    UnifiedMarketScanner = None


FRONTEND_CONTRACT_VERSION = "1.0.0"
FRONTEND_CONTRACT_SCHEMA = "css.frontend.contract.v1"

CONTRACT_NAME = "CSS Institutional Frontend Payload"
CONTRACT_VERSION = FRONTEND_CONTRACT_VERSION
CONTRACT_TIMESTAMP = "2026-05-08T00:00:00Z"
FRONTEND_SECTIONS = (
    "account_summary",
    "trade",
    "positions",
    "pnl_summary",
    "portfolio_summary",
    "portfolio_greeks",
    "risk",
    "governance",
    "market",
    "execution",
    "opportunities",
    "trade_summary",
    "session_command_centre",
    "live_micro_pilot",
    "live_readiness_certification",
    "broker",
    "broker_parity",
    "coinbase_live_validation",
    "broker_reconciliation",
    "analytics",
)

DATA_UNAVAILABLE = "DATA UNAVAILABLE"

_TRADE_UNIVERSE_CACHE: dict[str, Any] = {
    "updated_at": 0.0,
    "items": [],
}
_TRADE_UNIVERSE_CACHE_TTL_SECONDS = 5.0


@dataclass(frozen=True)
class FrontendEnvelope:
    payload_version: str = FRONTEND_CONTRACT_VERSION
    payload_schema: str = FRONTEND_CONTRACT_SCHEMA
    dashboard_payload_version: str = DASHBOARD_PAYLOAD_VERSION
    dashboard_payload_schema: str = DASHBOARD_PAYLOAD_SCHEMA
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    message_type: str = "dashboard_snapshot"
    source: str = "dashboard.runtime.frontend_contract"
    contract_name: str = CONTRACT_NAME
    contract_version: str = CONTRACT_VERSION
    contract_timestamp: str = CONTRACT_TIMESTAMP
    schema_metadata: dict[str, str] = field(
        default_factory=lambda: {
            "strict_typing": "True",
            "enforces_payload_versioning": "True",
            "compatibility": "Backward compatible with CSS legacy dashboards",
        }
    )


@dataclass(frozen=True)
class WebsocketDelta:
    message_type: str
    payload_version: str
    generated_at: str
    changed_sections: list[str]
    data: dict[str, Any]
    sequence: int = 0
    stale_after_ms: int = 15000

    def as_dict(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def build_frontend_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
) -> dict[str, Any]:
    dashboard_payload = _dashboard_payload(dashboard_state)
    envelope = FrontendEnvelope()

    payload = {
        "payload_version": envelope.payload_version,
        "payload_schema": envelope.payload_schema,
        "dashboard_payload_version": dashboard_payload.get(
            "payload_version",
            DASHBOARD_PAYLOAD_VERSION,
        ),
        "dashboard_payload_schema": dashboard_payload.get(
            "payload_schema",
            DASHBOARD_PAYLOAD_SCHEMA,
        ),
        "generated_at": envelope.generated_at,
        "message_type": envelope.message_type,
        "source_metadata": {
            "source": envelope.source,
            "canonical_bridge": "DashboardState.to_dict",
            "transport": "snapshot",
            "frontend_safe": True,
            "secrets_redacted": True,
        },
        "contract_name": envelope.contract_name,
        "contract_version": envelope.contract_version,
        "contract_timestamp": envelope.contract_timestamp,
        "schema_metadata": envelope.schema_metadata,
        "session": _mapping(dashboard_payload.get("session")),
        "session_id": str(dashboard_payload.get("session_id", "")),
        "resolved_mode": str(dashboard_payload.get("resolved_mode", "paper")),
        "sections": {
            "account_summary": account_summary(dashboard_payload),
            "trade": trade(dashboard_payload),
            "positions": positions(dashboard_payload),
            "pnl_summary": pnl_summary(dashboard_payload),
            "portfolio_summary": portfolio_summary(dashboard_payload),
            "portfolio_greeks": portfolio_greeks(dashboard_payload),
            "risk": risk(dashboard_payload),
            "governance": governance(dashboard_payload),
            "market": market(dashboard_payload),
            "execution": execution(dashboard_payload),
            "opportunities": opportunities(dashboard_payload),
            "trade_summary": trade_summary(dashboard_payload),
            "session_command_centre": session_command_centre(dashboard_payload),
            "live_micro_pilot": live_micro_pilot(dashboard_payload),
            "live_readiness_certification": live_readiness_certification(dashboard_payload),
            "broker": broker(dashboard_payload),
            "broker_parity": broker_parity(dashboard_payload),
            "coinbase_live_validation": coinbase_live_validation(dashboard_payload),
            "oanda_live_validation": oanda_live_validation(dashboard_payload),
            "broker_reconciliation": broker_reconciliation(dashboard_payload),
            "analytics": analytics(dashboard_payload),
        },
    }

    return payload


def account_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    account = _mapping(dashboard_payload.get("account_summary"))
    return {
        "cash_balance": _number(account.get("cash_balance")),
        "total_equity": _number(account.get("total_equity")),
        "buying_power": _number(account.get("buying_power")),
        "margin_used": _number(account.get("margin_used")),
        "available_margin": _number(account.get("available_margin")),
        "currency": str(account.get("currency", "USD")),
        "broker": str(account.get("broker", "NONE")),
        "account_mode": str(account.get("account_mode", "paper")),
    }


def trade(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    opportunities_by_symbol = {
        str(_mapping(item).get("symbol", "")).upper(): _mapping(item)
        for item in _list(dashboard_payload.get("opportunities"))
    }
    position_state = _mapping(dashboard_payload.get("position_state"))
    active_symbols = {
        str(symbol).upper() for symbol in _list(position_state.get("active_symbols"))
    }

    universe_rows = _universe_rows_for_trade(opportunities_by_symbol)

    rows: list[dict[str, Any]] = []
    for item in universe_rows:
        symbol = str(item.get("symbol", "UNKNOWN")).upper()
        opportunity = opportunities_by_symbol.get(symbol, {})

        rows.append(
            {
                "symbol": symbol,
                "asset_class": str(item.get("asset_class", "UNKNOWN")),
                "price": _number(item.get("price")),
                "vwap": _number(item.get("vwap")),
                "vwap_dev": _number(item.get("vwap_dev")),
                "spread_bps": _number(item.get("spread_bps")),
                "signal": str(opportunity.get("signal", "WATCH")),
                "status": str(opportunity.get("status", "MONITOR_ONLY")),
                "in_position": symbol in active_symbols,
            }
        )

    asset_classes = sorted(
        {str(row.get("asset_class", "UNKNOWN")) for row in rows}
    )

    return {
        "source": "backend.scanner.unified_market_scanner.UnifiedMarketScanner",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "asset_classes": asset_classes,
        "items": rows,
    }


def _universe_rows_for_trade(opportunities_by_symbol: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    if opportunities_by_symbol:
        rows: list[dict[str, Any]] = []
        for symbol in sorted(opportunities_by_symbol.keys()):
            row = _mapping(opportunities_by_symbol.get(symbol))
            rows.append(
                {
                    "symbol": symbol,
                    "asset_class": str(row.get("asset_class", "UNKNOWN")).upper(),
                    "price": _number(row.get("price")),
                    "vwap": _number(row.get("vwap")),
                    "vwap_dev": _number(row.get("vwap_dev")),
                    "spread_bps": _number(row.get("spread_bps")),
                }
            )
        if rows:
            return rows

    return _get_canonical_universe_rows()


def _get_canonical_universe_rows() -> list[dict[str, Any]]:
    now = time.time()
    cache_age = now - float(_TRADE_UNIVERSE_CACHE.get("updated_at", 0.0))
    if cache_age < _TRADE_UNIVERSE_CACHE_TTL_SECONDS:
        return list(_TRADE_UNIVERSE_CACHE.get("items", []))

    rows: list[dict[str, Any]] = []
    if UnifiedMarketScanner is not None:
        try:
            scan_rows = UnifiedMarketScanner().scan()
            for item in _list(scan_rows):
                mapped = _mapping(item)
                symbol = str(mapped.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "asset_class": str(mapped.get("asset_class", "UNKNOWN")).upper(),
                        "price": _number(mapped.get("price")),
                        "vwap": _number(mapped.get("vwap")),
                        "vwap_dev": _number(mapped.get("vwap_dev")),
                        "spread_bps": _number(mapped.get("spread_bps")),
                    }
                )
        except Exception:
            rows = []

    if not rows:
        rows = [
            {"symbol": "BTC-USD", "asset_class": "CRYPTO", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "ETH-USD", "asset_class": "CRYPTO", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "SOL-USD", "asset_class": "CRYPTO", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "EUR_USD", "asset_class": "FX", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "GBP_USD", "asset_class": "FX", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "USD_JPY", "asset_class": "FX", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "ES", "asset_class": "FUTURES", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "NQ", "asset_class": "FUTURES", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
            {"symbol": "CL", "asset_class": "FUTURES", "price": 0.0, "vwap": 0.0, "vwap_dev": 0.0, "spread_bps": 0.0},
        ]

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped[str(row.get("symbol", "")).upper()] = row

    canonical_rows = sorted(
        deduped.values(),
        key=lambda row: (str(row.get("asset_class", "")), str(row.get("symbol", ""))),
    )

    _TRADE_UNIVERSE_CACHE["updated_at"] = now
    _TRADE_UNIVERSE_CACHE["items"] = canonical_rows
    return list(canonical_rows)


def positions(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    open_positions = _mapping(dashboard_payload.get("open_positions"))
    by_asset = _mapping(open_positions.get("by_asset"))
    position_state = _mapping(dashboard_payload.get("position_state"))
    asset_summaries = _mapping(dashboard_payload.get("asset_class_summaries"))
    items = []

    for position in _list(position_state.get("positions")):
        position_payload = _mapping(position)
        items.append(
            {
                "symbol": str(position_payload.get("symbol", "UNKNOWN")),
                "asset_class": str(
                    position_payload.get("asset_class", "UNKNOWN")
                ),
                "side": str(position_payload.get("side", "UNKNOWN")),
                "qty": _number(position_payload.get("qty")),
                "entry_price": _number(position_payload.get("entry_price")),
                "current_price": _number(position_payload.get("current_price")),
                "exposure": _number(position_payload.get("exposure")),
                "realized_pnl": _number(position_payload.get("realized_pnl")),
                "unrealized_pnl": _number(
                    position_payload.get("unrealized_pnl")
                ),
            }
        )

    for asset_class, summary in asset_summaries.items():
        if items:
            break

        summary_payload = _mapping(summary)
        items.append(
            {
                "asset_class": str(asset_class),
                "open_positions": _integer(
                    summary_payload.get(
                        "open_positions",
                        by_asset.get(str(asset_class), 0),
                    )
                ),
                "realized_pnl": _number(summary_payload.get("realized_pnl")),
                "unrealized_pnl": _number(summary_payload.get("unrealized_pnl")),
                "exposure": _number(summary_payload.get("exposure")),
            }
        )

    return {
        "total": _integer(
            open_positions.get("total", position_state.get("open_count"))
        ),
        "by_asset": {str(key): _integer(value) for key, value in by_asset.items()},
        "long_count": _integer(position_state.get("long_count")),
        "short_count": _integer(position_state.get("short_count")),
        "winner_count": _integer(position_state.get("winner_count")),
        "loser_count": _integer(position_state.get("loser_count")),
        "active_symbols": _string_list(position_state.get("active_symbols")),
        "items": items,
    }


def pnl_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    pnl = _mapping(dashboard_payload.get("pnl_summary"))
    return {
        "realized_pnl": _number(pnl.get("realized_pnl")),
        "unrealized_pnl": _number(pnl.get("unrealized_pnl")),
        "net_pnl": _number(pnl.get("net_pnl")),
        "total_exposure": _number(pnl.get("total_exposure")),
        "exposure_utilization_pct": _number(
            pnl.get("exposure_utilization_pct")
        ),
        "winner_count": _integer(pnl.get("winner_count")),
        "loser_count": _integer(pnl.get("loser_count")),
        "win_rate_pct": _number(pnl.get("win_rate_pct")),
        "account_equity": _number(pnl.get("account_equity")),
    }


def portfolio_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    account = _mapping(dashboard_payload.get("account_summary"))
    pnl = _mapping(dashboard_payload.get("pnl_summary"))
    positions_state = _mapping(dashboard_payload.get("position_state"))

    cash = _number(account.get("cash_balance"))
    equity = _number(account.get("total_equity"))
    buying_power = _number(account.get("buying_power"))
    margin_used = _number(account.get("margin_used"))
    total_exposure = _number(pnl.get("total_exposure", positions_state.get("total_exposure")))

    available_capital = buying_power if buying_power > 0 else max(cash - total_exposure, 0.0)
    allocated_capital = max(total_exposure, margin_used)
    reserved_capital = max(equity - available_capital - allocated_capital, 0.0)

    positions = _normalized_positions_for_correlation(positions_state)
    concentration_score = 0.0
    correlation_score = 0.0
    portfolio_status = "NO_POSITIONS"
    source = "dashboard.runtime.frontend_contract"

    try:
        if positions:
            correlation = PortfolioCorrelationEngine().analyze_portfolio(positions)
            concentration_score = _number(correlation.get("concentration_score"))
            correlation_score = _number(correlation.get("correlation_score"))
            portfolio_status = "OK"
            source = "backend.analytics.portfolio_correlation_engine"
    except (PortfolioCorrelationEngineError, ValueError, TypeError):
        portfolio_status = "SOURCE_UNAVAILABLE"
        source = "SOURCE_UNAVAILABLE"
        concentration_score = 0.0
        correlation_score = 0.0

    diversification_score = max(0.0, min(1.0, 1.0 - concentration_score))
    risk_score = max(0.0, min(1.0, (concentration_score + correlation_score) / 2.0))
    capital_efficiency = (allocated_capital / equity) if equity > 0 else 0.0

    if portfolio_status == "SOURCE_UNAVAILABLE":
        portfolio_health = "SOURCE_UNAVAILABLE"
    elif risk_score <= 0.35:
        portfolio_health = "STABLE"
    elif risk_score <= 0.65:
        portfolio_health = "WATCH"
    else:
        portfolio_health = "DEFENSIVE"

    return {
        "total_exposure": round(total_exposure, 8),
        "cash": round(cash, 8),
        "equity": round(equity, 8),
        "available_capital": round(available_capital, 8),
        "allocated_capital": round(allocated_capital, 8),
        "reserved_capital": round(reserved_capital, 8),
        "diversification_score": round(diversification_score, 8),
        "portfolio_health": portfolio_health,
        "risk_score": round(risk_score, 8),
        "capital_efficiency": round(capital_efficiency, 8),
        "correlation_score": round(correlation_score, 8),
        "concentration_score": round(concentration_score, 8),
        "portfolio_status": portfolio_status,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


def portfolio_greeks(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    positions_state = _mapping(dashboard_payload.get("position_state"))
    raw_positions = positions_state.get("positions")
    positions = _list(raw_positions)
    underlying_exposure = 0.0
    options_exposure = 0.0
    net = {
        "delta": 0.0,
        "gamma": 0.0,
        "theta": 0.0,
        "vega": 0.0,
        "rho": 0.0,
    }

    try:
        if raw_positions is not None and not isinstance(raw_positions, list):
            raise ValueError("positions must be a list")

        source_set: set[str] = set()
        option_count = 0
        for raw in positions:
            row = _mapping(raw)
            asset_class = str(row.get("asset_class", "UNKNOWN")).strip().upper()
            exposure = _number(row.get("exposure", _number(row.get("qty")) * _number(row.get("current_price"))))

            if asset_class == "OPTIONS":
                option_count += 1
                options_exposure += abs(exposure)
                for greek in ("delta", "gamma", "theta", "vega", "rho"):
                    value = row.get(greek)
                    if value is None:
                        continue
                    net[greek] += _number(value)

                source_value = str(row.get("greeks_source", "")).strip().upper()
                if source_value and source_value != "UNKNOWN":
                    source_set.add(source_value)
            else:
                underlying_exposure += abs(exposure)

        if option_count == 0:
            greeks_status = "NO_OPTIONS"
            source = "position_state"
        else:
            greeks_status = "OK"
            source = "MIXED" if len(source_set) > 1 else (next(iter(source_set)) if source_set else "UNKNOWN")

    except Exception:
        greeks_status = "SOURCE_UNAVAILABLE"
        source = "SOURCE_UNAVAILABLE"
        option_count = 0
        options_exposure = 0.0
        underlying_exposure = 0.0
        net = {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0,
        }

    hedge_ratio = abs(net["delta"]) / underlying_exposure if underlying_exposure > 0 else 0.0

    return {
        "delta": round(net["delta"], 8),
        "gamma": round(net["gamma"], 8),
        "theta": round(net["theta"], 8),
        "vega": round(net["vega"], 8),
        "rho": round(net["rho"], 8),
        "net_delta": round(net["delta"], 8),
        "net_gamma": round(net["gamma"], 8),
        "net_theta": round(net["theta"], 8),
        "net_vega": round(net["vega"], 8),
        "net_rho": round(net["rho"], 8),
        "options_exposure": round(options_exposure, 8),
        "underlying_exposure": round(underlying_exposure, 8),
        "hedge_ratio": round(hedge_ratio, 8),
        "greeks_status": greeks_status,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


def risk(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    risk_payload = _mapping(dashboard_payload.get("risk_summary"))
    return {
        "risk_state": str(risk_payload.get("risk_state", "NORMAL")),
        "gate_status": str(risk_payload.get("gate_status", "OPEN")),
        "total_exposure": _number(risk_payload.get("total_exposure")),
        "exposure_utilization_pct": _number(
            risk_payload.get("exposure_utilization_pct")
        ),
        "current_drawdown_pct": _number(
            risk_payload.get("current_drawdown_pct")
        ),
        "max_drawdown_pct": _number(risk_payload.get("max_drawdown_pct")),
        "daily_loss_limit": _number(risk_payload.get("daily_loss_limit")),
        "position_limit": _integer(risk_payload.get("position_limit")),
        "exposure_limit": _number(risk_payload.get("exposure_limit")),
        "risk_limits_breached": _string_list(
            risk_payload.get("risk_limits_breached")
        ),
    }


def governance(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    governance_payload = _mapping(dashboard_payload.get("governance_summary"))
    return {
        "governance_enabled": _boolean(
            governance_payload.get("governance_enabled"),
            default=True,
        ),
        "session_locked": _boolean(governance_payload.get("session_locked")),
        "defensive_mode_active": _boolean(
            governance_payload.get("defensive_mode_active")
        ),
        "unified_trade_gate_active": _boolean(
            governance_payload.get("unified_trade_gate_active"),
            default=True,
        ),
        "audit_enabled": _boolean(
            governance_payload.get("audit_enabled"),
            default=True,
        ),
        "last_governance_event": str(
            governance_payload.get("last_governance_event", "")
        ),
    }


def market(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    market_payload = _mapping(dashboard_payload.get("market_summary"))
    defaults = {
        "trend_state": "UNKNOWN",
        "volatility_state": "UNKNOWN",
        "liquidity_state": "UNKNOWN",
        "mean_reversion_state": "UNKNOWN",
        "probability_state": "UNKNOWN",
        "velocity_state": "UNKNOWN",
        "vwap_state": "UNKNOWN",
        "momentum_state": "UNKNOWN",
        "pressure_state": "UNKNOWN",
        "acceleration_state": "UNKNOWN",
        "regime_state": "UNKNOWN",
        "spread_state": "UNKNOWN",
        "execution_cost_state": "UNKNOWN",
        "signal_confluence_state": "UNKNOWN",
    }
    payload = {
        key: str(market_payload.get(key, value))
        for key, value in defaults.items()
    }
    payload["vwap_distance"] = _number(market_payload.get("vwap_distance"))
    payload["vwap_elasticity"] = _number(market_payload.get("vwap_elasticity"))
    return payload


def execution(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    execution_payload = _mapping(dashboard_payload.get("execution_summary"))
    recent_trades = _execution_history(dashboard_payload)
    return {
        "execution_state": str(execution_payload.get("execution_state", "IDLE")),
        "accepted_trade_count": _integer(
            execution_payload.get("accepted_trade_count")
        ),
        "rejected_trade_count": _integer(
            execution_payload.get("rejected_trade_count")
        ),
        "pending_trade_count": _integer(
            execution_payload.get("pending_trade_count")
        ),
        "total_execution_cost": _number(
            execution_payload.get("total_execution_cost")
        ),
        "slippage_cost": _number(execution_payload.get("slippage_cost")),
        "spread_cost": _number(execution_payload.get("spread_cost")),
        "fee_cost": _number(execution_payload.get("fee_cost")),
        "avg_slippage_bps": _number(execution_payload.get("avg_slippage_bps")),
        "avg_spread_bps": _number(execution_payload.get("avg_spread_bps")),
        "execution_cost_state": str(
            execution_payload.get("execution_cost_state", "UNKNOWN")
        ),
        "last_execution_event": str(
            execution_payload.get("last_execution_event", "")
        ),
        "recent_trade_count": len(recent_trades),
        "recent_trades": recent_trades,
    }


def _execution_history(dashboard_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for item in _list(dashboard_payload.get("execution_history")):
        trade = _mapping(item)
        rows.append(
            {
                "timestamp": str(
                    trade.get(
                        "timestamp",
                        trade.get("created_utc", trade.get("recorded_utc", "")),
                    )
                ),
                "symbol": str(trade.get("symbol", "UNKNOWN")),
                "asset_class": str(trade.get("asset_class", "UNKNOWN")),
                "side": str(trade.get("side", "UNKNOWN")),
                "mode": str(trade.get("mode", "paper")),
                "broker": str(trade.get("broker", "CSS")),
                "status": str(trade.get("status", "UNKNOWN")),
                "qty": _number(trade.get("qty")),
                "amount": _number(trade.get("amount")),
                "execution_cost": _number(
                    trade.get("execution_cost", trade.get("cost", 0.0))
                ),
                "source": str(trade.get("source", "DashboardState")),
            }
        )

    return rows


def opportunities(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_opportunities = dashboard_payload.get("opportunities", [])
    if not isinstance(raw_opportunities, list):
        raw_opportunities = []
    items = [_opportunity_item(item) for item in raw_opportunities]
    ranked_items = sorted(
        items,
        key=lambda row: _number(row.get("composite_score", row.get("score", 0.0))),
        reverse=True,
    )
    green_items = [item for item in ranked_items if _opportunity_bucket(item) == "GREEN"]
    amber_items = [item for item in ranked_items if _opportunity_bucket(item) == "AMBER"]
    display_items = green_items if green_items else amber_items
    display_state = "GREEN_APPROVED" if green_items else "AMBER_WATCH"
    empty_state = ""
    if not display_items:
        display_state = "CAPITAL_PRESERVATION"
        empty_state = "Capital preservation active: no risk-approved opportunities are available."

    top = display_items[:3]
    avg_execution_quality = (sum(_number(row.get("execution_quality", 0.0)) for row in items) / len(items)) if items else 0.0
    market_health = _market_health(dashboard_payload)

    return {
        "items": display_items,
        "count": len(display_items),
        "raw_count": len(raw_opportunities),
        "display_state": display_state,
        "empty_state": empty_state,
        "market_health": market_health,
        "excluded_states": ["RED", "NOT_APPROVED"],
        "source": "DashboardState",
        "scoring_overview": {
            "top_ranked_symbols": [str(row.get("symbol", "UNKNOWN")) for row in top],
            "top_composite_scores": [_number(row.get("composite_score", 0.0)) for row in top],
            "best_adjusted_edge": max((_number(row.get("adjusted_edge", 0.0)) for row in items), default=0.0),
            "average_execution_quality": avg_execution_quality,
            "highest_survivability_symbols": [
                str(row.get("symbol", "UNKNOWN"))
                for row in sorted(items, key=lambda row: _number(row.get("survivability_score", 0.0)), reverse=True)[:3]
            ],
        },
    }


def _opportunity_item(value: Any) -> dict[str, Any]:
    item = _mapping(value)
    scoring_summary = _mapping(item.get("scoring_summary"))
    status = str(item.get("status", item.get("approval_state", "MONITOR_ONLY")))
    explanation = str(
        item.get(
            "opportunity_explanation",
            item.get("explanation", item.get("reason", item.get("note", ""))),
        )
    )
    return {
        "symbol": str(item.get("symbol", "UNKNOWN")),
        "asset_class": str(item.get("asset_class", "UNKNOWN")),
        "side": str(item.get("side", item.get("direction", "WATCH"))),
        "signal": str(item.get("signal", item.get("signal_state", "WATCH"))),
        "score": _number(item.get("score", item.get("composite_score"))),
        "composite_score": _number(item.get("composite_score", scoring_summary.get("total_score", 0.0))),
        "adjusted_edge": _number(scoring_summary.get("adjusted_edge", 0.0)),
        "execution_quality": _number(scoring_summary.get("execution_quality", 0.0)),
        "survivability_score": _number(scoring_summary.get("survivability_score", 0.0)),
        "probability": _number(item.get("probability", item.get("prob", 0.0))),
        "status": status,
        "risk_state": str(item.get("risk_state", item.get("risk_status", status))),
        "approval_state": str(item.get("approval_state", status)),
        "market_health": str(item.get("market_health", "")),
        "opportunity_explanation": explanation,
        "reason": explanation,
    }


def _opportunity_bucket(item: Mapping[str, Any]) -> str:
    fields = {
        str(item.get("status", "")),
        str(item.get("risk_state", "")),
        str(item.get("approval_state", "")),
        str(item.get("signal", "")),
    }
    normalized = {field.strip().upper() for field in fields if field}
    if normalized & {"RED", "NOT_APPROVED", "REJECTED", "BLOCKED", "DENIED"}:
        return "RED"
    if normalized & {"GREEN", "APPROVED", "APPROVE", "UNIFIED_GATE_APPROVED", "TRADE_APPROVED"}:
        return "GREEN"
    if normalized & {"AMBER", "WATCH", "NEAR_APPROVED", "MONITOR_ONLY", "CONFIRMED"}:
        return "AMBER"
    return "AMBER"


def _market_health(dashboard_payload: Mapping[str, Any]) -> str:
    market_payload = _mapping(dashboard_payload.get("market_summary"))
    risk_payload = _mapping(dashboard_payload.get("risk_summary"))
    states = {
        str(market_payload.get("liquidity_state", "")).upper(),
        str(market_payload.get("volatility_state", "")).upper(),
        str(market_payload.get("spread_state", "")).upper(),
        str(risk_payload.get("risk_state", "")).upper(),
    }
    if states & {"CRITICAL", "RED", "STRESSED", "WIDE", "BREACHED"}:
        return "RED"
    if states & {"AMBER", "WATCH", "ELEVATED", "HIGH", "DEFENSIVE"}:
        return "AMBER"
    if states & {"HEALTHY", "NORMAL", "TIGHT", "GREEN"}:
        return "GREEN"
    return DATA_UNAVAILABLE


def trade_summary(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    account = _mapping(dashboard_payload.get("account_summary"))
    pnl = _mapping(dashboard_payload.get("pnl_summary"))
    positions_payload = positions(dashboard_payload)
    execution_payload = execution(dashboard_payload)
    broker_payload = broker(dashboard_payload)
    session = _mapping(dashboard_payload.get("session"))

    generated_at = str(
        dashboard_payload.get("generated_at")
        or dashboard_payload.get("timestamp")
        or datetime.now(timezone.utc).isoformat()
    )
    mode = str(
        dashboard_payload.get("resolved_mode")
        or session.get("resolved_mode")
        or dashboard_payload.get("live_or_paper")
        or DATA_UNAVAILABLE
    )
    broker_name = _first_available(
        account.get("broker"),
        broker_payload.get("selected_broker"),
        dashboard_payload.get("broker_mode"),
    )
    if str(broker_name).strip().upper() in {"NONE", "UNKNOWN", "N/A", "NA"}:
        broker_name = DATA_UNAVAILABLE
    unrealized_pnl = _first_available(pnl.get("unrealized_pnl"))
    position_unrealized = sum(
        _number(_mapping(row).get("unrealized_pnl"))
        for row in _list(positions_payload.get("items"))
    )
    if _number(unrealized_pnl) == 0.0 and position_unrealized:
        unrealized_pnl = round(position_unrealized, 8)

    return {
        "date_time": generated_at,
        "mode": mode,
        "broker": broker_name,
        "engine_mode": _first_available(session.get("engine_mode"), dashboard_payload.get("engine_mode")),
        "account_balance": _first_available(account.get("account_balance"), account.get("cash_balance")),
        "equity": _first_available(account.get("equity"), account.get("total_equity"), pnl.get("account_equity")),
        "open_positions": positions_payload.get("total", DATA_UNAVAILABLE),
        "realized_pnl": _first_available(pnl.get("realized_pnl")),
        "unrealized_pnl": unrealized_pnl,
        "last_cycle": _first_available(session.get("cycle_number"), dashboard_payload.get("cycle_number")),
        "last_update": generated_at,
        "execution_status": _first_available(
            execution_payload.get("execution_state"),
            execution_payload.get("execution_status"),
        ),
        "data_status": "OK" if account else DATA_UNAVAILABLE,
        "advisory_only": True,
        "execution_allowed": False,
    }


def session_command_centre(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = trade_summary(dashboard_payload)
    opportunity = opportunities(dashboard_payload)
    risk_payload = risk(dashboard_payload)
    execution_payload = execution(dashboard_payload)
    portfolio = portfolio_summary(dashboard_payload)
    analytics_payload = analytics(dashboard_payload)
    broker_payload = broker(dashboard_payload)
    session = _mapping(dashboard_payload.get("session"))

    trade_quality = _bounded_score(
        (_number(analytics_payload.get("signal_quality")) * 60.0)
        + (_number(execution_payload.get("accepted_trade_count")) * 5.0)
        - (_number(execution_payload.get("rejected_trade_count")) * 7.5)
    )
    capital_efficiency = _bounded_score(_number(portfolio.get("capital_efficiency")) * 100.0)
    engine_health = _engine_health_score(risk_payload, execution_payload, broker_payload)
    market_health = str(opportunity.get("market_health", DATA_UNAVAILABLE))
    narrative = _ai_market_narrative(market_health, opportunity, risk_payload)

    navigation_links = [
        {"label": "Dashboard", "href": "/dashboard"},
        {"label": "Trade Summary", "href": "/trade-summary"},
        {"label": "Opportunities", "href": "/market-opportunities"},
        {"label": "Risk", "href": "/risk-governance"},
        {"label": "Broker", "href": "/broker"},
    ]
    intelligence_cards = [
        {"title": "Trade Quality Score", "value": trade_quality, "status": _score_status(trade_quality)},
        {"title": "Capital Efficiency Score", "value": capital_efficiency, "status": _score_status(capital_efficiency)},
        {"title": "Engine Health Score", "value": engine_health, "status": _score_status(engine_health)},
        {"title": "AI Market Narrative", "value": narrative, "status": market_health},
    ]

    return {
        "session_status": {
            "session_id": _first_available(dashboard_payload.get("session_id"), session.get("session_id")),
            "mode": summary["mode"],
            "engine_mode": summary["engine_mode"],
            "role": _first_available(session.get("role"), dashboard_payload.get("role")),
            "last_update": summary["last_update"],
        },
        "account_summary": {
            "account_balance": summary["account_balance"],
            "equity": summary["equity"],
            "realized_pnl": summary["realized_pnl"],
            "unrealized_pnl": summary["unrealized_pnl"],
        },
        "trading_activity": {
            "open_positions": summary["open_positions"],
            "execution_status": summary["execution_status"],
            "recent_trade_count": execution_payload.get("recent_trade_count", 0),
        },
        "risk_dashboard": {
            "risk_state": risk_payload.get("risk_state", DATA_UNAVAILABLE),
            "gate_status": risk_payload.get("gate_status", DATA_UNAVAILABLE),
            "exposure_utilization_pct": risk_payload.get("exposure_utilization_pct", 0.0),
        },
        "opportunity_centre": {
            "display_state": opportunity.get("display_state", DATA_UNAVAILABLE),
            "market_health": market_health,
            "count": opportunity.get("count", 0),
            "top_symbols": opportunity.get("scoring_overview", {}).get("top_ranked_symbols", []),
        },
        "runtime_health": {
            "broker_connected": broker_payload.get("connected", False),
            "broker_readiness": broker_payload.get("readiness_status", DATA_UNAVAILABLE),
            "execution_state": summary["execution_status"],
        },
        "intelligence_summary": {
            "trade_quality_score": trade_quality,
            "capital_efficiency_score": capital_efficiency,
            "engine_health_score": engine_health,
            "ai_market_narrative": narrative,
        },
        "daily_executive_summary": (
            f"{summary['mode']} session with {summary['open_positions']} open positions; "
            f"risk gate {risk_payload.get('gate_status', DATA_UNAVAILABLE)}; "
            f"opportunity posture {opportunity.get('display_state', DATA_UNAVAILABLE)}."
        ),
        "navigation_links": navigation_links,
        "intelligence_cards": intelligence_cards,
        "trade_quality_score": trade_quality,
        "capital_efficiency_score": capital_efficiency,
        "engine_health_score": engine_health,
        "ai_market_narrative": narrative,
        "advisory_only": True,
        "execution_allowed": False,
    }


def live_micro_pilot(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    explicit_payload = _mapping(dashboard_payload.get("live_micro_pilot"))
    if explicit_payload:
        payload = dict(explicit_payload)
    else:
        payload = {
            "section_title": "Live Micro-Pilot Status",
            "pilot_enabled": False,
            "pilot_armed": False,
            "pilot_state": "DISARMED",
            "currency": "CAD",
            "max_live_test_capital": "20.00",
            "max_position_size": "20.00",
            "remaining_live_test_capacity": "0.00",
            "config_valid": False,
            "config_error": "live_micro_pilot_artifact_not_provided",
            "pilot_guard_enforced": True,
            "broker_submission_guard": "REJECT_BEFORE_BROKER",
            "auto_flattening_enabled": False,
            "operator_controls": "SUPER_USER_ONLY",
        }
    payload["execution_allowed"] = False
    payload["advisory_only"] = True
    return payload


def live_readiness_certification(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    explicit_payload = _mapping(dashboard_payload.get("live_readiness_certification"))
    if explicit_payload:
        report = dict(explicit_payload)
    else:
        report = {
            "overall_certification_decision": "NO GO",
            "certification_status": "NO GO",
            "go_no_go": "NO GO",
            "readiness_score": 0.0,
            "known_warnings": [],
            "known_blockers": ["live_readiness_certification_not_provided"],
            "software_version": DATA_UNAVAILABLE,
            "commit": DATA_UNAVAILABLE,
            "git_tag": DATA_UNAVAILABLE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return {
        "section_title": "Live Readiness Certification",
        "live_readiness_score": _number(report.get("readiness_score")),
        "certification_status": str(report.get("certification_status", report.get("overall_certification_decision", "NO GO"))),
        "go_no_go": str(report.get("go_no_go", report.get("overall_certification_decision", "NO GO"))),
        "warnings": _string_list(report.get("known_warnings")),
        "blockers": _string_list(report.get("known_blockers")),
        "software_version": str(report.get("software_version", DATA_UNAVAILABLE)),
        "commit": str(report.get("commit", DATA_UNAVAILABLE)),
        "engineering_tag": str(report.get("git_tag", DATA_UNAVAILABLE)),
        "last_certification_time": str(report.get("timestamp", DATA_UNAVAILABLE)),
        "report": report,
        "execution_allowed": False,
        "advisory_only": True,
    }


def broker(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    broker_payload = _mapping(dashboard_payload.get("broker_summary"))
    credential_diagnostics = _mapping(broker_payload.get("credential_diagnostics"))
    limit_reconciliation = _mapping(broker_payload.get("limit_reconciliation"))
    broker_readiness = _mapping(broker_payload.get("broker_readiness"))
    return {
        "selected_broker": str(broker_payload.get("selected_broker", "NONE")),
        "broker_type": str(broker_payload.get("broker_type", broker_readiness.get("broker_type", "UNKNOWN"))),
        "broker_mode": str(broker_payload.get("broker_mode", "paper")),
        "connected": _boolean(broker_payload.get("connected")),
        "broker_connected": _boolean(broker_payload.get("broker_connected", broker_payload.get("connected"))),
        "broker_authenticated": _boolean(broker_payload.get("broker_authenticated")),
        "broker_health": str(broker_payload.get("broker_health", broker_payload.get("api_health", "UNKNOWN"))),
        "broker_infrastructure_health": str(
            broker_payload.get("broker_infrastructure_health", broker_payload.get("broker_health", broker_payload.get("api_health", "UNKNOWN")))
        ),
        "broker_ready": _boolean(broker_payload.get("broker_ready", broker_readiness.get("broker_ready"))),
        "broker_readiness": broker_readiness,
        "credentials_present": _boolean(broker_payload.get("credentials_present", broker_readiness.get("credentials_present"))),
        "authenticated": _boolean(broker_payload.get("authenticated", broker_payload.get("broker_authenticated", broker_readiness.get("authenticated")))),
        "account_loaded": _boolean(broker_payload.get("account_loaded", broker_readiness.get("account_loaded"))),
        "market_data_ready": _boolean(broker_payload.get("market_data_ready", broker_readiness.get("market_data_ready"))),
        "execution_supported": _boolean(broker_payload.get("execution_supported", broker_readiness.get("execution_supported"))),
        "infrastructure_health": str(broker_payload.get("infrastructure_health", broker_readiness.get("infrastructure_health", "UNKNOWN"))),
        "credentials_health": str(broker_payload.get("credentials_health", broker_readiness.get("credentials_health", "UNKNOWN"))),
        "authentication_health": str(broker_payload.get("authentication_health", broker_readiness.get("authentication_health", "UNKNOWN"))),
        "connection_health": str(broker_payload.get("connection_health", broker_readiness.get("connection_health", "UNKNOWN"))),
        "market_data_health": str(broker_payload.get("market_data_health", broker_readiness.get("market_data_health", "UNKNOWN"))),
        "account_data_health": str(broker_payload.get("account_data_health", broker_readiness.get("account_data_health", "UNKNOWN"))),
        "readiness_score": _number(broker_payload.get("readiness_score", broker_readiness.get("readiness_score"))),
        "broker_execution_armed": _boolean(broker_payload.get("broker_execution_armed")),
        "operator_requested_live": _boolean(broker_payload.get("operator_requested_live")),
        "execution_authority": _boolean(broker_payload.get("execution_authority")),
        "authority_reason": str(broker_payload.get("authority_reason", "Operator Intent Missing")),
        "live_authority_state": str(broker_payload.get("live_authority_state", "BLOCKED")),
        "live_execution_authority": _mapping(broker_payload.get("live_execution_authority")),
        "broker_execution_enabled": _boolean(broker_payload.get("broker_execution_enabled")),
        "broker_execution_status": str(broker_payload.get("broker_execution_status", "DISABLED")),
        "broker_connection_mode": str(broker_payload.get("broker_connection_mode", "PAPER_ONLY")),
        "live_trading_enabled": _boolean(
            broker_payload.get("live_trading_enabled")
        ),
        "last_heartbeat": str(broker_payload.get("last_heartbeat", "")),
        "api_health": str(broker_payload.get("api_health", "UNKNOWN")),
        "reconnect_state": str(broker_payload.get("reconnect_state", "NONE")),
        "supported_assets": _string_list(broker_payload.get("supported_assets")),
        "account_readiness": str(
            broker_payload.get("account_readiness", "UNKNOWN")
        ),
        "missing_credentials": _boolean(
            broker_payload.get("missing_credentials")
        ),
        "latency_ms": _number(broker_payload.get("latency_ms")),
        "readiness_status": str(
            broker_payload.get("readiness_status", "BROKER_BLOCKED")
        ),
        "readiness_reasons": _string_list(
            broker_payload.get("readiness_reasons")
        ),
        "credential_diagnostics": credential_diagnostics,
        "coinbase_key_present": _boolean(
            broker_payload.get("coinbase_key_present", credential_diagnostics.get("coinbase_key_present"))
        ),
        "coinbase_private_key_present": _boolean(
            broker_payload.get(
                "coinbase_private_key_present",
                credential_diagnostics.get("coinbase_private_key_present")
                or credential_diagnostics.get("coinbase_key_file_present"),
            )
        ),
        "missing_credential_names": _string_list(
            broker_payload.get("missing_credential_names", credential_diagnostics.get("missing_credentials"))
        ),
        "credential_status": str(
            broker_payload.get("credential_status", credential_diagnostics.get("credential_status", DATA_UNAVAILABLE))
        ),
        "credentials": str(
            broker_payload.get("credentials", broker_payload.get("credential_status", credential_diagnostics.get("credential_status", DATA_UNAVAILABLE)))
        ),
        "auth_status": str(broker_payload.get("auth_status", "NOT_TESTED")),
        "authentication_status": str(broker_payload.get("authentication_status", broker_payload.get("auth_status", "NOT_TESTED"))),
        "connection_status": str(broker_payload.get("connection_status", "NOT_TESTED")),
        "connection_error": str(broker_payload.get("connection_error", "")),
        "last_successful_sync": str(broker_payload.get("last_successful_sync", DATA_UNAVAILABLE)),
        "last_broker_sync": str(broker_payload.get("last_broker_sync", broker_payload.get("last_successful_sync", DATA_UNAVAILABLE))),
        "product_price_status": str(broker_payload.get("product_price_status", "NOT_TESTED")),
        "balance_position_status": str(broker_payload.get("balance_position_status", "NOT_TESTED")),
        "account_equity": broker_payload.get("account_equity", DATA_UNAVAILABLE),
        "cash": broker_payload.get("cash", DATA_UNAVAILABLE),
        "buying_power": broker_payload.get("buying_power", DATA_UNAVAILABLE),
        "available_balance": broker_payload.get("available_balance", DATA_UNAVAILABLE),
        "products_loaded": _integer(broker_payload.get("products_loaded", 0)),
        "market_data_status": str(broker_payload.get("market_data_status", broker_payload.get("product_price_status", "NOT_TESTED"))),
        "readiness_state": str(broker_payload.get("readiness_state", "UNCONFIGURED")),
        "go_no_go": str(broker_payload.get("go_no_go", "NO GO")),
        "readiness_checklist": _list(broker_payload.get("readiness_checklist")),
        "startup_diagnostics": _mapping(broker_payload.get("startup_diagnostics")),
        "order_submission_status": str(broker_payload.get("order_submission_status", "DISABLED")),
        "orders_sent_count": _integer(broker_payload.get("orders_sent_count", 0)),
        "orders_blocked_count": _integer(broker_payload.get("orders_blocked_count", 0)),
        "auth_reason": str(broker_payload.get("auth_reason", DATA_UNAVAILABLE)),
        "execution_scope": str(broker_payload.get("execution_scope", broker_payload.get("broker_connection_mode", DATA_UNAVAILABLE))),
        "can_live_execute": _boolean(broker_payload.get("can_live_execute")),
        "live_order_permission": _boolean(broker_payload.get("live_order_permission")),
        "live_micro_pilot_state": str(broker_payload.get("live_micro_pilot_state", "DISARMED")),
        "broker_guard": str(broker_payload.get("broker_guard", "REJECT_BEFORE_BROKER")),
        "drawdown_status": str(broker_payload.get("drawdown_status", DATA_UNAVAILABLE)),
        "drawdown_reason": str(broker_payload.get("drawdown_reason", DATA_UNAVAILABLE)),
        "limit_reconciliation": limit_reconciliation,
        "canonical_live_capital_authority": str(
            broker_payload.get(
                "canonical_live_capital_authority",
                limit_reconciliation.get("canonical_authority", "PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR"),
            )
        ),
        "canonical_live_pilot_limit_cad": str(
            broker_payload.get("canonical_live_pilot_limit_cad", limit_reconciliation.get("canonical_live_pilot_limit_cad", "20.00"))
        ),
        "legacy_secondary_limit_label": str(
            broker_payload.get("legacy_secondary_limit_label", limit_reconciliation.get("legacy_secondary_limit_label", "LEGACY_SECONDARY_LIMIT"))
        ),
        "legacy_coinbase_max_live_order_usd": broker_payload.get(
            "legacy_coinbase_max_live_order_usd",
            limit_reconciliation.get("legacy_coinbase_max_live_order_usd", DATA_UNAVAILABLE),
        ),
    }


def broker_parity(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    broker_payload = _mapping(dashboard_payload.get("broker_summary"))
    explicit_payload = _mapping(dashboard_payload.get("broker_parity"))
    report = dict(explicit_payload) if explicit_payload else broker_parity_payload(broker_payload)
    report["execution_allowed"] = False
    report["advisory_only"] = True
    return report


def coinbase_live_validation(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    broker_payload = _mapping(dashboard_payload.get("broker_summary"))
    explicit_payload = _mapping(dashboard_payload.get("coinbase_live_validation"))
    validation_payload = _mapping(broker_payload.get("coinbase_live_validation"))
    source = explicit_payload or validation_payload
    broker_validation = _mapping(source.get("broker_validation"))
    broker_health = _mapping(source.get("broker_health"))
    market_snapshot = _mapping(source.get("broker_market_snapshot"))
    return {
        "validation_status": str(broker_validation.get("validation_status", source.get("validation_status", "DATA UNAVAILABLE"))),
        "api_reachable": _boolean(broker_validation.get("api_reachable", source.get("api_reachable"))),
        "authentication": _boolean(broker_validation.get("authentication", source.get("authenticated"))),
        "account_loaded": _boolean(broker_validation.get("account_loaded", source.get("account_loaded"))),
        "portfolio_loaded": _boolean(broker_validation.get("portfolio_loaded", source.get("portfolio_loaded"))),
        "balances_loaded": _boolean(broker_validation.get("balances_loaded", source.get("balances_loaded"))),
        "products_loaded": _integer(broker_validation.get("products_loaded", source.get("products_loaded", 0))),
        "market_data_loaded": _boolean(broker_validation.get("market_data_loaded", source.get("market_data_loaded"))),
        "last_successful_sync": str(
            broker_validation.get("last_successful_sync", broker_health.get("last_successful_sync", source.get("last_successful_sync", DATA_UNAVAILABLE)))
        ),
        "validation_timestamp": str(
            broker_validation.get("validation_timestamp", market_snapshot.get("validation_timestamp", source.get("validation_timestamp", DATA_UNAVAILABLE)))
        ),
        "read_checks": _mapping(broker_validation.get("read_checks", source.get("read_checks"))),
        "failure_reasons": _list(broker_validation.get("failure_reasons", source.get("failure_reasons"))),
        "broker_validation": broker_validation,
        "broker_health": broker_health,
        "broker_market_snapshot": market_snapshot,
        "broker_execution_status": "DISABLED",
        "execution_authority": False,
        "can_live_execute": False,
        "live_micro_pilot_state": "DISARMED",
        "advisory_only": True,
        "execution_allowed": False,
    }


def oanda_live_validation(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    broker_payload = _mapping(dashboard_payload.get("broker_summary"))
    explicit_payload = _mapping(dashboard_payload.get("oanda_live_validation"))
    validation_payload = _mapping(broker_payload.get("oanda_live_validation"))
    source = explicit_payload or validation_payload
    broker_validation = _mapping(source.get("broker_validation"))
    broker_health = _mapping(source.get("broker_health"))
    market_snapshot = _mapping(source.get("broker_market_snapshot"))
    return {
        "validation_status": str(broker_validation.get("validation_status", source.get("validation_status", "DATA UNAVAILABLE"))),
        "api_reachable": _boolean(broker_validation.get("api_reachable", source.get("api_reachable"))),
        "authentication": _boolean(broker_validation.get("authentication", source.get("authenticated"))),
        "account_loaded": _boolean(broker_validation.get("account_loaded", source.get("account_loaded"))),
        "portfolio_loaded": _boolean(broker_validation.get("portfolio_loaded", source.get("portfolio_loaded"))),
        "balances_loaded": _boolean(broker_validation.get("balances_loaded", source.get("balances_loaded"))),
        "products_loaded": _integer(broker_validation.get("products_loaded", source.get("products_loaded", 0))),
        "market_data_loaded": _boolean(broker_validation.get("market_data_loaded", source.get("market_data_loaded"))),
        "last_successful_sync": str(
            broker_validation.get("last_successful_sync", broker_health.get("last_successful_sync", source.get("last_successful_sync", DATA_UNAVAILABLE)))
        ),
        "validation_timestamp": str(
            broker_validation.get("validation_timestamp", market_snapshot.get("validation_timestamp", source.get("validation_timestamp", DATA_UNAVAILABLE)))
        ),
        "read_checks": _mapping(broker_validation.get("read_checks", source.get("read_checks"))),
        "failure_reasons": _list(broker_validation.get("failure_reasons", source.get("failure_reasons"))),
        "broker_validation": broker_validation,
        "broker_health": broker_health,
        "broker_market_snapshot": market_snapshot,
        "broker_execution_status": "DISABLED",
        "execution_authority": False,
        "can_live_execute": False,
        "live_micro_pilot_state": "DISARMED",
        "advisory_only": True,
        "execution_allowed": False,
    }


def broker_reconciliation(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    return build_broker_reconciliation_payload(dashboard_payload)



def analytics(dashboard_payload: Mapping[str, Any]) -> dict[str, Any]:
    analytics_summary = _mapping(dashboard_payload.get("analytics_summary"))
    headline = _mapping(analytics_summary.get("headline"))
    return {
        "expectancy": _number(headline.get("expectancy")),
        "profit_factor": _number(headline.get("profit_factor")),
        "estimated_execution_cost": _number(headline.get("estimated_execution_cost")),
        "signal_quality": _number(headline.get("signal_quality")),
        "current_edge_estimate": _number(headline.get("current_edge_estimate")),
        "drawdown_state": _number(headline.get("drawdown_state")),
    }

def build_section_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
    section: str,
) -> dict[str, Any]:
    payload = build_frontend_payload(dashboard_state)
    sections = _mapping(payload.get("sections"))
    return {
        "payload_version": payload["payload_version"],
        "payload_schema": payload["payload_schema"],
        "generated_at": payload["generated_at"],
        "section": section,
        "data": sections.get(section, {}),
    }


def build_websocket_delta(
    previous_payload: Mapping[str, Any] | None,
    current_payload: Mapping[str, Any],
    *,
    sequence: int = 0,
    sections: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    previous_sections = _mapping((previous_payload or {}).get("sections"))
    current_sections = _mapping(current_payload.get("sections"))
    sections_to_scan = sections or FRONTEND_SECTIONS
    changed_sections = [
        section
        for section in sections_to_scan
        if previous_sections.get(section) != current_sections.get(section)
    ]
    data = {
        section: current_sections.get(section, {})
        for section in changed_sections
    }

    return WebsocketDelta(
        message_type="dashboard_delta",
        payload_version=FRONTEND_CONTRACT_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        changed_sections=changed_sections,
        data=data,
        sequence=sequence,
    ).as_dict()


def _dashboard_payload(
    dashboard_state: DashboardState | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(dashboard_state, DashboardState):
        return dashboard_state.to_dict()
    if isinstance(dashboard_state, Mapping):
        return _json_safe(dict(dashboard_state))
    return DashboardState().to_dict()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalized_positions_for_correlation(position_state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _list(position_state.get("positions")):
        item = _mapping(raw)
        symbol = str(item.get("symbol") or "").strip()
        if not symbol:
            continue

        exposure = _number(item.get("exposure", _number(item.get("qty")) * _number(item.get("current_price"))))
        rows.append(
            {
                "symbol": symbol,
                "asset_class": str(item.get("asset_class", "UNKNOWN")),
                "side": str(item.get("side", "UNKNOWN")),
                "exposure_value": exposure,
            }
        )
    return rows


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _first_available(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return DATA_UNAVAILABLE


def _bounded_score(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value))), 2)


def _score_status(score: float) -> str:
    if score >= 75.0:
        return "GREEN"
    if score >= 45.0:
        return "AMBER"
    return "RED"


def _engine_health_score(
    risk_payload: Mapping[str, Any],
    execution_payload: Mapping[str, Any],
    broker_payload: Mapping[str, Any],
) -> float:
    score = 82.0
    risk_state = str(risk_payload.get("risk_state", "")).upper()
    gate_status = str(risk_payload.get("gate_status", "")).upper()
    execution_state = str(execution_payload.get("execution_state", "")).upper()
    if risk_state in {"RED", "CRITICAL", "BREACHED"}:
        score -= 35.0
    if gate_status in {"CLOSED", "BLOCKED", "REJECTING"}:
        score -= 25.0
    if execution_state in {"ERROR", "FAILED", "BLOCKED"}:
        score -= 20.0
    if broker_payload.get("connected") is True:
        score += 8.0
    return _bounded_score(score)


def _ai_market_narrative(
    market_health: str,
    opportunity_payload: Mapping[str, Any],
    risk_payload: Mapping[str, Any],
) -> str:
    display_state = str(opportunity_payload.get("display_state", DATA_UNAVAILABLE))
    gate_status = str(risk_payload.get("gate_status", DATA_UNAVAILABLE))
    if display_state == "CAPITAL_PRESERVATION":
        return "Capital preservation posture: no risk-approved opportunities are being surfaced."
    return (
        f"Market health is {market_health}; opportunity posture is {display_state}; "
        f"risk gate is {gate_status}. Display-only intelligence, no execution authority implied."
    )


def _integer(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _boolean(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {
            str(key): (
                "REDACTED"
                if _is_sensitive_key(str(key))
                else _json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    safe_metadata_keys = {
        "secrets_redacted",
        "credentials_redacted",
        "missing_credentials",
        "credential_status",
    }

    if normalized in safe_metadata_keys:
        return False

    sensitive_fragments = (
        "api_key",
        "access_key",
        "private_key",
        "secret",
        "token",
        "password",
        "passphrase",
        "credential",
        "pem",
        "authorization",
        "bearer",
        "oauth",
        "session_cookie",
    )
    return normalized == "key" or any(
        fragment in normalized for fragment in sensitive_fragments
    )


__all__ = [
    "FRONTEND_CONTRACT_SCHEMA",
    "FRONTEND_CONTRACT_VERSION",
    "FRONTEND_SECTIONS",
    "FrontendEnvelope",
    "WebsocketDelta",
    "account_summary",
    "broker",
    "broker_parity",
    "coinbase_live_validation",
    "oanda_live_validation",
    "broker_reconciliation",
    "build_frontend_payload",
    "build_section_payload",
    "build_websocket_delta",
    "trade",
    "execution",
    "governance",
    "market",
    "opportunities",
    "session_command_centre",
    "trade_summary",
    "portfolio_summary",
    "portfolio_greeks",
    "pnl_summary",
    "positions",
    "risk",
]
