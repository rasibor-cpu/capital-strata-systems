from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


READ_ONLY_EXECUTION_SCOPE = "LIVE READ-ONLY VALIDATION"
DISABLED_EXECUTION_STATUS = "DISABLED"
UNKNOWN_DRAW_DOWN_REASON = "Broker balance unavailable"


@dataclass(frozen=True)
class CoinbaseLiveCredentials:
    key_name_present: bool
    private_key_present: bool
    key_file_present: bool
    missing_credentials: tuple[str, ...] = ()
    key_name: str = field(default="", repr=False)
    private_key: str = field(default="", repr=False)

    @property
    def ready(self) -> bool:
        return self.key_name_present and (self.private_key_present or self.key_file_present)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "coinbase_key_present": self.key_name_present,
            "coinbase_private_key_present": self.private_key_present,
            "coinbase_key_file_present": self.key_file_present,
            "missing_credentials": list(self.missing_credentials),
            "credential_status": "PRESENT" if self.ready else "MISSING",
            "redacted": True,
        }


class CoinbaseLiveReadOnlyAdapter:
    """
    Canonical Coinbase LIVE read-only adapter.

    The adapter deliberately exposes only read methods. It contains no order,
    cancel, amend, or modify methods, and every status payload keeps broker
    execution disabled.
    """

    def __init__(
        self,
        *,
        env: Mapping[str, Any] | None = None,
        read_client: Any | None = None,
        client_factory: Callable[[CoinbaseLiveCredentials], Any] | None = None,
        now: Callable[[], datetime] | None = None,
        default_product_id: str = "BTC-USD",
    ) -> None:
        self._env = env if isinstance(env, Mapping) else os.environ
        self.credentials = load_coinbase_live_credentials(self._env)
        self._read_client = read_client
        self._client_factory = client_factory
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.default_product_id = default_product_id
        self.health = "UNKNOWN"
        self.connected = False
        self.authenticated = False
        self.connection_error = ""
        self.last_successful_sync = ""

    def connection_status(self) -> dict[str, Any]:
        return self._status_payload()

    def authenticate(self) -> dict[str, Any]:
        status = self.sync(include_market_data=False)
        return {
            "authenticated": status["broker_authenticated"],
            "connected": status["broker_connected"],
            "broker_health": status["broker_health"],
            "connection_error": status["connection_error"],
        }

    def get_account(self) -> Any:
        client = self._client()
        return self._call_first(client, ("get_account", "get_account_summary", "get_accounts"))

    def get_accounts(self) -> Any:
        client = self._client()
        return self._call_first(client, ("get_accounts", "list_accounts"))

    def get_balances(self) -> Any:
        client = self._client()
        accounts = self._call_first(client, ("get_accounts", "list_accounts"))
        if accounts is not None:
            return accounts
        return self._call_first(
            client,
            ("get_account_balance", "get_balance", "get_live_balance", "get_portfolio_balance", "get_account"),
        )

    def get_products(self) -> Any:
        client = self._client()
        return self._call_first(client, ("get_products", "list_products", "get_product"))

    def get_server_time(self) -> Any:
        client = self._client()
        return self._call_first(client, ("get_time", "get_server_time", "server_time"))

    def get_ticker(self, product_id: str | None = None) -> Any:
        client = self._client()
        selected_product = product_id or self.default_product_id
        for name in ("get_product_ticker", "get_market_trades", "get_price", "get_product"):
            method = getattr(client, name, None)
            if not callable(method):
                continue
            try:
                return method(selected_product)
            except TypeError:
                return method(product_id=selected_product)
        return None

    def sync(self, *, include_market_data: bool = True) -> dict[str, Any]:
        self.health = "CONNECTING"

        if not self.credentials.ready:
            self.connected = False
            self.authenticated = False
            self.health = "UNKNOWN"
            self.connection_error = "missing credentials"
            return self._status_payload(
                read_checks={
                    "account": "NOT_ATTEMPTED",
                    "balances": "NOT_ATTEMPTED",
                    "products": "NOT_ATTEMPTED",
                    "server_time": "NOT_ATTEMPTED",
                    "ticker": "NOT_ATTEMPTED",
                }
            )

        read_checks: dict[str, str] = {}
        try:
            client = self._client()
            self.connected = True
            self.health = "CONNECTED"

            account_payload = self._safe_call(lambda: self.get_account())
            balances_payload = self._safe_call(lambda: self.get_balances())
            products_payload = self._safe_call(lambda: self.get_products())
            server_time_payload = self._safe_call(lambda: self.get_server_time())
            ticker_payload = self._safe_call(lambda: self.get_ticker()) if include_market_data else None

            del client
            read_checks = {
                "account": _read_status(account_payload),
                "balances": _read_status(balances_payload),
                "products": _read_status(products_payload, unavailable_ok=True),
                "server_time": _read_status(server_time_payload, unavailable_ok=True),
                "ticker": _read_status(ticker_payload, unavailable_ok=True),
            }

            if read_checks["account"] == "OK" or read_checks["balances"] == "OK":
                self.authenticated = True
                self.health = "HEALTHY"
                self.connection_error = ""
                self.last_successful_sync = self._now().isoformat()
            else:
                self.authenticated = False
                self.health = "CONNECTED"
                self.connection_error = "authenticated account or balance read unavailable"

            account_values = extract_coinbase_account_values(
                balances_payload if balances_payload is not None else account_payload
            )
            return self._status_payload(
                account_values=account_values,
                read_checks=read_checks,
                products_loaded=count_coinbase_products(products_payload),
                market_data_status="OK" if read_checks["ticker"] == "OK" else read_checks["ticker"],
            )
        except Exception as exc:
            self.connected = False
            self.authenticated = False
            self.health = "UNKNOWN"
            self.connection_error = str(exc)[:160]
            return self._status_payload(read_checks=read_checks)

    def _client(self) -> Any:
        if self._read_client is not None:
            return self._read_client
        if self._client_factory is not None:
            self._read_client = self._client_factory(self.credentials)
            return self._read_client
        self._read_client = _default_coinbase_client(self.credentials)
        return self._read_client

    def _safe_call(self, func: Callable[[], Any]) -> Any:
        try:
            return func()
        except Exception as exc:
            self.connection_error = str(exc)[:160]
            return None

    def _call_first(self, client: Any, method_names: tuple[str, ...]) -> Any:
        for name in method_names:
            method = getattr(client, name, None)
            if not callable(method):
                continue
            return method()
        return None

    def _status_payload(
        self,
        *,
        account_values: Mapping[str, Any] | None = None,
        read_checks: Mapping[str, str] | None = None,
        products_loaded: int = 0,
        market_data_status: str = "NOT_TESTED",
    ) -> dict[str, Any]:
        values = dict(account_values or {})
        has_balance = any(
            values.get(key) is not None
            for key in ("account_equity", "cash", "buying_power", "available_balance")
        )
        return {
            "selected_broker": "COINBASE",
            "broker": "COINBASE",
            "broker_mode": "live",
            "credential_diagnostics": self.credentials.diagnostics(),
            "credential_status": "PRESENT" if self.credentials.ready else "MISSING",
            "broker_connected": bool(self.connected),
            "broker_authenticated": bool(self.authenticated),
            "authenticated": bool(self.authenticated),
            "connected": bool(self.connected),
            "broker_health": self.health,
            "connection_status": self.health,
            "connection_error": self.connection_error,
            "last_successful_sync": self.last_successful_sync,
            "last_broker_sync": self.last_successful_sync or "DATA UNAVAILABLE",
            "execution_scope": READ_ONLY_EXECUTION_SCOPE,
            "broker_execution_status": DISABLED_EXECUTION_STATUS,
            "broker_execution_armed": False,
            "can_live_execute": False,
            "live_order_permission": False,
            "execution_allowed": False,
            "live_micro_pilot_state": "DISARMED",
            "broker_guard": "REJECT_BEFORE_BROKER",
            "order_submission_status": "DISABLED",
            "orders_sent_count": 0,
            "orders_blocked_count": 0,
            "account_equity": values.get("account_equity"),
            "cash": values.get("cash"),
            "buying_power": values.get("buying_power"),
            "available_balance": values.get("available_balance"),
            "products_loaded": int(products_loaded or 0),
            "market_data_status": market_data_status,
            "read_checks": dict(read_checks or {}),
            "drawdown_status": "UNKNOWN" if not has_balance else "AVAILABLE",
            "drawdown_reason": "" if has_balance else UNKNOWN_DRAW_DOWN_REASON,
        }


