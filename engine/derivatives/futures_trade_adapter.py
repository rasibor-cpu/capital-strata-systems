"""
FuturesTradeAdapter – Derivatives Execution Layer
Capital Strata Systems (CSS)

Purpose:
- Translate futures contracts into standardized notional risk
- Integrate with ExecutionGate
- Preserve RiskGovernor + Drawdown discipline
- Support CME-style multiplier contracts

Design:
- No broker calls
- Deterministic conversion
- Risk-normalized sizing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# ============================================================
# CONTRACT SPECIFICATION
# ============================================================

@dataclass(frozen=True)
class FuturesContractSpec:
    symbol: str
    contract_multiplier: float
    tick_size: float
    tick_value: float


# Example baseline specs (extend later)
CONTRACT_SPECS: Dict[str, FuturesContractSpec] = {
    "ES": FuturesContractSpec(symbol="ES", contract_multiplier=50.0, tick_size=0.25, tick_value=12.5),
    "NQ": FuturesContractSpec(symbol="NQ", contract_multiplier=20.0, tick_size=0.25, tick_value=5.0),
    "CL": FuturesContractSpec(symbol="CL", contract_multiplier=1000.0, tick_size=0.01, tick_value=10.0),
}


# ============================================================
# FUTURES TRADE OBJECT
# ============================================================

@dataclass
class FuturesTradeRequest:
    symbol: str
    contracts: int
    entry_price: float
    stop_price: float


# ============================================================
# ADAPTER
# ============================================================

class FuturesTradeAdapter:

    def __init__(self) -> None:
        pass

    def compute_notional(self, trade: FuturesTradeRequest) -> float:
        """
        Convert futures contract size into USD notional exposure.
        """

        spec = CONTRACT_SPECS.get(trade.symbol)
        if not spec:
            raise ValueError(f"Unknown futures contract: {trade.symbol}")

        return trade.contracts * spec.contract_multiplier * trade.entry_price

    def compute_risk_amount(self, trade: FuturesTradeRequest) -> float:
        """
        Calculate absolute dollar risk based on stop distance.
        """

        spec = CONTRACT_SPECS.get(trade.symbol)
        if not spec:
            raise ValueError(f"Unknown futures contract: {trade.symbol}")

        price_diff = abs(trade.entry_price - trade.stop_price)

        return trade.contracts * spec.contract_multiplier * price_diff

    def to_execution_payload(self, trade: FuturesTradeRequest) -> Dict[str, float]:
        """
        Convert to generic ExecutionGate payload.
        """

        notional = self.compute_notional(trade)

        stop_distance_pct = abs(trade.entry_price - trade.stop_price) / trade.entry_price

        return {
            "instrument": trade.symbol,
            "side": "BUY",
            "notional": notional,
            "stop_distance_pct": stop_distance_pct,
        }
