from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# =========================================================
# PNL SUMMARY
# =========================================================

@dataclass
class PnLSummary:
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0

    total_fees: float = 0.0
    total_slippage: float = 0.0

    gross_profit: float = 0.0
    gross_loss: float = 0.0

    net_profit: float = 0.0

    winners: int = 0
    losers: int = 0

    win_rate: float = 0.0


# =========================================================
# EXPOSURE SUMMARY
# =========================================================

@dataclass
class ExposureSummary:
    total_exposure: float = 0.0

    crypto_exposure: float = 0.0
    fx_exposure: float = 0.0
    futures_exposure: float = 0.0
    options_exposure: float = 0.0

    leveraged_exposure: float = 0.0


# =========================================================
# GOVERNANCE SUMMARY
# =========================================================

@dataclass
class GovernanceSummary:
    governance_enabled: bool = True

    defensive_mode_active: bool = False

    session_locked: bool = False

    blocked_trades: int = 0

    governance_events: List[str] = field(
        default_factory=list
    )


# =========================================================
# MARKET SUMMARY
# =========================================================

@dataclass
class MarketSummary:
    trend_state: str = "UNKNOWN"

    volatility_state: str = "UNKNOWN"

    liquidity_state: str = "UNKNOWN"

    regime_state: str = "UNKNOWN"

    momentum_state: str = "UNKNOWN"

    pressure_state: str = "UNKNOWN"

    acceleration_state: str = "UNKNOWN"

    vwap_state: str = "UNKNOWN"

    signal_confluence_state: str = "UNKNOWN"


# =========================================================
# BROKER SUMMARY
# =========================================================

@dataclass
class BrokerSummary:
    selected_broker: str = "NONE"

    broker_mode: str = "paper"

    connected: bool = False

    open_orders: int = 0

    execution_failures: int = 0

    last_broker_event: str = ""


# =========================================================
# TRADE WAREHOUSE SUMMARY
# =========================================================

@dataclass
class TradeWarehouseSummary:
    total_trades: int = 0

    crypto_trades: int = 0
    fx_trades: int = 0
    futures_trades: int = 0
    options_trades: int = 0

    archived_reports: int = 0


# =========================================================
# CANONICAL DASHBOARD SUMMARY PAYLOAD
# =========================================================

@dataclass
class DashboardSummaryPayload:

    pnl: PnLSummary = field(
        default_factory=PnLSummary
    )

    exposure: ExposureSummary = field(
        default_factory=ExposureSummary
    )

    governance: GovernanceSummary = field(
        default_factory=GovernanceSummary
    )

    market: MarketSummary = field(
        default_factory=MarketSummary
    )

    broker: BrokerSummary = field(
        default_factory=BrokerSummary
    )

    warehouse: TradeWarehouseSummary = field(
        default_factory=TradeWarehouseSummary
    )

    metadata: Dict[str, str] = field(
        default_factory=dict
    )