def load_coinbase_live_credentials(env: Mapping[str, Any] | None = None) -> CoinbaseLiveCredentials:
    source = env if isinstance(env, Mapping) else os.environ
    key_name = _first_present(source, ("COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY"))
    private_key = _first_present(
        source,
        (
            "COINBASE_CDP_PRIVATE_KEY",
            "COINBASE_PRIVATE_KEY",
            "COINBASE_API_SECRET",
            "COINBASE_CDP_PRIVATE_KEY_PATH",
            "COINBASE_PRIVATE_KEY_PATH",
        ),
    )
    key_file = _first_present(source, ("COINBASE_KEY_JSON_PATH", "COINBASE_KEY_JSON", "COINBASE_KEY_FILE"))

    loaded_key_name = key_name
    loaded_private_key = private_key
    if key_file and (not loaded_key_name or not loaded_private_key):
        file_key_name, file_private_key = _load_key_file_values(key_file)
        loaded_key_name = loaded_key_name or file_key_name
        loaded_private_key = loaded_private_key or file_private_key

    missing: list[str] = []
    if not loaded_key_name:
        missing.append("COINBASE_CDP_KEY_NAME|COINBASE_KEY_NAME|COINBASE_API_KEY")
    if not loaded_private_key and not key_file:
        missing.append("COINBASE_CDP_PRIVATE_KEY|COINBASE_PRIVATE_KEY|COINBASE_API_SECRET|COINBASE_KEY_FILE")

    return CoinbaseLiveCredentials(
        key_name_present=bool(loaded_key_name),
        private_key_present=bool(loaded_private_key),
        key_file_present=bool(key_file),
        missing_credentials=tuple(missing),
        key_name=loaded_key_name,
        private_key=loaded_private_key,
    )


