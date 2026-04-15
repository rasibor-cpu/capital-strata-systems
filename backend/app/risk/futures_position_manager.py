"""
Futures Position Manager
Capital Strata Systems – Phase 18 (Profitability Upgrade)

Enhancements:
- Side-aware LONG / SHORT futures support
- Correct long/short PnL calculation
- Trailing profit capture
- Peak favorable excursion tracking
- Automatic update_positions() lifecycle engine
- Time-based exit enforcement
- Fully backward compatible
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

    DEFAULT_TRAIL_TRIGGER_PCT = 0.015
    DEFAULT_TRAIL_STOP_PCT = 0.0075
    DEFAULT_MAX_HOLD_CYCLES = 4

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
        side: str = "LONG",
    ) -> Dict:
        """
        Attempts to open a futures position via adapter.
        """

        side = str(side).upper().strip()
        if side not in {"LONG", "SHORT"}:
            side = "LONG"

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
            "side": side,
            "entry_price": float(entry_price),
            "stop_price": float(stop_price),
            "contracts": int(contracts),
            "risk": float(risk),
            "timestamp": time.time(),
            "status": "OPEN",

            # New profitability fields
            "peak_price_seen": float(entry_price),
            "trailing_active": False,
            "trail_trigger_pct": self.DEFAULT_TRAIL_TRIGGER_PCT,
            "trail_stop_pct": self.DEFAULT_TRAIL_STOP_PCT,
            "max_hold_cycles": self.DEFAULT_MAX_HOLD_CYCLES,
            "entry_cycle": int(state.get("current_cycle", 0)),
        }

        self.open_positions[position_id] = position

        return {
            "status": "OPENED",
            "position": position,
        }

    # -----------------------------------------------------

    def update_positions(
        self,
        *,
        price_map: Dict[str, float],
        current_cycle: int,
    ) -> List[Dict]:
        """
        Lifecycle updater:
        - activates trailing winners
        - applies trailing exits
        - enforces stop loss
        - enforces time exits
        """

        events: List[Dict] = []

        for position_id, pos in list(self.open_positions.items()):
            if pos["status"] != "OPEN":
                continue

            symbol = pos["symbol"]
            if symbol not in price_map:
                continue

            current_price = float(price_map[symbol])
            side = pos["side"]
            entry_price = float(pos["entry_price"])
            stop_price = float(pos["stop_price"])
            held_cycles = max(
                0,
                int(current_cycle) - int(pos.get("entry_cycle", current_cycle))
            )

            # Track peak favorable excursion
            if side == "LONG":
                pos["peak_price_seen"] = max(
                    float(pos["peak_price_seen"]),
                    current_price
                )
            else:
                pos["peak_price_seen"] = min(
                    float(pos["peak_price_seen"]),
                    current_price
                )

            # Unrealized PnL
            pos["current_price"] = current_price
            pos["held_cycles"] = held_cycles
            pos["unrealized_pnl"] = self._compute_pnl(
                side=side,
                entry_price=entry_price,
                exit_price=current_price,
                contracts=int(pos["contracts"]),
            )

            # Stop loss
            if side == "LONG" and current_price <= stop_price:
                events.append(
                    self.close_position(
                        position_id=position_id,
                        exit_price=current_price,
                        reason="SL",
                    )
                )
                continue

            if side == "SHORT" and current_price >= stop_price:
                events.append(
                    self.close_position(
                        position_id=position_id,
                        exit_price=current_price,
                        reason="SL",
                    )
                )
                continue

            # Activate trailing
            if not pos["trailing_active"]:
                if self._trail_trigger_hit(pos, current_price):
                    pos["trailing_active"] = True

            # Trailing exit
            if pos["trailing_active"]:
                if self._trail_exit_hit(pos, current_price):
                    events.append(
                        self.close_position(
                            position_id=position_id,
                            exit_price=current_price,
                            reason="TRAIL_TP",
                        )
                    )
                    continue

            # Time exit
            if held_cycles >= int(pos["max_hold_cycles"]):
                events.append(
                    self.close_position(
                        position_id=position_id,
                        exit_price=current_price,
                        reason="TIME",
                    )
                )

        return events

    # -----------------------------------------------------

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "MANUAL",
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
        side = position["side"]

        pnl = self._compute_pnl(
            side=side,
            entry_price=entry_price,
            exit_price=float(exit_price),
            contracts=contracts,
        )

        self.adapter.close_trade(float(position["risk"]))

        position["exit_price"] = float(exit_price)
        position["pnl"] = float(pnl)
        position["status"] = "CLOSED"
        position["reason"] = reason
        position["closed_timestamp"] = time.time()

        closed_copy = dict(position)
        self.closed_positions.append(closed_copy)

        return {
            "status": "CLOSED",
            "position": position,
        }

    # -----------------------------------------------------

    def _compute_pnl(
        self,
        *,
        side: str,
        entry_price: float,
        exit_price: float,
        contracts: int,
    ) -> float:
        if side == "SHORT":
            return (entry_price - exit_price) * contracts
        return (exit_price - entry_price) * contracts

    # -----------------------------------------------------

    def _trail_trigger_hit(self, pos: Dict, current_price: float) -> bool:
        entry = float(pos["entry_price"])
        trigger_pct = float(pos["trail_trigger_pct"])
        side = pos["side"]

        if side == "LONG":
            return current_price >= entry * (1.0 + trigger_pct)
        else:
            return current_price <= entry * (1.0 - trigger_pct)

    # -----------------------------------------------------

    def _trail_exit_hit(self, pos: Dict, current_price: float) -> bool:
        peak = float(pos["peak_price_seen"])
        trail_pct = float(pos["trail_stop_pct"])
        side = pos["side"]

        if side == "LONG":
            trail_level = peak * (1.0 - trail_pct)
            return current_price <= trail_level
        else:
            trail_level = peak * (1.0 + trail_pct)
            return current_price >= trail_level

    # -----------------------------------------------------

    def has_open_position_for_symbol(self, symbol: str) -> bool:
        for position in self.open_positions.values():
            if position.get("status") == "OPEN" and position.get("symbol") == symbol:
                return True
        return False

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
