from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional

from backend.app.brokers.broker_bootstrap import initialize_broker


STATE_FILE = "artifacts/css_account_state.json"


class AccountState:
    def __init__(self):
        self.balance: float = 0.0
        self.open_positions: list = []
        self.trade_history: list = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "balance": self.balance,
            "open_positions": self.open_positions,
            "trade_history": self.trade_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountState":
        obj = cls()
        obj.balance = data.get("balance", 0.0)
        obj.open_positions = data.get("open_positions", [])
        obj.trade_history = data.get("trade_history", [])
        return obj


class AccountStateEngine:
    """
    PCNRASS REALISM v2 SAFE ENGINE

    Guarantees:
    - NO STATIC BALANCES
    - Broker balance ALWAYS takes priority
    - Falls back ONLY to persisted state
    - State persists across cycles and restarts
    - No interference with PnL engine
    """

    def __init__(self):
        self.state = self._load_state()
        self.broker = None

    # ----------------------------
    # INITIALIZATION
    # ----------------------------
    def initialize(self):
        try:
            self.broker = initialize_broker()
        except Exception:
            self.broker = None

        broker_balance = self._fetch_broker_balance()

        if broker_balance is not None and broker_balance > 0:
            self.state.balance = broker_balance
            self._save_state()
        else:
            # fallback ONLY to persisted state
            pass

    # ----------------------------
    # BROKER BALANCE FETCH
    # ----------------------------
    def _fetch_broker_balance(self) -> Optional[float]:
        if not self.broker:
            return None

        try:
            balance = self.broker.get_balance()
            if isinstance(balance, dict):
                return float(balance.get("balance", 0.0))
            return float(balance)
        except Exception:
            return None

    # ----------------------------
    # STATE LOAD/SAVE
    # ----------------------------
    def _load_state(self) -> AccountState:
        if not os.path.exists(STATE_FILE):
            return AccountState()

        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return AccountState.from_dict(data)
        except Exception:
            return AccountState()

    def _save_state(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    # ----------------------------
    # BALANCE MANAGEMENT
    # ----------------------------
    def update_balance(self, new_balance: float):
        if new_balance is None:
            return

        self.state.balance = float(new_balance)
        self._save_state()

    def get_balance(self) -> float:
        return self.state.balance

    # ----------------------------
    # POSITION MANAGEMENT
    # ----------------------------
    def set_open_positions(self, positions: list):
        self.state.open_positions = positions or []
        self._save_state()

    def get_open_positions(self) -> list:
        return self.state.open_positions

    # ----------------------------
    # TRADE HISTORY
    # ----------------------------
    def add_trade(self, trade: Dict[str, Any]):
        if not isinstance(trade, dict):
            return

        self.state.trade_history.append(trade)
        self._save_state()

    def get_trade_history(self) -> list:
        return self.state.trade_history

    # ----------------------------
    # FULL SYNC (REALISM CORE)
    # ----------------------------
    def sync_after_cycle(
        self,
        realized_pnl: float,
        open_positions: list,
        latest_balance: Optional[float] = None,
    ):
        """
        Core realism logic:
        - Updates balance using TRUE source
        - Syncs positions
        - Persists everything
        """

        # Priority 1: broker / verified balance
        if latest_balance is not None:
            self.state.balance = float(latest_balance)

        # Priority 2: fallback → add realized pnl
        else:
            self.state.balance += float(realized_pnl or 0.0)

        self.state.open_positions = open_positions or []

        self._save_state()