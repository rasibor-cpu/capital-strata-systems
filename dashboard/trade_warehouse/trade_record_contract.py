from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# =========================================================
# EXECUTION COSTS
# =========================================================

@dataclass
class ExecutionCostRecord:
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    commission_cost: float = 0.0
    financing_cost: float = 0.0

    total_cost: float = 0.0


# =========================================================
# MARKET SNAPSHOT
# =========================================================

@dataclass
class MarketSnapshot:
    trend_state: str = "UNKNOWN"
    volatility_state: str = "UNKNOWN"
    liquidity_state: str = "UNKNOWN"
    regime_state: str = "UNKNOWN"

    vwap_distance: float = 0.0
    vwap_elasticity: float = 0.0

    momentum_state: str = "UNKNOWN"
    pressure_state: str = "UNKNOWN"

    probability: float = 0.0
    signal_score: float = 0.0


# =========================================================
# GOVERNANCE SNAPSHOT
# =========================================================

@dataclass
class GovernanceSnapshot:
    approved: bool = False

    approval_reason: str = ""

    engine_mode: str = "SAFE"

    broker_mode: str = "paper"

    governance_event_id: str = ""


# =========================================================
# TRADE RECORD
# =========================================================

@dataclass
class TradeRecord:

    # -----------------------------------------------------
    # IDENTIFIERS
    # -----------------------------------------------------

    trade_id: str

    timestamp: str

    asset_class: str

    symbol: str

    # -----------------------------------------------------
    # EXECUTION
    # -----------------------------------------------------

    side: str

    quantity: float

    entry_price: float

    exit_price: float = 0.0

    # -----------------------------------------------------
    # ACCOUNTING
    # -----------------------------------------------------

    realized_pnl: float = 0.0

    unrealized_pnl: float = 0.0

    holding_time_seconds: float = 0.0

    # -----------------------------------------------------
    # EXECUTION COSTS
    # -----------------------------------------------------

    execution_costs: ExecutionCostRecord = field(
        default_factory=ExecutionCostRecord
    )

    # -----------------------------------------------------
    # MARKET SNAPSHOT
    # -----------------------------------------------------

    market_snapshot: MarketSnapshot = field(
        default_factory=MarketSnapshot
    )

    # -----------------------------------------------------
    # GOVERNANCE SNAPSHOT
    # -----------------------------------------------------

    governance_snapshot: GovernanceSnapshot = field(
        default_factory=GovernanceSnapshot
    )

    # -----------------------------------------------------
    # BROKER
    # -----------------------------------------------------

    broker: str = "NONE"

    broker_order_id: str = ""

    # -----------------------------------------------------
    # STRATEGY
    # -----------------------------------------------------

    strategy_source: str = ""

    exit_reason: str = ""

    # -----------------------------------------------------
    # TAGS
    # -----------------------------------------------------

    tags: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, str] = field(
        default_factory=dict
    )