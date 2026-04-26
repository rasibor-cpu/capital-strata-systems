from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional


# ================================
# 🔌 BROKER INTERFACE (ABSTRACTION)
# ================================

class BaseBrokerAdapter:
    def is_connected(self) -> bool:
        raise NotImplementedError

    def get_balance(self) -> float:
        raise NotImplementedError

    def get_name(self) -> str:
        raise NotImplementedError


# ================================
# 🔌 BROKER IMPLEMENTATIONS (SAFE WRAPPERS)
# ================================

class CoinbaseAdapter(BaseBrokerAdapter):
    def __init__(self):
        self.name = "coinbase"

    def is_connected(self) -> bool:
        return bool(os.getenv("COINBASE_KEY_NAME") and os.getenv("COINBASE_PRIVATE_KEY"))

    def get_balance(self) -> float:
        try:
            # TODO: Replace with real API call (already exists in your adapter layer)
            return float(os.getenv("COINBASE_BALANCE", "0"))
        except Exception:
            return 0.0

    def get_name(self) -> str:
        return self.name


class OandaAdapter(BaseBrokerAdapter):
    def __init__(self):
        self.name = "oanda"

    def is_connected(self) -> bool:
        return bool(os.getenv("OANDA_API_KEY") and os.getenv("OANDA_ACCOUNT_ID"))

    def get_balance(self) -> float:
        try:
            return float(os.getenv("OANDA_BALANCE", "0"))
        except Exception:
            return 0.0

    def get_name(self) -> str:
        return self.name


class PaperBrokerAdapter(BaseBrokerAdapter):
    def __init__(self):
        self.name = "paper"

    def is_connected(self) -> bool:
        return True

    def get_balance(self) -> float:
        return 1000.0  # fallback only

    def get_name(self) -> str:
        return self.name


# ================================
# 🧠 BROKER REGISTRY (UNIVERSAL)
# ================================

class BrokerRegistry:
    def __init__(self):
        self.brokers = [
            CoinbaseAdapter(),
            OandaAdapter(),
            PaperBrokerAdapter(),
        ]

    def get_active_broker(self) -> BaseBrokerAdapter:
        for broker in self.brokers:
            if broker.get_name() != "paper" and broker.is_connected():
                return broker

        # fallback
        return PaperBrokerAdapter()


# ================================
# 💾 ACCOUNT STATE PERSISTENCE
# ================================

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

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AccountState":
        state = AccountState()
        state.balance = data.get("balance", 0.0)
        state.open_positions = data.get("open_positions", [])
        state.trade_history = data.get("trade_history", [])
        return state


class AccountPersistence:
    @staticmethod
    def load() -> AccountState:
        if not os.path.exists(STATE_FILE):
            return AccountState()

        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return AccountState.from_dict(data)
        except Exception:
            return AccountState()

    @staticmethod
    def save(state: AccountState):
        os.makedirs("artifacts", exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state.to_dict(), f, indent=2)


# ================================
# 💰 CAPITAL ENGINE (CORE)
# ================================

class CapitalEngine:
    def __init__(self):
        self.registry = BrokerRegistry()
        self.state = AccountPersistence.load()
        self.active_broker: Optional[BaseBrokerAdapter] = None

    def initialize(self):
        self.active_broker = self.registry.get_active_broker()
        broker_balance = self.active_broker.get_balance()

        # CRITICAL: override stale balance with real broker value
        self.state.balance = broker_balance

        AccountPersistence.save(self.state)

    def get_balance(self) -> float:
        return self.state.balance

    def update_balance(self, new_balance: float):
        self.state.balance = new_balance
        AccountPersistence.save(self.state)

    def get_active_broker_name(self) -> str:
        return self.active_broker.get_name() if self.active_broker else "none"