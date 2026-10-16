# Issue #129 — Questrade and Binance: governed market data and read-only accounts

**No live-money orders. Execution stays disabled.** This change adds no order path to either broker. The FINANCE worktree `C:\rasib\source\css-simulation-48h` and its running 48-hour trial are not touched.

## What was already there (reused, not rebuilt)
**Questrade (`backend/brokers/questrade/`)**
- an allowlisted, GET-only `QuestradeReadOnlyClient`, which refuses any other method before dispatch;
- `QuestradeGetOnlyHttpTransport`, HTTPS-only, with no Authorization echo;
- OAuth refresh (`oauth_refresh.py`) and the token lifecycle;
- the DPAPI-encrypted refresh-token store for Windows;
- read-only accounts, balances, positions, activities, quotes, symbol search, market status and option chains, with masked account numbers and sanitised diagnostics.

**Binance**
- public klines and a depth quote (`backend/signals/market_data.py`);
- the signed read-only account adapter (`backend/app/brokers/binance_live_read_only_adapter.py`);
- the jurisdiction gate `binance_eligibility`.

## Added
**Questrade**
- **Allowlist:** read-only paths `/symbols/search`, `/symbols/{id}`, `/markets/candles/{id}` and `/accounts/{id}/orders`. The orders path gives order **history** only, because every non-GET method is refused.
- **`QuestradeAdvisoryAdapter.get_order_history()`:** masked account and normalised fields (id, symbol, symbolId, side, type, state, quantities, average fill price and times). It always returns `execution_allowed=false`.
- **`backend/signals/questrade_market_data.py` `QuestradeCandles`:** Canadian and US listed-equity bars as a pipeline `CandleSeries`.
  - Exact `symbol → symbolId` resolution; an ambiguous or unknown symbol is refused.
  - Currency, listing exchange (venue) and security type are recorded; a missing currency is refused.
  - **Entitlement:** a quote delay of 0 is classified `LIVE`; anything else, or unknown, is `DELAYED` and never upgraded.
  - Daily bars are keyed by trading date.
  - Intraday bars must be aligned to the bar grid, otherwise they are refused.
  - Errors map to `questrade:<CODE>`, for example `ACCESS_TOKEN_REQUIRED`, `AUTHORIZATION_REVOKED`, `RATE_LIMITED` or `PROVIDER_UNAVAILABLE`.
- **`provider_matrix`:** a `questrade_api` row, `BLOCKED` until a refresh-token reference exists.

**Binance (public hosts only, no key) — `backend/signals/binance_market_data.py`**
- **`exchange_filters`:** tick size, step size, minimum quantity and minimum notional, and status, from `exchangeInfo`.
- **`WeightGuard`:**
  - enforces an 80% budget of the 1-minute request weight (`X-MBX-USED-WEIGHT-1M`), resetting once 60 s have passed since the server last reported usage;
  - one guard is shared per process by default, so the budget and any back-off carry across calls (Binance meters per IP);
  - on 429 or 418, blocks requests until `Retry-After` has passed (418 is an IP ban);
  - HTTP 451 remains authoritative.
- **`DepthBook`:** Binance's diff-depth sequencing.
  - Events already covered by the snapshot are dropped.
  - The first applied event must bridge the snapshot, and each later event must start at `prev.u + 1`.
  - A gap or a crossed book marks the book `OUT_OF_SYNC`; it is never repaired by guessing.
- **`DepthStream`:** WebSocket client for `data-stream.binance.vision`.
  - It buffers events, takes a snapshot, then applies events.
  - It resyncs with a fresh snapshot after a gap.
  - It reconnects with capped exponential backoff, applies a staleness timeout and a bounded reconnect budget (reset after a healthy session), and fails closed.
- **Eligibility first:** every entry point applies `binance_eligibility` before any connection is attempted. That means an unattested country or a restricted jurisdiction (**CA**, US, NL, ...) is refused.

## Tests
`tests/test_css129_questrade_binance_readonly.py` (26 tests) are contract tests with fakes; no network is used.

**Questrade**
- candles, provenance and entitlement;
- trading-date keying;
- delayed or unknown entitlement;
- unknown, ambiguous and currencyless symbols;
- 401, 429 and 503 failing closed;
- no request without authorization;
- masked order history with no token leakage;
- `POST`, `PUT`, `DELETE` and `PATCH` blocked, and a non-allowlisted path blocked, with nothing sent.

**Binance**
- jurisdiction refusal before any request (CA, US, empty, invalid);
- exchange filters;
- weight budget and 418 ban back-off;
- 451;
- depth drop, bridge, apply and gap;
- snapshot too old;
- crossed book;
- stream resync after a gap;
- stale feed and reconnect exhaustion.

**Static check:** the new modules contain no order endpoint, signing or write call.

## Verified vs not verified
**Verified:** behaviour against Binance's and Questrade's documented response contracts, using fakes, on Linux and Windows CI.

**Not verified here:** live connectivity, entitlement and permissions. This cloud environment cannot reach either host. FINANCE reported HTTP 200 for Binance public time and candles and for Questrade's login page; that does **not** prove OAuth authorization or trading permissions.

## Human actions and decisions required
1. **Questrade OAuth authorization (owner).** Authorize the CSS app in Questrade's API Centre for **read-only** scopes (account data and market data), then store the refresh token in the DPAPI store on FINANCE. Never commit it or paste it into chat.
2. **Questrade intraday bar alignment (verification).** After authorization, run one read-only candle fetch per interval for one TSX and one US symbol. Confirm the bar start alignment and the quote `delay` (real-time vs delayed entitlement).
3. **Binance jurisdiction (owner and compliance).** `CSS_OPERATING_COUNTRY=CA` is restricted by the existing gate (Binance.com does not serve Canada). This change does **not** relax it. Public market data, authenticated read-only accounts and any testnet stay refused for CA unless a documented legal decision changes the gate. No testnet or demo adapter was built for that reason.
4. **Order support for either broker** needs broker partner permissions and separate CSS production approvals. Execution remains capability-gated off.
