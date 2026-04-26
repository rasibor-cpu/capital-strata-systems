from __future__ import annotations

"""
CSS Account Engine
------------------
PCNRASS-safe replacement file.

Purpose
-------
- Removes static starting capital assumptions.
- Fetches live broker balance where available and explicitly requests live broker mode by default.
- Persists the last verified account state across logon/logoff and dashboard cycles.
- Does not overwrite existing transaction/open-position history unless a verified newer state is available.
- Fails safely: if broker balance cannot be fetched, it reloads the last persisted verified balance.

Expected project context
------------------------
- Uses project-root-safe broker_bootstrap import from backend.app.brokers first, then backend.brokers fallback
- Default state file: artifacts/css_account_state.json
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_local_env_file() -> None:
    """
    Load .env from project root without requiring python-dotenv.

    This is PCNRASS-safe:
    - Does not overwrite environment variables that already exist.
    - Reads only simple KEY=VALUE lines.
    - Ignores comments and blank lines.
    """
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Fail softly; the account engine will still report missing variables clearly.
        return


_load_local_env_file()

import sys
from pathlib import Path as _Path

_PROJECT_ROOT = _Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from backend.app.brokers.broker_bootstrap import initialize_broker
except ModuleNotFoundError:
    from backend.brokers.broker_bootstrap import initialize_broker

try:
    from backend.app.brokers.coinbase_balance_fetcher import CoinbaseBalanceFetcher
except ModuleNotFoundError:
    CoinbaseBalanceFetcher = None


STATE_FILE = Path("artifacts/css_account_state.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class AccountState:
    """
    Durable account state used by CSS.

    Important:
    - balance is the last verified broker balance when broker fetch succeeds.
    - if live fetch fails, the engine retains the last persisted verified balance.
    - no static capital fallback is used.
    """

    def __init__(
        self,
        balance: float = 0.0,
        broker: str = "UNKNOWN",
        currency: str = "USD",
        open_positions: Optional[List[Dict[str, Any]]] = None,
        trade_history: Optional[List[Dict[str, Any]]] = None,
        last_verified_balance: Optional[float] = None,
        last_verified_at: Optional[str] = None,
        last_sync_status: str = "INIT",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.balance: float = _safe_float(balance, 0.0)
        self.broker: str = broker or "UNKNOWN"
        self.currency: str = currency or "USD"
        self.open_positions: List[Dict[str, Any]] = open_positions or []
        self.trade_history: List[Dict[str, Any]] = trade_history or []
        self.last_verified_balance: Optional[float] = (
            _safe_float(last_verified_balance, self.balance)
            if last_verified_balance is not None
            else None
        )
        self.last_verified_at: Optional[str] = last_verified_at
        self.last_sync_status: str = last_sync_status
        self.metadata: Dict[str, Any] = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "balance": self.balance,
            "broker": self.broker,
            "currency": self.currency,
            "open_positions": self.open_positions,
            "trade_history": self.trade_history,
            "last_verified_balance": self.last_verified_balance,
            "last_verified_at": self.last_verified_at,
            "last_sync_status": self.last_sync_status,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AccountState":
        return cls(
            balance=_safe_float(payload.get("balance"), 0.0),
            broker=str(payload.get("broker") or "UNKNOWN"),
            currency=str(payload.get("currency") or "USD"),
            open_positions=list(payload.get("open_positions") or []),
            trade_history=list(payload.get("trade_history") or []),
            last_verified_balance=payload.get("last_verified_balance"),
            last_verified_at=payload.get("last_verified_at"),
            last_sync_status=str(payload.get("last_sync_status") or "LOADED"),
            metadata=dict(payload.get("metadata") or {}),
        )


class AccountEngine:
    """
    Broker-aware account state manager.

    Public methods are intentionally broad to avoid breaking existing dashboard code:
    - load()
    - save()
    - sync_from_broker()
    - get_balance()
    - get_state()
    - record_trade()
    - update_open_positions()
    - refresh()
    """

    def __init__(
        self,
        broker_name: Optional[str] = None,
        state_file: Path | str = STATE_FILE,
        auto_sync: bool = True,
    ) -> None:
        self.state_file = Path(state_file)
        self.broker_name = broker_name or os.getenv("CSS_ACTIVE_BROKER") or os.getenv("BROKER") or "coinbase"
        self.broker_mode = (
            os.getenv("CSS_BROKER_MODE")
            or os.getenv("BROKER_MODE")
            or os.getenv("CSS_EXECUTION_MODE")
            or "live"
        ).lower().strip()
        self.state: AccountState = self.load()
        self.broker: Any = None

        if auto_sync:
            self.sync_from_broker()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> AccountState:
        try:
            if not self.state_file.exists():
                return AccountState(
                    broker=self.broker_name,
                    last_sync_status="NO_STATE_FILE_YET",
                    metadata={"created_at": _utc_now()},
                )

            with self.state_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            state = AccountState.from_dict(payload)
            state.last_sync_status = "LOADED_FROM_DISK"
            return state

        except Exception as exc:
            return AccountState(
                broker=self.broker_name,
                last_sync_status="LOAD_FAILED_USING_EMPTY_STATE",
                metadata={"load_error": str(exc), "load_failed_at": _utc_now()},
            )

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        tmp_file = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, indent=2, sort_keys=True)

        tmp_file.replace(self.state_file)

    # ------------------------------------------------------------------
    # Broker initialization and live balance extraction
    # ------------------------------------------------------------------

    def _initialize_broker_safely(self) -> Any:
        if self.broker is not None:
            return self.broker

        # Different CSS branches have used slightly different bootstrap signatures.
        # Try the least invasive patterns without breaking older code.
        attempts: List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]] = [
            # Newer CSS broker bootstrap versions require explicit live mode
            # to avoid silent paper-mode regression.
            ("keyword_name_mode", tuple(), {"broker_name": self.broker_name, "mode": self.broker_mode}),
            ("keyword_broker_mode", tuple(), {"broker": self.broker_name, "mode": self.broker_mode}),
            ("keyword_name_trading_mode", tuple(), {"broker_name": self.broker_name, "trading_mode": self.broker_mode}),
            ("keyword_broker_trading_mode", tuple(), {"broker": self.broker_name, "trading_mode": self.broker_mode}),
            ("positional_name_mode", (self.broker_name, self.broker_mode), {}),
            ("keyword_name", tuple(), {"broker_name": self.broker_name}),
            ("keyword_broker", tuple(), {"broker": self.broker_name}),
            ("positional", (self.broker_name,), {}),
            ("no_args", tuple(), {}),
        ]

        last_error: Optional[str] = None

        for _label, args, kwargs in attempts:
            try:
                self.broker = initialize_broker(*args, **kwargs)
                if self.broker is not None:
                    return self.broker
            except TypeError as exc:
                last_error = str(exc)
                continue
            except Exception as exc:
                last_error = str(exc)
                break

        raise RuntimeError(f"Broker initialization failed for {self.broker_name}: {last_error}")

    def _extract_balance_from_dict(self, payload: Dict[str, Any]) -> Optional[Tuple[float, str]]:
        """
        Supports common account/balance response shapes without hard-coding one adapter version.
        """
        if not payload:
            return None

        currency = str(
            payload.get("currency")
            or payload.get("asset")
            or payload.get("base_currency")
            or payload.get("account_currency")
            or "USD"
        )

        direct_keys = (
            "balance",
            "available_balance",
            "available",
            "cash",
            "equity",
            "portfolio_value",
            "total_balance",
            "account_value",
            "value",
        )

        for key in direct_keys:
            if key in payload:
                value = payload.get(key)
                if isinstance(value, dict):
                    nested_amount = (
                        value.get("value")
                        or value.get("amount")
                        or value.get("balance")
                        or value.get("available")
                    )
                    amount = _safe_float(nested_amount, -1.0)
                else:
                    amount = _safe_float(value, -1.0)

                if amount >= 0:
                    return amount, currency

        # Coinbase-like nested account responses
        for container_key in ("account", "portfolio", "data", "result"):
            container = payload.get(container_key)
            if isinstance(container, dict):
                found = self._extract_balance_from_dict(container)
                if found:
                    return found

        # Coinbase-like list of balances/accounts
        for list_key in ("accounts", "balances", "portfolios"):
            items = payload.get(list_key)
            if isinstance(items, list):
                total = 0.0
                found_any = False

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    # Prefer USD/cash-like entries when identifiable.
                    item_currency = str(
                        item.get("currency")
                        or item.get("asset")
                        or item.get("symbol")
                        or item.get("account_currency")
                        or currency
                    )

                    candidate = self._extract_balance_from_dict(item)
                    if candidate:
                        amount, candidate_currency = candidate
                        if item_currency.upper() in {"USD", "USDC", "USDT"} or candidate_currency.upper() in {"USD", "USDC", "USDT"}:
                            total += amount
                            found_any = True

                if found_any:
                    return total, "USD"

        return None

    def _call_first_available(self, obj: Any, method_names: List[str]) -> Any:
        for method_name in method_names:
            method = getattr(obj, method_name, None)
            if callable(method):
                return method()
        raise AttributeError(f"No supported balance method found on broker adapter: {method_names}")

    def _fetch_coinbase_balance_direct(self) -> Optional[Tuple[float, str, Dict[str, Any]]]:
        """
        Direct Coinbase balance path using existing coinbase_balance_fetcher.py.

        This is intentionally used before generic adapter-method discovery because
        the current Coinbase adapter initializes successfully but does not expose
        a public get_balance/get_accounts method.
        """
        if self.broker_name.lower().strip() != "coinbase":
            return None

        if CoinbaseBalanceFetcher is None:
            return None

        # Support both naming conventions already present in CSS .env files:
        # - COINBASE_CDP_KEY_NAME / COINBASE_CDP_PRIVATE_KEY_PATH
        # - COINBASE_KEY_NAME / COINBASE_PRIVATE_KEY_PATH
        #
        # Coinbase Advanced JWT signing requires the full CDP resource key name
        # where available, usually:
        # organizations/.../apiKeys/...
        key_name = (
            os.getenv("COINBASE_CDP_KEY_NAME")
            or os.getenv("COINBASE_KEY_NAME")
        )
        private_key_path = (
            os.getenv("COINBASE_CDP_PRIVATE_KEY_PATH")
            or os.getenv("COINBASE_PRIVATE_KEY_PATH")
            or os.getenv("COINBASE_PEM_PATH")
            or os.getenv("COINBASE_PRIVATE_KEY_FILE")
        )

        if not key_name:
            raise RuntimeError("COINBASE_CDP_KEY_NAME or COINBASE_KEY_NAME is missing from .env")

        if not private_key_path:
            raise RuntimeError("COINBASE_CDP_PRIVATE_KEY_PATH or COINBASE_PRIVATE_KEY_PATH is missing from .env")

        key_path = Path(private_key_path)
        if not key_path.is_absolute():
            key_path = Path.cwd() / key_path

        if not key_path.exists():
            raise FileNotFoundError(f"Coinbase PEM file not found: {key_path}")

        fetcher = CoinbaseBalanceFetcher(
            key_name=key_name,
            private_key_path=str(key_path),
        )

        balance = fetcher.get_balance()
        if balance is None:
            raise RuntimeError("coinbase_balance_fetcher returned None")

        return (
            _safe_float(balance, 0.0),
            "USD",
            {
                "source_type": "coinbase_balance_fetcher",
                "key_name": key_name,
                "private_key_path": str(key_path),
            },
        )

    def fetch_live_balance(self) -> Tuple[float, str, Dict[str, Any]]:
        """
        Returns: (balance, currency, raw_payload_summary)

        No static fallback occurs here. Failure is handled by sync_from_broker().
        """
        direct_coinbase = self._fetch_coinbase_balance_direct()
        if direct_coinbase is not None:
            return direct_coinbase

        broker = self._initialize_broker_safely()

        method_names = [
            "get_account_balance",
            "fetch_account_balance",
            "get_balance",
            "fetch_balance",
            "get_account",
            "get_accounts",
            "get_portfolio",
            "fetch_portfolio",
        ]

        raw = self._call_first_available(broker, method_names)

        if isinstance(raw, (int, float, str)):
            balance = _safe_float(raw, -1.0)
            if balance >= 0:
                return balance, "USD", {"source_type": type(raw).__name__}

        if isinstance(raw, dict):
            extracted = self._extract_balance_from_dict(raw)
            if extracted:
                balance, currency = extracted
                return balance, currency, {"source_type": "dict", "keys": list(raw.keys())[:20]}

        if isinstance(raw, list):
            total = 0.0
            found_any = False
            for item in raw:
                if isinstance(item, dict):
                    extracted = self._extract_balance_from_dict(item)
                    if extracted:
                        amount, currency = extracted
                        if currency.upper() in {"USD", "USDC", "USDT"}:
                            total += amount
                            found_any = True
            if found_any:
                return total, "USD", {"source_type": "list", "count": len(raw)}

        raise ValueError(f"Could not extract balance from broker response type: {type(raw).__name__}")

    # ------------------------------------------------------------------
    # Public account operations
    # ------------------------------------------------------------------

    def sync_from_broker(self) -> AccountState:
        """
        Fetches live balance and persists it.

        If live fetch fails:
        - preserves last verified balance
        - does not overwrite history
        - saves sync error for dashboard visibility
        """
        try:
            balance, currency, summary = self.fetch_live_balance()

            self.state.balance = balance
            self.state.last_verified_balance = balance
            self.state.currency = currency
            self.state.broker = self.broker_name
            self.state.metadata["broker_mode"] = self.broker_mode
            self.state.last_verified_at = _utc_now()
            self.state.last_sync_status = "LIVE_BALANCE_VERIFIED"
            self.state.metadata.update(
                {
                    "last_live_balance_summary": summary,
                    "last_sync_error": None,
                    "updated_at": _utc_now(),
                }
            )
            self.save()
            return self.state

        except Exception as exc:
            fallback = self.state.last_verified_balance
            if fallback is not None:
                self.state.balance = _safe_float(fallback, self.state.balance)

            self.state.broker = self.broker_name
            self.state.metadata["broker_mode"] = self.broker_mode
            self.state.last_sync_status = "LIVE_BALANCE_FAILED_USING_LAST_VERIFIED"
            self.state.metadata.update(
                {
                    "last_sync_error": str(exc),
                    "last_sync_error_at": _utc_now(),
                    "updated_at": _utc_now(),
                }
            )
            self.save()
            return self.state

    def refresh(self) -> AccountState:
        return self.sync_from_broker()

    def get_balance(self, live: bool = False) -> float:
        if live:
            self.sync_from_broker()
        return _safe_float(self.state.balance, 0.0)

    def get_state(self, live: bool = False) -> Dict[str, Any]:
        if live:
            self.sync_from_broker()
        return self.state.to_dict()

    def update_open_positions(self, positions: List[Dict[str, Any]]) -> None:
        self.state.open_positions = positions or []
        self.state.metadata["positions_updated_at"] = _utc_now()
        self.save()

    def record_trade(self, trade: Dict[str, Any]) -> None:
        if not isinstance(trade, dict):
            trade = {"raw_trade": str(trade)}

        trade.setdefault("recorded_at", _utc_now())
        self.state.trade_history.append(trade)
        self.state.metadata["trade_history_updated_at"] = _utc_now()
        self.save()

    def append_transaction(self, transaction: Dict[str, Any]) -> None:
        self.record_trade(transaction)


# ----------------------------------------------------------------------
# Backward-compatible module-level helpers
# ----------------------------------------------------------------------

_DEFAULT_ENGINE: Optional[AccountEngine] = None


def get_account_engine(broker_name: Optional[str] = None, auto_sync: bool = True) -> AccountEngine:
    global _DEFAULT_ENGINE

    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = AccountEngine(broker_name=broker_name, auto_sync=auto_sync)

    return _DEFAULT_ENGINE


def load_account_state() -> Dict[str, Any]:
    return get_account_engine(auto_sync=False).get_state(live=False)


def save_account_state(state: Dict[str, Any]) -> None:
    engine = get_account_engine(auto_sync=False)
    engine.state = AccountState.from_dict(state or {})
    engine.save()


def refresh_account_state_from_broker(broker_name: Optional[str] = None) -> Dict[str, Any]:
    return get_account_engine(broker_name=broker_name, auto_sync=False).refresh().to_dict()


def get_account_balance(live: bool = False) -> float:
    return get_account_engine(auto_sync=False).get_balance(live=live)


if __name__ == "__main__":
    engine = AccountEngine(auto_sync=True)
    state = engine.get_state(live=False)

    print("CSS Account Engine")
    print("------------------")
    print(f"Broker: {state.get('broker')}")
    print(f"Mode: {state.get('metadata', {}).get('broker_mode', 'unknown')}")
    print(f"Balance: {state.get('balance')} {state.get('currency')}")
    print(f"Status: {state.get('last_sync_status')}")
    print(f"Last verified: {state.get('last_verified_at')}")
    if state.get("metadata", {}).get("last_sync_error"):
        print(f"Last sync error: {state['metadata']['last_sync_error']}")
