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

from typing import Dict, List, Optional
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
        self.closed_positions: List[Dict] = []

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

        entry_price = float(position["entry_price"])
        contracts = int(position["contracts"])

        pnl = (float(exit_price) - entry_price) * contracts

        self.adapter.close_trade(float(position["risk"]))

        position["exit_price"] = float(exit_price)
        position["pnl"] = float(pnl)
        position["status"] = "CLOSED"
        position["closed_timestamp"] = time.time()

        closed_copy = dict(position)
        self.closed_positions.append(closed_copy)

        return {
            "status": "CLOSED",
            "position": position,
        }

    # -----------------------------------------------------

    def has_open_position_for_symbol(self, symbol: str) -> bool:
        for position in self.open_positions.values():
            if position.get("status") == "OPEN" and position.get("symbol") == symbol:
                return True
        return False

    # -----------------------------------------------------

    def get_open_position_for_symbol(self, symbol: str) -> Optional[Dict]:
        for position in self.open_positions.values():
            if position.get("status") == "OPEN" and position.get("symbol") == symbol:
                return position
        return None

    # -----------------------------------------------------

    def open_position_if_allowed(
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
        Opens only if no existing open position for the symbol.
        """

        if self.has_open_position_for_symbol(symbol):
            return {
                "status": "SKIPPED",
                "reason": f"Open position already exists for {symbol}",
                "symbol": symbol,
            }

        return self.open_position(
            symbol=symbol,
            entry_price=entry_price,
            stop_price=stop_price,
            contracts=contracts,
            current_equity=current_equity,
            state=state,
        )

    # -----------------------------------------------------

    def close_position_by_symbol(
        self,
        *,
        symbol: str,
        exit_price: float,
    ) -> Dict:
        """
        Closes first matching open position for a symbol.
        """

        position = self.get_open_position_for_symbol(symbol)
        if not position:
            return {
                "status": "ERROR",
                "reason": f"No open position found for {symbol}",
                "symbol": symbol,
            }

        return self.close_position(
            position_id=position["position_id"],
            exit_price=exit_price,
        )

    # -----------------------------------------------------

    def get_position_hold_cycles(
        self,
        *,
        position: Dict,
        current_cycle: int,
    ) -> int:
        """
        Computes hold cycles if cycle metadata is present.
        """

        try:
            entry_cycle = int(position.get("entry_cycle", current_cycle))
            return max(0, int(current_cycle) - entry_cycle)
        except Exception:
            return 0

    # -----------------------------------------------------

    def mark_position_cycle_metadata(
        self,
        *,
        position_id: str,
        entry_cycle: int,
        signal_score: float = 0.0,
    ) -> None:
        """
        Optional metadata enrichment for dashboard/orchestrator usage.
        """

        if position_id not in self.open_positions:
            return

        self.open_positions[position_id]["entry_cycle"] = int(entry_cycle)
        self.open_positions[position_id]["signal_score"] = float(signal_score)

    # -----------------------------------------------------

    def get_open_positions(self) -> List[Dict]:
        return [
            p for p in self.open_positions.values()
            if p["status"] == "OPEN"
        ]

    # -----------------------------------------------------

    def get_closed_positions(self) -> List[Dict]:
        return list(self.closed_positions)

    # -----------------------------------------------------

    def get_all_positions(self) -> List[Dict]:
        return list(self.open_positions.values())