from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from backend.runtime.broker_readiness_framework import (
    broker_readiness_payload,
    build_broker_readiness_snapshot,
)


class OandaLiveReadOnlyAdapter:
    """Canonical OANDA LIVE read-only adapter.

    This adapter exposes only read operations. It deliberately does not define
    submit, modify, close, cancel, market, limit, or stop order methods.
    """

    def __init__(
        self,
        *,
        env: Mapping[str, Any] | None = None,
        read_client: Any | None = None,
        client_factory: Callable[[], Any] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.env = env if isinstance(env, Mapping) else os.environ
        self.read_client = read_client
        self.client_factory = client_factory
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.connected = False
        self.authenticated = False
        self.broker_health = "UNKNOWN"
        self.connection_error = ""
        self.last_successful_sync = ""

    def credential_diagnostics(self) -> dict[str, Any]:
        token_present = _present(self.env, ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN"))
        account_present = _present(self.env, ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID"))
        base_url_present = _present(self.env, ("OANDA_BASE_URL",))
        missing: list[str] = []
        if not token_present:
            missing.append("OANDA_API_KEY|OANDA_ACCESS_TOKEN|OANDA_TOKEN")
        if not account_present:
            missing.append("OANDA_ACCOUNT_ID|OANDA_LIVE_ACCOUNT_ID|OANDA_PRACTICE_ACCOUNT_ID")
        if not base_url_present:
            missing.append("OANDA_BASE_URL")
        ready = token_present and account_present and base_url_present
        return {
            "oanda_token_present": token_present,
            "oanda_account_present": account_present,
            "oanda_base_url_present": base_url_present,
            "credential_status": "PRESENT" if ready else "MISSING",
            "missing_credentials": missing,
            "redacted": True,
        }

    def authenticate(self) -> dict[str, Any]:
        status = self.sync(include_market_data=False)
        return {
            "authenticated": status["authenticated"],
            "connected": status["connected"],
            "broker_health": status["broker_health"],
            "connection_error": status["connection_error"],
        }

    def get_account_summary(self) -> Any:
        return _call_first(self._client(), ("get_account_summary", "account_summary"))

    def get_nav(self) -> Any:
        return _extract_account(self.get_account_summary()).get("NAV")

    def get_balance(self) -> Any:
        return _extract_account(self.get_account_summary()).get("balance")

    def get_margin(self) -> Any:
        account = _extract_account(self.get_account_summary())
        return {
            "margin_used": account.get("marginUsed") or account.get("margin_used"),
            "margin_available": account.get("marginAvailable") or account.get("margin_available"),
        }

    def get_positions(self) -> Any:
        return _call_first(self._client(), ("get_open_positions", "get_positions", "list_positions"))

    def get_open_trades(self) -> Any:
        return _call_first(self._client(), ("get_open_trades", "list_open_trades", "get_trades"))

    def get_pricing(self) -> Any:
        return _call_first(self._client(), ("get_pricing", "get_prices", "pricing", "heartbeat"))

    def get_instruments(self) -> Any:
        return _call_first(self._client(), ("get_instruments", "list_instruments", "instruments"))

    def get_account_metadata(self) -> Any:
        return _call_first(self._client(), ("get_account_metadata", "account_metadata", "get_account_details"))

    def get_server_status(self) -> Any:
        return _call_first(self._client(), ("get_server_status", "server_status", "heartbeat"))

    def heartbeat(self) -> Any:
        client = self._client()
        heartbeat = getattr(client, "heartbeat", None)
        if callable(heartbeat):
            return heartbeat()
        return {"ok": True, "timestamp": self.now().isoformat()}

    def connection_status(self) -> dict[str, Any]:
        return self._status_payload()

    def sync(self, *, include_market_data: bool = True) -> dict[str, Any]:
        diagnostics = self.credential_diagnostics()
        if diagnostics["credential_status"] != "PRESENT":
            self.connected = False
            self.authenticated = False
            self.broker_health = "UNKNOWN"
            self.connection_error = "missing credentials"
            return self._status_payload(credential_diagnostics=diagnostics)
        try:
            account_payload = self.get_account_summary()
            positions_payload = self.get_positions()
            open_trades_payload = self.get_open_trades()
            instruments_payload = self.get_instruments()
            pricing_payload = self.get_pricing() if include_market_data else None
            heartbeat_payload = self.heartbeat()
            metadata_payload = self.get_account_metadata()
            account = _extract_account(account_payload)
            self.connected = True
            self.authenticated = bool(account_payload)
            self.broker_health = "HEALTHY" if self.authenticated else "CONNECTED"
            self.connection_error = ""
            if self.authenticated:
                self.last_successful_sync = self.now().isoformat()
            return self._status_payload(
                credential_diagnostics=diagnostics,
                account=account,
                products_loaded=_count_items(instruments_payload),
                market_data_ready=pricing_payload is not None or heartbeat_payload is not None,
                positions_loaded=positions_payload is not None or open_trades_payload is not None,
            )
        except Exception as exc:
            self.connected = False
            self.authenticated = False
            self.broker_health = "UNKNOWN"
            self.connection_error = str(exc)[:160]
            return self._status_payload(credential_diagnostics=diagnostics)

    def _client(self) -> Any:
        if self.read_client is not None:
            return self.read_client
        if self.client_factory is not None:
            self.read_client = self.client_factory()
            return self.read_client
        from backend.app.brokers.oanda_adapter import OandaAdapter

        self.read_client = OandaAdapter()
        return self.read_client

    def _status_payload(
        self,
        *,
        credential_diagnostics: Mapping[str, Any] | None = None,
        account: Mapping[str, Any] | None = None,
        products_loaded: int = 0,
        market_data_ready: bool = False,
        positions_loaded: bool = False,
    ) -> dict[str, Any]:
        diagnostics = dict(credential_diagnostics or self.credential_diagnostics())
        account_payload = dict(account or {})
        balance = _float_or_none(account_payload.get("balance"))
        equity = _float_or_none(account_payload.get("NAV") or account_payload.get("nav"))
        buying_power = _float_or_none(account_payload.get("marginAvailable") or account_payload.get("margin_available"))
        snapshot = build_broker_readiness_snapshot(
            {
                "broker_name": "OANDA",
                "broker_type": "FX",
                "mode": "live",
                "credential_status": diagnostics.get("credential_status"),
                "authenticated": self.authenticated,
                "connected": self.connected,
                "account_loaded": bool(account_payload),
                "market_data_ready": market_data_ready,
                "products_loaded": products_loaded,
                "broker_health": self.broker_health,
                "infrastructure_health": self.broker_health,
                "credentials_health": "READY" if diagnostics.get("credential_status") == "PRESENT" else "MISSING",
                "authentication_health": "AUTHENTICATED" if self.authenticated else "NOT_TESTED",
                "connection_health": "CONNECTED" if self.connected else "NOT_CONNECTED",
                "market_data_health": "READY" if market_data_ready else "NOT_TESTED",
                "account_data_health": "READY" if account_payload else "UNAVAILABLE",
                "execution_supported": True,
                "execution_enabled": False,
                "last_successful_sync": self.last_successful_sync,
                "account_balance": balance,
                "equity": equity,
                "buying_power": buying_power,
                "authority_block_reason": self.connection_error or "Broker Execution Disabled",
            }
        )
        readiness = broker_readiness_payload(snapshot)
        return {
            "selected_broker": "OANDA",
            "broker": "OANDA",
            "broker_type": "FX",
            "broker_mode": "live",
            "credential_diagnostics": diagnostics,
            "credential_status": diagnostics.get("credential_status", "MISSING"),
            "authenticated": self.authenticated,
            "connected": self.connected,
            "broker_authenticated": self.authenticated,
            "broker_connected": self.connected,
            "broker_health": self.broker_health,
            "infrastructure_health": self.broker_health,
            "credentials_health": "READY" if diagnostics.get("credential_status") == "PRESENT" else "MISSING",
            "authentication_health": "AUTHENTICATED" if self.authenticated else "NOT_TESTED",
            "connection_health": "CONNECTED" if self.connected else "NOT_CONNECTED",
            "market_data_health": "READY" if market_data_ready else "NOT_TESTED",
            "account_data_health": "READY" if account_payload else "UNAVAILABLE",
            "connection_status": self.broker_health,
            "connection_error": self.connection_error,
            "last_successful_sync": self.last_successful_sync,
            "last_broker_sync": self.last_successful_sync or "DATA UNAVAILABLE",
            "account_equity": equity,
            "cash": balance,
            "buying_power": buying_power,
            "available_balance": buying_power,
            "products_loaded": products_loaded,
            "market_data_status": "OK" if market_data_ready else "NOT_TESTED",
            "account_loaded": bool(account_payload),
            "positions_loaded": positions_loaded,
            "execution_supported": True,
            "execution_enabled": False,
            "broker_execution_enabled": False,
            "can_live_execute": False,
            "execution_authority": False,
            "authority_reason": readiness["authority_block_reason"],
            "live_authority_state": "BLOCKED",
            "broker_readiness": readiness,
            "readiness_score": readiness["readiness_score"],
            "drawdown_status": "UNKNOWN" if equity is None else "AVAILABLE",
            "drawdown_reason": "Broker balance unavailable" if equity is None else "",
            "advisory_only": True,
            "execution_allowed": False,
        }


def _present(env: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return any(bool(str(env.get(name, "")).strip()) for name in names)


def _call_first(client: Any, method_names: tuple[str, ...]) -> Any:
    for name in method_names:
        method = getattr(client, name, None)
        if callable(method):
            return method()
    return None


def _extract_account(payload: Any) -> dict[str, Any]:
    payload = _plain(payload)
    if isinstance(payload, dict):
        account = payload.get("account") or payload.get("data") or payload
        return dict(account) if isinstance(account, Mapping) else {}
    return {}


def _count_items(payload: Any) -> int:
    payload = _plain(payload)
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("instruments", "products", "data", "results", "prices"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if payload else 0
    return 0


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict()
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return {key: item for key, item in vars(value).items() if not key.startswith("_")}
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["OandaLiveReadOnlyAdapter"]
