"""Phase 188 — GET-only OANDA transport for controlled read-only certification.

Never submits, cancels, or modifies orders. Never imports OandaAdapter.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

FORBIDDEN_PATH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "/orders",
        "/order",
        "place_order",
        "submit_order",
        "cancel_order",
        "modify_order",
        "/trades/",  # close/modify trade paths blocked for write verbs
    }
)

ALLOWED_METHODS: frozenset[str] = frozenset({"GET", "HEAD"})


@dataclass(frozen=True)
class TransportResult:
    ok: bool
    status_code: int
    payload: Any
    latency_ms: float
    error: str = ""


class OandaReadOnlyHttpTransport:
    """Minimal OANDA v3 GET client. POST/PUT/PATCH/DELETE are hard-denied."""

    ADAPTER_VERSION = "188.1"

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        account_id: str,
        timeout_s: float = 10.0,
        opener: Any | None = None,
    ) -> None:
        self.base_url = str(base_url or "").rstrip("/") + "/"
        self._token = token
        self._account_id = account_id
        self.timeout_s = timeout_s
        self._opener = opener
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"https", "http"}:
            raise ValueError("endpoint must be http(s)")
        self.host = parsed.hostname or ""

    def get_account_summary(self) -> Any:
        return self._get_json(f"v3/accounts/{self._account_id}/summary")

    def get_open_positions(self) -> Any:
        return self._get_json(f"v3/accounts/{self._account_id}/openPositions")

    def get_open_trades(self) -> Any:
        return self._get_json(f"v3/accounts/{self._account_id}/openTrades")

    def get_instruments(self) -> Any:
        return self._get_json(f"v3/accounts/{self._account_id}/instruments")

    def get_pricing(self, instruments: str = "EUR_USD") -> Any:
        return self._get_json(
            f"v3/accounts/{self._account_id}/pricing?instruments={instruments}"
        )

    def heartbeat(self) -> Any:
        # Account summary doubles as authenticated heartbeat for RO cert.
        return {"ok": True, "summary": self.get_account_summary()}

    def get_account_metadata(self) -> Any:
        return self._get_json(f"v3/accounts/{self._account_id}")

    def request(self, method: str, path: str) -> TransportResult:
        method_u = str(method or "").upper()
        if method_u not in ALLOWED_METHODS:
            raise PermissionError(f"Phase 188 forbids HTTP method {method_u}")
        lowered = path.lower()
        # Block order write endpoints even on GET naming collisions for safety.
        if any(frag in lowered for frag in ("/orders", "place_order", "submit_order")):
            if "pricing" not in lowered and "instruments" not in lowered:
                # Allow only account/instrument/pricing GETs; explicit order paths denied.
                if "/orders" in lowered:
                    raise PermissionError("Phase 188 forbids order endpoints")
        return self._request(method_u, path)

    def _get_json(self, path: str) -> Any:
        result = self._request("GET", path)
        if not result.ok:
            raise RuntimeError(result.error or f"http_{result.status_code}")
        return result.payload

    def _request(self, method: str, path: str) -> TransportResult:
        url = urljoin(self.base_url, path.lstrip("/"))
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, headers=headers, method=method)
        started = time.perf_counter()
        try:
            if self._opener is not None:
                resp_ctx = self._opener.open(req, timeout=self.timeout_s)
            else:
                ctx = ssl.create_default_context()
                resp_ctx = urllib.request.urlopen(req, timeout=self.timeout_s, context=ctx)
            with resp_ctx as resp:
                raw = resp.read()
                latency = (time.perf_counter() - started) * 1000.0
                status = int(getattr(resp, "status", 200) or 200)
                payload: Any
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    payload = {"raw": "[non-json]"}
                return TransportResult(True, status, payload, latency)
        except Exception as exc:  # noqa: BLE001 — surface as transport failure
            latency = (time.perf_counter() - started) * 1000.0
            code = 0
            if isinstance(exc, urllib.error.HTTPError):
                code = int(exc.code)
            return TransportResult(False, code, None, latency, error=str(exc)[:200])

    # Hard denials — attribute access raises.
    def place_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Phase 188 read-only transport cannot place_order")

    def submit_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Phase 188 read-only transport cannot submit_order")

    def cancel_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Phase 188 read-only transport cannot cancel_order")

    def modify_order(self, *args: Any, **kwargs: Any) -> None:
        raise PermissionError("Phase 188 read-only transport cannot modify_order")


def build_transport_from_env(env: Mapping[str, Any]) -> OandaReadOnlyHttpTransport | None:
    token = _first(env, ("OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN"))
    account = _first(
        env,
        ("OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID"),
    )
    base = str(env.get("OANDA_BASE_URL", "") or "").strip()
    if not (token and account and base):
        return None
    return OandaReadOnlyHttpTransport(base_url=base, token=token, account_id=account)


def _first(env: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = str(env.get(name, "") or "").strip()
        if value:
            return value
    return ""
