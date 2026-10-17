"""Binance LIVE read-only adapter. GET-only; no write or execution methods."""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit

import requests


DEFAULT_BINANCE_REST_URL = "https://api.binance.com"
# The API key and signed requests may only go to Binance's own HTTPS REST hosts. Any other value of
# BINANCE_BASE_URL / BINANCE_API_URL / BINANCE_REST_URL is refused (no plain http, no other host).
ALLOWED_BINANCE_REST_HOSTS = frozenset({
    "api.binance.com", "api1.binance.com", "api2.binance.com", "api3.binance.com", "api4.binance.com",
    "api-gcp.binance.com",
})
DEFAULT_QUOTE_SYMBOL = "BTCUSDT"
SOURCE_BINANCE_LIVE_READ_ONLY = "BINANCE_LIVE_READ_ONLY"
_AVAILABLE = "AVAILABLE"
_UNAVAILABLE = "UNAVAILABLE"
_SENSITIVE_ATTRS = frozenset({"api_key", "api_secret", "secret", "signature"})


class BinanceReadOnlyError(Exception):
    """Fail-closed Binance read-only error."""


class BinanceConfigurationError(BinanceReadOnlyError):
    """Missing or unusable Binance configuration."""


class BinanceReadOnlyMethodError(BinanceReadOnlyError):
    """Non-GET HTTP method rejected by the read-only adapter."""


class BinanceJurisdictionError(BinanceReadOnlyError):
    """Operating country unattested or restricted: no request is sent (binance_eligibility)."""


def _allowlisted_base_url(raw: str) -> str:
    """The base URL if it is https on an allowlisted Binance REST host with no path, else ''."""
    try:
        parts = urlsplit(raw)
        port = parts.port  # raises ValueError for a malformed port
    except ValueError:
        return ""
    if parts.scheme != "https" or (parts.hostname or "") not in ALLOWED_BINANCE_REST_HOSTS:
        return ""
    if parts.username or parts.password or port not in (None, 443) or parts.path not in ("", "/"):
        return ""
    if parts.query or parts.fragment:
        return ""
    return f"https://{parts.hostname}"


