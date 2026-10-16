"""Binance Spot PUBLIC market data: filters, weight budget, sequenced depth stream (issue #129).

Public market-data hosts only (data-api.binance.vision / data-stream.binance.vision): no API key,
no account access, no order path. Every entry point first applies binance_eligibility(): an
unattested operating country or a jurisdiction Binance.com does not serve (CA included) is refused
before any connection is attempted. HTTP 451 stays authoritative (no alternate host, proxy or VPN).

  exchange_filters      exchangeInfo -> tick size, step size, minimum quantity / notional, status
  WeightGuard           X-MBX-USED-WEIGHT-1M budget; 429 / 418 stop requests until the server's
                        Retry-After has passed (418 = IP ban; never retried early)
  DepthBook             diff-depth sequencing per Binance's documented algorithm: events at or
                        before the snapshot are dropped, the first applied event must bridge the
                        snapshot, each later event must start exactly at prev.u + 1; any gap marks
                        the book OUT_OF_SYNC (never repaired by guessing) until a new snapshot
  DepthStream           websocket client: buffer -> snapshot -> apply, resync on gap, reconnect
                        with capped exponential backoff, staleness timeout, bounded reconnects
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Mapping

from backend.signals.candles import CandleError, _requests_session, check_http
from backend.signals.market_data import BINANCE_PUBLIC_BASE, binance_eligibility, normalize_symbol

BINANCE_PUBLIC_STREAM = "wss://data-stream.binance.vision"
WEIGHT_LIMIT_1M = 6000  # Binance Spot REST request-weight limit per IP per minute (re-check exchangeInfo)


def _require_eligible(operating_country: str | None) -> None:
    ok, why = binance_eligibility(operating_country)
    if not ok:
        raise CandleError(why)


# --------------------------------------------------------------------------- REST weight budget
@dataclass
class WeightGuard:
    limit: int = WEIGHT_LIMIT_1M
    budget_fraction: float = 0.8
    clock: Callable[[], float] = time.monotonic
    used: int = 0
    blocked_until: float = 0.0

    def before_request(self) -> None:
        if self.clock() < self.blocked_until:
            raise CandleError("binance_backoff_in_effect")
        if self.used >= self.limit * self.budget_fraction:
            raise CandleError("binance_request_weight_budget_exhausted")

    def after_response(self, resp: Any) -> None:
        headers = getattr(resp, "headers", None) or {}
        try:
            self.used = int(headers.get("X-MBX-USED-WEIGHT-1M", self.used))
        except (TypeError, ValueError):
            pass
        status = int(getattr(resp, "status_code", 200) or 200)
        if status in (418, 429):
            try:
                wait = float(headers.get("Retry-After", 60))
            except (TypeError, ValueError):
                wait = 60.0
            self.blocked_until = self.clock() + max(wait, 1.0)
            raise CandleError("binance_ip_banned" if status == 418 else "binance_rate_limited")

    def get(self, http: Any, url: str, params: Mapping[str, Any]) -> Any:
        self.before_request()
        resp = http.get(url, params=dict(params), timeout=10.0)
        self.after_response(resp)
        check_http(resp)
        return resp


# --------------------------------------------------------------------------- exchange filters
@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float

    @property
    def trading(self) -> bool:
        return self.status == "TRADING"


def exchange_filters(instrument: str, *, operating_country: str | None, http: Any = None,
                     guard: WeightGuard | None = None) -> SymbolFilters:
    _require_eligible(operating_country)
    symbol = normalize_symbol("binance", instrument)
    resp = (guard or WeightGuard()).get(http or _requests_session(), f"{BINANCE_PUBLIC_BASE}/api/v3/exchangeInfo",
                                        {"symbol": symbol})
    try:
        (info,) = [s for s in resp.json()["symbols"] if s.get("symbol") == symbol]
        filters = {f["filterType"]: f for f in info.get("filters", [])}
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        return SymbolFilters(symbol, str(info["status"]), str(info["baseAsset"]), str(info["quoteAsset"]),
                             float(filters["PRICE_FILTER"]["tickSize"]), float(filters["LOT_SIZE"]["stepSize"]),
                             float(filters["LOT_SIZE"]["minQty"]), float(notional.get("minNotional", "nan")))
    except (KeyError, TypeError, ValueError) as exc:
        raise CandleError("binance_exchange_info_invalid") from exc


# --------------------------------------------------------------------------- depth sequencing
IN_SYNC, AWAITING_SNAPSHOT, OUT_OF_SYNC = "IN_SYNC", "AWAITING_SNAPSHOT", "OUT_OF_SYNC"


@dataclass
class DepthBook:
    symbol: str
    state: str = AWAITING_SNAPSHOT
    last_update_id: int = 0
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    event_time_ms: int | None = None
    gaps: int = 0
    _bridged: bool = False

    def load_snapshot(self, snapshot: Mapping[str, Any]) -> None:
        try:
            self.last_update_id = int(snapshot["lastUpdateId"])
            self.bids = {float(p): float(q) for p, q in snapshot["bids"] if float(q) > 0}
            self.asks = {float(p): float(q) for p, q in snapshot["asks"] if float(q) > 0}
        except (KeyError, TypeError, ValueError) as exc:
            raise CandleError("binance_depth_snapshot_invalid") from exc
        self.state, self._bridged = IN_SYNC, False

    def apply(self, event: Mapping[str, Any]) -> bool:
        """Apply one diff-depth event. Returns False when dropped as already covered by the snapshot."""
        if self.state != IN_SYNC:
            raise CandleError(f"binance_depth_{self.state.lower()}")
        try:
            first, last = int(event["U"]), int(event["u"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CandleError("binance_depth_event_invalid") from exc
        if last <= self.last_update_id:
            return False  # older than the book
        expected = self.last_update_id + 1
        if (not self._bridged and not (first <= expected <= last)) or (self._bridged and first != expected):
            self.state, self.gaps = OUT_OF_SYNC, self.gaps + 1
            raise CandleError("binance_depth_sequence_gap")
        for side, book in (("b", self.bids), ("a", self.asks)):
            for p, q in event.get(side, []):
                price, qty = float(p), float(q)
                if qty == 0:
                    book.pop(price, None)
                else:
                    book[price] = qty
        self.last_update_id, self._bridged = last, True
        self.event_time_ms = int(event.get("E") or 0) or self.event_time_ms
        if self.bids and self.asks and max(self.bids) >= min(self.asks):
            self.state, self.gaps = OUT_OF_SYNC, self.gaps + 1
            raise CandleError("binance_depth_crossed_book")
        return True

    def best(self) -> tuple[float, float]:
        if self.state != IN_SYNC or not self.bids or not self.asks:
            raise CandleError("binance_depth_unavailable")
        return max(self.bids), min(self.asks)

    def age_s(self, now: datetime) -> float | None:
        if self.event_time_ms is None:
            return None
        return now.timestamp() - self.event_time_ms / 1000


# --------------------------------------------------------------------------- websocket stream
Connect = Callable[[str], Awaitable[Any]]  # returns an async-iterable connection with .close()


async def _default_connect(url: str):  # pragma: no cover - network
    import websockets
    return await websockets.connect(url, open_timeout=10, ping_interval=20, ping_timeout=20, max_size=2**22)


@dataclass
class DepthStream:
    instrument: str
    operating_country: str | None
    snapshot: Callable[[str], Awaitable[Mapping[str, Any]]]
    connect: Connect = _default_connect
    stale_after_s: float = 10.0
    max_reconnects: int = 5
    base_backoff_s: float = 1.0
    max_backoff_s: float = 30.0
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    log: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_eligible(self.operating_country)  # refused before any connection is attempted
        self.symbol = normalize_symbol("binance", self.instrument)
        self.url = f"{BINANCE_PUBLIC_STREAM}/ws/{self.symbol.lower()}@depth@100ms"
        self.book = DepthBook(self.symbol)

    async def run(self, on_book: Callable[[DepthBook], None], *, max_updates: int | None = None) -> DepthBook:
        updates, reconnects, backoff = 0, 0, self.base_backoff_s
        while True:
            try:
                conn = await self.connect(self.url)
            except Exception as exc:  # connection refused, DNS, TLS ...
                self.log.append({"event": "CONNECT_FAILED", "error": type(exc).__name__})
            else:
                self.log.append({"event": "CONNECTED"})
                try:
                    async for applied in self._session(conn):
                        backoff, reconnects = self.base_backoff_s, 0  # healthy again: budgets reset
                        on_book(self.book)
                        updates += applied
                        if max_updates is not None and updates >= max_updates:
                            return self.book
                except CandleError as exc:
                    self.log.append({"event": "SESSION_ENDED", "reason": str(exc)})
                finally:
                    try:
                        await conn.close()
                    except Exception:
                        pass
            reconnects += 1
            if reconnects > self.max_reconnects:
                self.book.state = OUT_OF_SYNC
                raise CandleError("binance_stream_reconnects_exhausted")
            self.log.append({"event": "RECONNECT", "attempt": reconnects, "backoff_s": backoff})
            await self.sleep(backoff)
            backoff = min(self.max_backoff_s, backoff * 2)

    async def _session(self, conn):
        """Buffer events, load a snapshot, then apply in order; a gap ends the session (resync)."""
        self.book = DepthBook(self.symbol)
        buffered: list[Mapping[str, Any]] = []
        iterator = conn.__aiter__()
        first = await self._next(iterator)
        buffered.append(first)
        self.book.load_snapshot(await self.snapshot(self.symbol))
        for event in buffered:
            if self.book.apply(event):
                yield 1
        while True:
            event = await self._next(iterator)
            if self.book.apply(event):
                yield 1

    async def _next(self, iterator) -> Mapping[str, Any]:
        try:
            raw = await asyncio.wait_for(iterator.__anext__(), timeout=self.stale_after_s)
        except asyncio.TimeoutError as exc:
            raise CandleError("binance_stream_stale") from exc
        except StopAsyncIteration as exc:
            raise CandleError("binance_stream_closed") from exc
        try:
            event = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise CandleError("binance_depth_event_invalid") from exc
        if event.get("s") not in (None, self.symbol):
            raise CandleError("binance_depth_symbol_mismatch")
        return event


def public_snapshot_fetcher(*, operating_country: str | None, http: Any = None, guard: WeightGuard | None = None):
    """REST depth snapshot for DepthStream (public host, weight-guarded, eligibility-checked)."""
    _require_eligible(operating_country)
    http, guard = http or _requests_session(), guard or WeightGuard()

    async def fetch(symbol: str) -> Mapping[str, Any]:
        resp = await asyncio.to_thread(guard.get, http, f"{BINANCE_PUBLIC_BASE}/api/v3/depth",
                                       {"symbol": symbol, "limit": 1000})
        return resp.json()
    return fetch


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