def extract_coinbase_account_values(payload: Any) -> dict[str, Any]:
    plain = _to_plain(payload)
    balance = _extract_first_amount(plain, ("available_balance", "balance", "cash", "amount", "value"))
    equity = _extract_first_amount(plain, ("equity", "total", "portfolio_balance", "account_balance", "balance", "value"))
    buying_power = _extract_first_amount(plain, ("buying_power", "available_to_trade", "available_balance", "available", "cash"))
    return {
        "account_equity": equity if equity is not None else balance,
        "cash": balance,
        "buying_power": buying_power,
        "available_balance": buying_power if buying_power is not None else balance,
    }


def count_coinbase_products(payload: Any) -> int:
    plain = _to_plain(payload)
    if isinstance(plain, list):
        return len(plain)
    if isinstance(plain, dict):
        for key in ("products", "data", "results"):
            value = plain.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if plain else 0
    return 0


def _default_coinbase_client(credentials: CoinbaseLiveCredentials) -> Any:
    try:
        from coinbase.rest import RESTClient  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local operator venv
        raise RuntimeError("coinbase RESTClient unavailable") from exc

    return RESTClient(api_key=credentials.key_name, api_secret=credentials.private_key)


def _first_present(env: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = str(env.get(name, "") or "").strip()
        if value:
            return value
    return ""


def _load_key_file_values(path: str) -> tuple[str, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return "", ""
    return (
        str(data.get("name") or data.get("key_name") or data.get("apiKey") or "").strip(),
        str(data.get("privateKey") or data.get("private_key") or data.get("apiSecret") or "").strip(),
    )


def _read_status(payload: Any, *, unavailable_ok: bool = False) -> str:
    if payload is None:
        return "UNAVAILABLE" if unavailable_ok else "FAILED"
    return "OK"


def _to_plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        if isinstance(value, list):
            return [_to_plain(item) for item in value]
        if isinstance(value, dict):
            return {key: _to_plain(item) for key, item in value.items()}
        return value
    if hasattr(value, "to_dict"):
        try:
            return _to_plain(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return {
                key: _to_plain(item)
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        except Exception:
            pass
    return value


def _extract_first_amount(payload: Any, keys: tuple[str, ...]) -> float | None:
    plain = _to_plain(payload)
    if plain is None:
        return None
    if isinstance(plain, (int, float)):
        value = float(plain)
        return value if value >= 0 else None
    if isinstance(plain, str):
        return _parse_amount(plain)
    if isinstance(plain, list):
        total = 0.0
        found = False
        for item in plain:
            amount = _extract_first_amount(item, keys)
            if amount is not None:
                total += amount
                found = True
        return total if found else None
    if isinstance(plain, dict):
        for key in keys:
            if key not in plain:
                continue
            value = plain.get(key)
            if isinstance(value, dict):
                value = value.get("value") or value.get("amount") or value.get("balance")
            amount = _parse_amount(value)
            if amount is not None:
                return amount
        for nested_key in ("accounts", "data", "results"):
            nested = plain.get(nested_key)
            if isinstance(nested, list):
                return _extract_first_amount(nested, keys)
    return None


def _parse_amount(value: Any) -> float | None:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return amount if amount >= 0 else None


__all__ = [
    "CoinbaseLiveCredentials",
    "CoinbaseLiveReadOnlyAdapter",
    "DISABLED_EXECUTION_STATUS",
    "READ_ONLY_EXECUTION_SCOPE",
    "UNKNOWN_DRAW_DOWN_REASON",
    "count_coinbase_products",
    "extract_coinbase_account_values",
    "load_coinbase_live_credentials",
]
