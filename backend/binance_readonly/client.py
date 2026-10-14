"""GET-only Binance Spot client with a hard endpoint allowlist.

* Only HTTP GET is possible; ``_request`` refuses any other method.
* Only the paths below can be requested; there is no order, cancel, transfer,
  withdrawal, margin, futures or options endpoint anywhere in this module.
* Account endpoints (other than the key-permission report used to establish
  eligibility) are refused until ``confirm_eligibility`` receives a passing decision.
* HTTP 451 (restricted location) raises RestrictedLocationError; nothing retries,
  switches host or routes around it.
* Errors never include the query string (which carries the signature) or the key.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlencode

from backend.binance_readonly.credentials import BinanceCredentials
from backend.binance_readonly.eligibility import EligibilityDecision

LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://api.binance.com"
PUBLIC_PATHS = frozenset({"/api/v3/ping", "/api/v3/time", "/api/v3/exchangeInfo"})
ELIGIBILITY_PATHS = frozenset({"/sapi/v1/account/apiRestrictions", "/sapi/v1/account/status"})
ACCOUNT_READ_PATHS = frozenset({"/api/v3/account", "/api/v3/allOrders", "/api/v3/myTrades"})
SIGNED_PATHS = ELIGIBILITY_PATHS | ACCOUNT_READ_PATHS
ALLOWED_PATHS = PUBLIC_PATHS | SIGNED_PATHS
RECV_WINDOW_MS = 5000
HTTP_TIMEOUT_SECONDS = 10.0
MAX_HISTORY_LIMIT = 100

# transport(url, headers, timeout) -> (status, parsed_json_or_None). GET only.
Transport = Callable[[str, Mapping[str, str], float], tuple[int, Any]]


class BinanceReadOnlyError(RuntimeError):
    pass


class EndpointNotAllowedError(BinanceReadOnlyError):
    pass


class EligibilityNotConfirmedError(BinanceReadOnlyError):
    pass


class RestrictedLocationError(BinanceReadOnlyError):
    pass


class RateLimitedError(BinanceReadOnlyError):
    pass


class BinanceAPIError(BinanceReadOnlyError):
    def __init__(self, path: str, status: int, code: Any, message: str) -> None:
        super().__init__(f"{path}: HTTP {status} code={code} {message}"[:300])
        self.path, self.status, self.code = path, status, code


def default_transport(url: str, headers: Mapping[str, str], timeout: float) -> tuple[int, Any]:
    import requests

    response = requests.get(url, headers=dict(headers), timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return int(response.status_code), body


class BinanceReadOnlyClient:
    def __init__(
        self,
        credentials: Optional[BinanceCredentials] = None,
        *,
        transport: Optional[Transport] = None,
        clock_ms: Optional[Callable[[], int]] = None,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or default_transport
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._time_offset_ms = 0
        self._eligible = False

    # ------------------------------------------------------------------
    @property
    def eligible(self) -> bool:
        return self._eligible

    def confirm_eligibility(self, decision: EligibilityDecision) -> None:
        if not isinstance(decision, EligibilityDecision) or decision.eligible is not True:
            raise EligibilityNotConfirmedError("eligibility decision did not pass")
        self._eligible = True

    def _request(self, method: str, path: str, params: Mapping[str, Any] | None, *, signed: bool) -> Any:
        if method != "GET":
            raise EndpointNotAllowedError(f"method {method} is not permitted (read-only client)")
        if path not in ALLOWED_PATHS:
            raise EndpointNotAllowedError(f"{path} is not on the read-only allowlist")
        if signed != (path in SIGNED_PATHS):
            raise EndpointNotAllowedError(f"{path} signing mode mismatch")
        if path in ACCOUNT_READ_PATHS and not self._eligible:
            raise EligibilityNotConfirmedError(f"{path} refused: eligibility has not been confirmed")

        query: dict[str, Any] = {k: v for k, v in (params or {}).items() if v is not None}
        headers = {"User-Agent": "CSS-BinanceReadOnly/1.0"}
        if signed:
            if self._credentials is None:
                raise BinanceReadOnlyError(f"{path} requires credentials")
            query["recvWindow"] = RECV_WINDOW_MS
            query["timestamp"] = self._clock_ms() + self._time_offset_ms
            encoded = urlencode(query)
            encoded = f"{encoded}&signature={self._credentials.sign(encoded)}"
            headers["X-MBX-APIKEY"] = self._credentials.api_key_header
        else:
            encoded = urlencode(query)
        url = f"{API_BASE_URL}{path}" + (f"?{encoded}" if encoded else "")

        try:
            status, body = self._transport(url, headers, HTTP_TIMEOUT_SECONDS)
        except Exception as exc:
            raise BinanceReadOnlyError(f"{path}: transport error {type(exc).__name__}") from None

        if status == 451:
            raise RestrictedLocationError(
                f"{path}: Binance reports service unavailable from a restricted location (HTTP 451)"
            )
        if status in (418, 429):
            raise RateLimitedError(f"{path}: rate limited (HTTP {status}); stop and retry later")
        if status != 200:
            code = body.get("code") if isinstance(body, dict) else None
            msg = str(body.get("msg", "")) if isinstance(body, dict) else ""
            raise BinanceAPIError(path, status, code, msg)
        return body

    # ------------------------------------------------------------------ public
    def ping(self) -> Any:
        return self._request("GET", "/api/v3/ping", None, signed=False)

    def sync_time(self) -> dict[str, int]:
        local_before = self._clock_ms()
        body = self._request("GET", "/api/v3/time", None, signed=False)
        local_after = self._clock_ms()
        server = int(body["serverTime"])
        self._time_offset_ms = server - (local_before + local_after) // 2
        return {"server_time_ms": server, "offset_ms": self._time_offset_ms}

    def exchange_info(self, symbols: list[str]) -> Any:
        return self._request(
            "GET", "/api/v3/exchangeInfo", {"symbols": "[" + ",".join(f'"{s}"' for s in symbols) + "]"}, signed=False,
        )

    # ------------------------------------------------------------------ eligibility (signed)
    def api_restrictions(self) -> Any:
        return self._request("GET", "/sapi/v1/account/apiRestrictions", None, signed=True)

    def account_status(self) -> Any:
        return self._request("GET", "/sapi/v1/account/status", None, signed=True)

    # ------------------------------------------------------------------ account reads (signed, gated)
    def account(self) -> Any:
        return self._request("GET", "/api/v3/account", {"omitZeroBalances": "true"}, signed=True)

    def all_orders(self, symbol: str, limit: int = 50) -> Any:
        return self._request(
            "GET", "/api/v3/allOrders", {"symbol": symbol, "limit": max(1, min(int(limit), MAX_HISTORY_LIMIT))},
            signed=True,
        )

    def my_trades(self, symbol: str, limit: int = 50) -> Any:
        return self._request(
            "GET", "/api/v3/myTrades", {"symbol": symbol, "limit": max(1, min(int(limit), MAX_HISTORY_LIMIT))},
            signed=True,
        )