class BinanceLiveReadOnlyAdapter:
    """GET-only Binance spot adapter for LIVE_READ_ONLY operational certification.

    Credentials are used only to sign authenticated GET requests. They are never
    exposed as public attributes, returned in payloads, or persisted.
    """

    execution_allowed = False
    live_trading_blocked = True
    broker_execution_armed = False
    advisory_only = True

    def __init__(
        self,
        *,
        env: Mapping[str, Any] | None = None,
        transport: Callable[..., Any] | None = None,
        now: Callable[[], datetime] | None = None,
        default_symbol: str = DEFAULT_QUOTE_SYMBOL,
    ) -> None:
        self._env = env if isinstance(env, Mapping) else os.environ
        self._api_key = str(self._env.get("BINANCE_API_KEY") or "").strip()
        self._api_secret = str(self._env.get("BINANCE_API_SECRET") or "").strip()
        configured_url = str(
            self._env.get("BINANCE_BASE_URL")
            or self._env.get("BINANCE_API_URL")
            or self._env.get("BINANCE_REST_URL")
            or DEFAULT_BINANCE_REST_URL
        ).strip().rstrip("/")
        self.base_url = _allowlisted_base_url(configured_url)
        self.base_url_rejected = not self.base_url
        # Jurisdiction gate (same rule as every public Binance path): CA, US and other restricted or
        # unattested countries are refused before any request, signed or not, is sent.
        from backend.signals.market_data import binance_eligibility

        self._eligible, self.eligibility_reason = binance_eligibility(
            str(self._env.get("CSS_OPERATING_COUNTRY") or ""))
        self._transport = transport
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.default_symbol = default_symbol
        self.connected = False
        self.authenticated = False
        self.health = "UNKNOWN"
        self.connection_error = ""
        self.last_successful_sync = ""

    @property
    def eligible(self) -> bool:
        """Derived once from the attested country at construction; read-only."""
        return self._eligible

    def __repr__(self) -> str:
        return (
            "BinanceLiveReadOnlyAdapter("
            f"configured={self.is_configured()}, "
            "execution_allowed=False, "
            "advisory_only=True)"
        )

    def __dir__(self) -> list[str]:
        return [name for name in super().__dir__() if name.lower() not in _SENSITIVE_ATTRS]

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_secret and self.base_url)

    def credential_diagnostics(self) -> dict[str, Any]:
        missing: list[str] = []
        if not self._api_key:
            missing.append("BINANCE_API_KEY")
        if not self._api_secret:
            missing.append("BINANCE_API_SECRET")
        if not self.base_url:
            missing.append("BINANCE_BASE_URL")
        return {
            "binance_api_key_present": bool(self._api_key),
            "binance_api_secret_present": bool(self._api_secret),
            "binance_base_url_present": bool(self.base_url),
            "binance_base_url_rejected": self.base_url_rejected,
            "binance_eligible": self.eligible,
            "binance_eligibility_reason": self.eligibility_reason,
            "credential_status": "PRESENT" if self.is_configured() else "MISSING",
            "missing_credentials": missing,
            "redacted": True,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }

    def server_time(self) -> dict[str, Any]:
        raw = self._get("/api/v3/time", signed=False)
        millis = raw.get("serverTime") if isinstance(raw, Mapping) else None
        parsed = _utc_from_millis(millis)
        if parsed is None:
            raise BinanceReadOnlyError("malformed_server_time")
        return {
            "server_time_ms": int(millis),
            "timestamp": parsed.isoformat(),
            "status": "OK",
            "source": SOURCE_BINANCE_LIVE_READ_ONLY,
        }

    def get_account(self) -> dict[str, Any]:
        raw = self._get("/api/v3/account", signed=True)
        if not isinstance(raw, Mapping) or "balances" not in raw:
            raise BinanceReadOnlyError("malformed_account_response")
        balances = self._parse_balances(raw.get("balances"))
        payload: dict[str, Any] = {
            "account_type": str(raw.get("accountType") or "SPOT").upper(),
            "update_time": raw.get("updateTime"),
            "balances": balances,
            "source": SOURCE_BINANCE_LIVE_READ_ONLY,
            "execution_allowed": False,
            "advisory_only": True,
        }
        uid = raw.get("uid")
        if uid not in (None, ""):
            payload["account_id"] = str(uid)
        return payload

    def get_balances(self) -> list[dict[str, Any]]:
        return list(self.get_account().get("balances") or [])

    def account_summary(self) -> dict[str, Any]:
        account = self.get_account()
        return {
            "account_type": account.get("account_type"),
            "account_id": account.get("account_id"),
            "balances": list(account.get("balances") or []),
            "balance_count": len(account.get("balances") or []),
            "source": SOURCE_BINANCE_LIVE_READ_ONLY,
            "open_positions_availability": _UNAVAILABLE,
            "session_pnl_availability": _UNAVAILABLE,
            "maturity_availability": _UNAVAILABLE,
            "market_value_availability": _UNAVAILABLE,
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
        }

    def get_exchange_info(self) -> dict[str, Any]:
        raw = self._get("/api/v3/exchangeInfo", signed=False)
        if not isinstance(raw, Mapping) or not isinstance(raw.get("symbols"), list):
            raise BinanceReadOnlyError("malformed_exchange_info")
        products = []
        for item in raw.get("symbols") or []:
            if not isinstance(item, Mapping):
                continue
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            products.append(
                {
                    "symbol": symbol,
                    "status": str(item.get("status") or _UNAVAILABLE),
                    "base_asset": str(item.get("baseAsset") or _UNAVAILABLE),
                    "quote_asset": str(item.get("quoteAsset") or _UNAVAILABLE),
                    "source": SOURCE_BINANCE_LIVE_READ_ONLY,
                }
            )
        if not products:
            raise BinanceReadOnlyError("malformed_exchange_info")
        return {
            "products": products,
            "product_count": len(products),
            "source": SOURCE_BINANCE_LIVE_READ_ONLY,
        }

    def get_products(self) -> list[dict[str, Any]]:
        return list(self.get_exchange_info().get("products") or [])

    def get_ticker(self, symbol: str | None = None) -> dict[str, Any]:
        inst = str(symbol or self.default_symbol).strip().upper() or DEFAULT_QUOTE_SYMBOL
        raw = self._get("/api/v3/ticker/price", params={"symbol": inst}, signed=False)
        if not isinstance(raw, Mapping) or raw.get("price") in (None, ""):
            raise BinanceReadOnlyError("malformed_ticker_response")
        if not _is_number(raw.get("price")):
            raise BinanceReadOnlyError("malformed_ticker_response")
        return {
            "symbol": str(raw.get("symbol") or inst).upper(),
            "price": float(raw.get("price")),
            "timestamp": self._now().astimezone(timezone.utc).isoformat(),
            "status": "OK",
            "source": SOURCE_BINANCE_LIVE_READ_ONLY,
            "market_value_availability": _UNAVAILABLE,
        }

    def market_data(self, symbol: str | None = None) -> dict[str, Any]:
        return self.get_ticker(symbol)

    def safety_posture(self) -> dict[str, Any]:
        return {
            "execution_allowed": False,
            "live_trading_blocked": True,
            "broker_execution_armed": False,
            "advisory_only": True,
            "open_positions_availability": _UNAVAILABLE,
            "session_pnl_availability": _UNAVAILABLE,
            "maturity_availability": _UNAVAILABLE,
        }

    def _parse_balances(self, raw_balances: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_balances, list):
            raise BinanceReadOnlyError("malformed_account_response")
        rows: list[dict[str, Any]] = []
        for item in raw_balances:
            if not isinstance(item, Mapping):
                continue
            asset = str(item.get("asset") or "").strip().upper()
            if not asset:
                continue
            if "free" not in item:
                continue
            available = _as_number(item.get("free"))
            if available is None:
                continue
            held = None
            held_available = False
            if "locked" in item:
                held = _as_number(item.get("locked"))
                held_available = held is not None
            total = None
            total_provenance = _UNAVAILABLE
            if held_available:
                total = float(available) + float(held)
                total_provenance = "derived_available_plus_held"
            rows.append(
                {
                    "asset": asset,
                    "available_quantity": available,
                    "available_quantity_availability": _AVAILABLE,
                    "held_quantity": held if held_available else None,
                    "held_quantity_availability": _AVAILABLE if held_available else _UNAVAILABLE,
                    "total_quantity": total,
                    "total_quantity_availability": _AVAILABLE if total is not None else _UNAVAILABLE,
                    "total_quantity_provenance": total_provenance,
                    "market_value": None,
                    "market_value_availability": _UNAVAILABLE,
                    "availability": _AVAILABLE,
                    "provenance": SOURCE_BINANCE_LIVE_READ_ONLY,
                }
            )
        return rows

    def _get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        return self._request("GET", path, params=params, signed=signed)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        verb = str(method or "").strip().upper()
        if verb != "GET":
            raise BinanceReadOnlyMethodError("Binance live read-only adapter permits GET only")
        if not self.eligible:
            raise BinanceJurisdictionError(self.eligibility_reason)
        if not self.base_url:
            raise BinanceConfigurationError("binance_base_url_not_allowlisted")
        if signed and not self.is_configured():
            raise BinanceConfigurationError("Binance credentials are missing")

        query = dict(params or {})
        headers = {"Accept": "application/json"}
        if signed:
            query["timestamp"] = int(self._now().timestamp() * 1000)
            encoded = urlencode(query, doseq=True)
            query["signature"] = hmac.new(
                self._api_secret.encode("utf-8"),
                encoded.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            headers["X-MBX-APIKEY"] = self._api_key

        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self._send(verb, url, headers=headers, params=query)
        except BinanceReadOnlyError:
            raise
        except requests.Timeout as exc:
            raise BinanceReadOnlyError(f"timeout: {exc}") from exc
        except requests.ConnectionError as exc:
            raise BinanceReadOnlyError(f"network: {exc}") from exc
        except Exception as exc:
            raise BinanceReadOnlyError(str(exc)[:160]) from exc
        return self._parse_response(response)

    def _send(self, method: str, url: str, *, headers: Mapping[str, str], params: Mapping[str, Any]) -> Any:
        if self._transport is not None:
            return self._transport(method, url, headers=dict(headers), params=dict(params))
        # Never follow redirects: requests strips only Authorization on a cross-host redirect, so
        # X-MBX-APIKEY would be forwarded to the redirect target. Any 3xx is an error (below).
        return requests.get(url, headers=dict(headers), params=dict(params), timeout=20, allow_redirects=False)

    def _parse_response(self, response: Any) -> Any:
        status = getattr(response, "status_code", None)
        if isinstance(status, int) and 300 <= status < 400:
            raise BinanceReadOnlyError(f"redirect_refused:{status}")  # never followed, never parsed
        try:
            payload = response.json() if hasattr(response, "json") else response
        except Exception as exc:
            raise BinanceReadOnlyError(f"malformed_response: {exc}") from exc
        if status in {401, 403}:
            raise BinanceReadOnlyError(f"unauthorized:{status}")
        if isinstance(payload, Mapping):
            code = payload.get("code")
            msg = str(payload.get("msg") or "")
            if status == 429 or code == -1003:
                raise BinanceReadOnlyError("rate_limit")
            if code in {-2014, -2015, -1022} or "api-key" in msg.lower() or "signature" in msg.lower():
                raise BinanceReadOnlyError(f"unauthorized:{msg or code}")
            if status not in (None, 200) or (isinstance(code, int) and code < 0):
                raise BinanceReadOnlyError(f"api_error:{status or code}")
        elif status not in (None, 200):
            raise BinanceReadOnlyError(f"api_error:{status}")
        return payload


def _utc_from_millis(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        millis = float(value)
    except (TypeError, ValueError):
        return None
    if millis != millis or millis <= 0:
        return None
    return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc)


def _as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_number(value: Any) -> bool:
    return _as_number(value) is not None


__all__ = [
    "ALLOWED_BINANCE_REST_HOSTS",
    "BinanceJurisdictionError",
    "DEFAULT_BINANCE_REST_URL",
    "SOURCE_BINANCE_LIVE_READ_ONLY",
    "BinanceConfigurationError",
    "BinanceLiveReadOnlyAdapter",
    "BinanceReadOnlyError",
    "BinanceReadOnlyMethodError",
]
