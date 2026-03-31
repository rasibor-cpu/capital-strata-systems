"""
Futures Position Manager
Capital Strata Systems – Phase 17 (Lifecycle Engine)

Purpose:
- Track individual futures positions
- Manage open/close lifecycle
- Integrate with FuturesSimAdapter (risk control)
- Prepare for future PnL + margin expansion

Design Principles:
- No regression to existing system
- Works alongside current adapter (not replacing it)
- Lightweight but extensible
"""

from __future__ import annotations

from typing import Dict, List
import uuid
import time

from backend.app.brokers.futures_sim_adapter import FuturesSimAdapter
from backend.app.risk.futures_contract_specs import calculate_futures_risk


class FuturesPositionManager:
    """
    Manages futures positions lifecycle.
    """

    def __init__(
        self,
        adapter: FuturesSimAdapter,
    ) -> None:
        self.adapter = adapter
        self.open_positions: Dict[str, Dict] = {}

    # -----------------------------------------------------

    def open_position(
        self,
        *,
        symbol: str,
        entry_price: float,
        stop_price: float,
        contracts: int,
        current_equity: float,
        state: Dict,
    ) -> Dict:
        """
        Attempts to open a futures position via adapter.
        """

        result = self.adapter.simulate_trade(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            contracts=contracts,
            current_equity=current_equity,
            state=state,
        )

        if result.get("status") != "APPROVED":
            return result

        # ---- Create position record ----
        position_id = str(uuid.uuid4())

        risk = calculate_futures_risk(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            contracts=contracts,
        )

        position = {
            "position_id": position_id,
            "symbol": symbol,
            "entry_price": float(entry_price),
            "stop_price": float(stop_price),
            "contracts": int(contracts),
            "risk": float(risk),
            "timestamp": time.time(),
            "status": "OPEN",
        }

        self.open_positions[position_id] = position

        return {
            "status": "OPENED",
            "position": position,
        }

    # -----------------------------------------------------

    def close_position(
        self,
        position_id: str,
        exit_price: float,
    ) -> Dict:
        """
        Closes a futures position.
        """

        if position_id not in self.open_positions:
            return {
                "status": "ERROR",
                "reason": "Position not found",
                "position_id": position_id,
            }

        position = self.open_positions[position_id]

        if position["status"] != "OPEN":
            return {
                "status": "ERROR",
                "reason": "Position already closed",
                "position_id": position_id,
            }

        # ---- Calculate PnL ----
        entry_price = position["entry_price"]
        contracts = position["contracts"]

        # NOTE: multiplier approximation handled via risk engine scaling
        pnl = (exit_price - entry_price) * contracts

        # ---- Reduce risk exposure ----
        self.adapter.close_trade(position["risk"])

        # ---- Update position ----
        position["exit_price"] = float(exit_price)
        position["pnl"] = float(pnl)
        position["status"] = "CLOSED"
        position["closed_timestamp"] = time.time()

        return {
            "status": "CLOSED",
            "position": position,
        }

    # -----------------------------------------------------

    def get_open_positions(self) -> List[Dict]:
        return [
            p for p in self.open_positions.values()
            if p["status"] == "OPEN"
        ]

    # -----------------------------------------------------

    def get_all_positions(self) -> List[Dict]:
        return list(self.open_positions.values())