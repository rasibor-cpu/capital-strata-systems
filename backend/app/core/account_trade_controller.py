from __future__ import annotations

from typing import Dict, List, Optional

from backend.app.core.account_engine import CapitalEngine, AccountPersistence
from backend.app.accounting.pnl_engine import (
    Position,
    InstrumentSpec,
    ExecutionCost,
    compute_portfolio_snapshot,
)
from datetime import datetime, timezone
import json
import os


TRADE_LOG_FILE = "audit_logs/trades.jsonl"


class TradeLogger:
    @staticmethod
    def log(event: dict):
        os.makedirs("audit_logs", exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        with open(TRADE_LOG_FILE, "a") as f:
            f.write(json.dumps(payload) + "\n")


class AccountTradeController:
    """
    CSS Control Layer (NON-REGRESSION COMPLIANT)

    Responsibilities:
    - Manage trade lifecycle (OPEN / CLOSE)
    - Interface with PnL engine (NO modification)
    - Sync with CapitalEngine (real broker balance)
    - Persist account state
    - Log trades (audit trail)
    """

    def __init__(self):
        self.capital_engine = CapitalEngine()
        self.capital_engine.initialize()

        self.state = self.capital_engine.state
        self.active_broker = self.capital_engine.get_active_broker_name()

        self.positions: List[Position] = []

        self._restore_positions()

    # =========================
    # 🔄 RESTORE STATE
    # =========================
    def _restore_positions(self):
        """
        Restore open positions from persisted state
        """
        for pos in self.state.open_positions:
            try:
                spec = InstrumentSpec(
                    symbol=pos["symbol"],
                    asset_class=pos["asset_class"],
                    multiplier=pos.get("multiplier", 1.0),
                )

                position = Position(
                    symbol=pos["symbol"],
                    side=pos["side"],
                    entry_price=pos["entry_price"],
                    current_price=pos["entry_price"],
                    quantity=pos["quantity"],
                    instrument_spec=spec,
                    entry_cost=ExecutionCost(**pos.get("entry_cost", {})),
                    estimated_exit_cost=ExecutionCost(**pos.get("exit_cost", {})),
                    realized_pnl=pos.get("realized_pnl", 0.0),
                    is_open=True,
                )

                self.positions.append(position)

            except Exception:
                continue

    # =========================
    # 📥 OPEN TRADE
    # =========================
    def open_trade(
        self,
        symbol: str,
        asset_class: str,
        side: str,
        entry_price: float,
        quantity: float,
    ):

        spec = InstrumentSpec(
            symbol=symbol,
            asset_class=asset_class.upper(),
            multiplier=1.0,
        )

        entry_cost = ExecutionCost(
            spread=entry_price * quantity * 0.0005,
            slippage=entry_price * quantity * 0.0005,
            fees=entry_price * quantity * 0.001,
        )

        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            instrument_spec=spec,
            entry_cost=entry_cost,
            estimated_exit_cost=ExecutionCost(),
            realized_pnl=0.0,
            is_open=True,
        )

        self.positions.append(position)

        self.state.open_positions.append({
            "symbol": symbol,
            "asset_class": asset_class,
            "side": side,
            "entry_price": entry_price,
            "quantity": quantity,
            "entry_cost": entry_cost.__dict__,
        })

        AccountPersistence.save(self.state)

        TradeLogger.log({
            "event": "OPEN",
            "symbol": symbol,
            "asset_class": asset_class,
            "side": side,
            "entry_price": entry_price,
            "quantity": quantity,
            "broker": self.active_broker,
        })

    # =========================
    # 📤 CLOSE TRADE
    # =========================
    def close_trade(
        self,
        symbol: str,
        exit_price: float,
    ):

        for position in self.positions:
            if position.symbol == symbol and position.is_open:

                position.current_price = exit_price
                position.is_open = False

                # Compute realized pnl using your existing engine
                snapshot = compute_portfolio_snapshot(
                    self.positions,
                    self.capital_engine.get_balance()
                )

                position.realized_pnl = snapshot.total_net_realized

                self.state.trade_history.append({
                    "symbol": symbol,
                    "exit_price": exit_price,
                    "pnl": position.realized_pnl,
                })

                # Update capital
                new_balance = snapshot.live_equity
                self.capital_engine.update_balance(new_balance)

                AccountPersistence.save(self.state)

                TradeLogger.log({
                    "event": "CLOSE",
                    "symbol": symbol,
                    "exit_price": exit_price,
                    "realized_pnl": position.realized_pnl,
                    "balance": new_balance,
                    "broker": self.active_broker,
                })

                return

    # =========================
    # 🔄 UPDATE MARKET PRICES
    # =========================
    def update_market_prices(self, price_map: Dict[str, float]):
        for position in self.positions:
            if position.symbol in price_map:
                position.current_price = price_map[position.symbol]

    # =========================
    # 📊 GET DASHBOARD SNAPSHOT
    # =========================
    def get_snapshot(self) -> dict:

        snapshot = compute_portfolio_snapshot(
            self.positions,
            self.capital_engine.get_balance()
        )

        return {
            "broker": self.active_broker,
            "balance": snapshot.live_equity,
            "realized_pnl": snapshot.total_net_realized,
            "unrealized_pnl": snapshot.total_net_unrealized,
            "open_positions": snapshot.open_positions,
            "closed_positions": snapshot.closed_positions,
        }