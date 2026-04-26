from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

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

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AccountState":
        state = AccountState()
        state.balance = float(data.get("balance", 0.0) or 0.0)
        state.open_positions = data.get("open_positions", [])
        state.trade_history = data.get("trade_history", [])
        return state


class AccountPersistence:
    @staticmethod
    def load() -> AccountState:
        if not os.path.exists(STATE_FILE):
            return AccountState()

        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return AccountState.from_dict(json.load(f))
        except Exception:
            return AccountState()

    @staticmethod
    def save(state: AccountState) -> None:
        os.makedirs("artifacts", exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)


class CapitalEngine:
    """
    PCNRASS-safe capital engine.

    Preserves public API:
    - initialize()
    - get_balance()
    - update_balance()
    - get_active_broker_name()

    Balance source priority:
    1. Coinbase live balance via PEM/JWT
    2. OANDA NAV/balance via adapter
    3. Generic broker account fields
    4. Persisted balance fallback
    """

    def __init__(self):
        self.state = AccountPersistence.load()
        self.active_broker = None
        self.broker_name: Optional[str] = None
        self.mode: Optional[str] = None
        self.last_balance_source: str = "persisted"

    def initialize(self, broker_name: str = "coinbase", mode: str = "live") -> None:
        self.broker_name = (broker_name or "coinbase").strip().lower()
        self.mode = (mode or "live").strip().lower()

        balance = None

        try:
            self.active_broker = initialize_broker(self.broker_name, mode=self.mode)
            balance = self._fetch_live_balance()
        except Exception as exc:
            print(f"[CAPITAL ERROR] {exc}")
            print("[CAPITAL FALLBACK] Using persisted balance")

        if balance is not None and balance >= 0:
            self.state.balance = float(balance)
            AccountPersistence.save(self.state)
            print(
                f"[CAPITAL] Live balance loaded from "
                f"{self.last_balance_source}: {self.state.balance:.2f}"
            )
        else:
            AccountPersistence.save(self.state)
            print(
                "[CAPITAL WARNING] Live balance unavailable — "
                f"persisted balance remains: {self.state.balance:.2f}"
            )

    def _fetch_live_balance(self) -> Optional[float]:
        if self.broker_name == "coinbase":
            coinbase_balance = self._fetch_coinbase_live_balance()
            if coinbase_balance is not None:
                self.last_balance_source = "coinbase"
                return coinbase_balance

        if self.active_broker is not None and hasattr(self.active_broker, "get_account_summary"):
            try:
                summary = self.active_broker.get_account_summary()

                if hasattr(self.active_broker, "extract_balance_nav"):
                    bal = self.active_broker.extract_balance_nav(summary)

                    if bal.get("nav") is not None:
                        self.last_balance_source = "oanda_nav"
                        return float(bal["nav"])

                    if bal.get("balance") is not None:
                        self.last_balance_source = "oanda_balance"
                        return float(bal["balance"])

            except Exception as exc:
                print(f"[OANDA BALANCE ERROR] {exc}")

        if self.active_broker is not None and hasattr(self.active_broker, "get_account_info"):
            try:
                info = self.active_broker.get_account_info()

                if isinstance(info, dict):
                    for key in ("balance", "equity", "nav", "NAV", "cash", "buying_power"):
                        value = info.get(key)
                        if value is not None:
                            self.last_balance_source = f"generic_{key}"
                            return float(value)

            except Exception as exc:
                print(f"[GENERIC BALANCE ERROR] {exc}")

        return None

    def _read_text_file(self, candidates: list[str]) -> str:
        for candidate in candidates:
            path = Path(candidate)
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8").strip()
                except Exception:
                    continue
        return ""

    def _resolve_coinbase_key_name(self) -> str:
        """
        Resolve Coinbase API key name without exposing the private key.

        Priority:
        1. COINBASE_KEY_NAME environment variable
        2. coinbase_key_name.txt in project root
        3. COINBASE_API_KEY_NAME environment variable
        4. COINBASE_API_KEY environment variable
        """
        key_name = (os.getenv("COINBASE_KEY_NAME") or "").strip()
        if key_name:
            return key_name

        key_name = self._read_text_file([
            "coinbase_key_name.txt",
            "secrets/coinbase_key_name.txt",
            ".secrets/coinbase_key_name.txt",
        ])
        if key_name:
            return key_name

        for env_key in ("COINBASE_API_KEY_NAME", "COINBASE_API_KEY"):
            key_name = (os.getenv(env_key) or "").strip()
            if key_name:
                return key_name

        return ""

    def _resolve_coinbase_pem_path(self) -> str:
        """
        Resolve Coinbase PEM path.

        Priority:
        1. COINBASE_PRIVATE_KEY_PATH
        2. coinbase_private_key.pem in project root
        3. secrets/coinbase_private_key.pem
        4. .secrets/coinbase_private_key.pem
        """
        env_path = (os.getenv("COINBASE_PRIVATE_KEY_PATH") or "").strip()
        if env_path and Path(env_path).exists():
            return env_path

        for candidate in (
            "coinbase_private_key.pem",
            "secrets/coinbase_private_key.pem",
            ".secrets/coinbase_private_key.pem",
        ):
            if Path(candidate).exists():
                return candidate

        return env_path or "coinbase_private_key.pem"

    def _fetch_coinbase_live_balance(self) -> Optional[float]:
        key_name = self._resolve_coinbase_key_name()
        pem_path = self._resolve_coinbase_pem_path()

        if not key_name:
            print(
                "[COINBASE BALANCE ERROR] Coinbase key name not found. "
                "Create coinbase_key_name.txt or set COINBASE_KEY_NAME."
            )
            return None

        if not Path(pem_path).exists():
            print(f"[COINBASE BALANCE ERROR] PEM file not found: {pem_path}")
            return None

        try:
            import jwt
        except Exception as exc:
            print(f"[COINBASE BALANCE ERROR] PyJWT unavailable: {exc}")
            print("Run: pip install pyjwt")
            return None

        try:
            private_key = Path(pem_path).read_text(encoding="utf-8")

            path = "/api/v3/brokerage/accounts"
            now = int(time.time())

            payload = {
                "sub": key_name,
                "iss": "cdp",
                "nbf": now,
                "exp": now + 120,
                "uri": f"GET {path}",
            }

            token = jwt.encode(
                payload,
                private_key,
                algorithm="ES256",
                headers={
                    "kid": key_name,
                    "nonce": str(now),
                },
            )

            response = requests.get(
                "https://api.coinbase.com" + path,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )

            if response.status_code != 200:
                print(
                    f"[COINBASE BALANCE ERROR] HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return None

            data = response.json()
            accounts = data.get("accounts", [])

            total_available = 0.0
            total_hold = 0.0

            for account in accounts:
                available = account.get("available_balance") or {}
                hold = account.get("hold") or {}

                try:
                    if available.get("value") is not None:
                        total_available += float(available.get("value"))
                except Exception:
                    pass

                try:
                    if hold.get("value") is not None:
                        total_hold += float(hold.get("value"))
                except Exception:
                    pass

            return round(total_available + total_hold, 6)

        except Exception as exc:
            print(f"[COINBASE BALANCE ERROR] {exc}")
            return None

    def get_balance(self) -> float:
        return float(self.state.balance)

    def update_balance(self, new_balance: float) -> None:
        self.state.balance = float(new_balance)
        AccountPersistence.save(self.state)

    def get_active_broker_name(self) -> str:
        return self.broker_name or "none"