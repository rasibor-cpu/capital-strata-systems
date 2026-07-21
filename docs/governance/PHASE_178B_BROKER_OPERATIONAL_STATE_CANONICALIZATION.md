# Phase 178B — Broker Operational State Canonicalization

**Date:** 2026-07-20
**Tier-1 brokers:** Coinbase, Binance, OANDA, Questrade
**Scope:** Source-only structured operational states; no broker connectivity or execution.

## 1. Exception and state audit

| Broker / layer | Prior behavior | Canonical 178B behavior |
| --- | --- | --- |
| Registry / Binance | `get_adapter()` raised `NotImplementedError` | Returns `BinanceOperationalAdapter`; missing credentials is `CREDENTIALS_REQUIRED` |
| Registry / Questrade | `get_adapter()` raised `NotImplementedError` | Returns `QuestradeOperationalAdapter`; missing configuration is `CONFIGURATION_REQUIRED` |
| Coinbase execution | Live buy/sell raised `NotImplementedError` | Returns `EXECUTION_BLOCKED` result |
| Coinbase read-only legacy methods | Runtime errors for missing SDK/credentials | Canonical consumers use `CoinbaseOperationalAdapter`; `operational_readiness()` is the compatibility boundary |
| Binance | Registry-only skeleton | Structured account, market-data, health, readiness, and capability operations |
| OANDA request boundary | Missing config raised `RuntimeError` | Returns `CONFIGURATION_REQUIRED` plus legacy `ok/error` fields |
| OANDA readiness | Boolean `is_configured()` plus string errors | `OandaOperationalAdapter` supplies structured states; legacy boolean remains derived compatibility evidence |
| Questrade advisory adapter | String status dictionaries and typed `ConfigurationRequiredError` helper | Canonical result fields; `require_configured()` now returns a result |
| Base adapter | Abstract methods raised `NotImplementedError` | Abstract markers no longer define exception behavior |
| LIVE_READ_ONLY | Allowed-action list and booleans only | Every read operation includes a `BrokerOperationResult` |
| Readiness / operational status | Boolean and string inference | Canonical state/result added; deprecated fields derive from it |
| Mission Control / mobile / reports | Raw strings and sparse booleans | Operator state, capability states, action, retryability, freshness, and expected-condition fields |

Broad exception handlers remain only where they protect import, provider parsing, persistence, or unexpected boundary faults. They are not a normal readiness truth source. Unexpected faults convert to `FAILED` with a sanitized correlation ID at canonical boundaries.

## 2. Canonical state definitions

The sole canonical enum is `BrokerOperationalState` in
`backend/app/brokers/operational_state.py`.

Lifecycle states:

- `NOT_INITIALIZED`, `DISABLED`
- `CONFIGURATION_REQUIRED`, `CREDENTIALS_REQUIRED`
- `AUTHENTICATION_REQUIRED`, `AUTHENTICATING`, `AUTHENTICATED`
- `TOKEN_EXPIRED`, `TOKEN_REFRESH_REQUIRED`
- `ACCOUNT_REQUIRED`, `ACCOUNT_UNAVAILABLE`, `ACCOUNT_READY`
- `MARKET_DATA_REQUIRED`, `MARKET_DATA_UNAVAILABLE`, `MARKET_DATA_READY`
- `OPTION_CHAIN_PROVIDER_REQUIRED`, `OPTION_CHAIN_UNAVAILABLE`, `OPTION_CHAIN_READY`
- `HOLDINGS_REQUIRED`, `HOLDINGS_UNAVAILABLE`, `HOLDINGS_READY`
- `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `DEGRADED`
- `READ_ONLY_READY`, `ADVISORY_READY`
- `EXECUTION_BLOCKED`, `FAILED`

Legacy names (`REGISTERED`, `UNCONFIGURED`, `LIVE_READ_ONLY`, `READY`,
`BLOCKED`, `ERROR`) are enum aliases to canonical values, not parallel states.

## 3. Broker operation-result contract

`BrokerOperationResult` contains:

- broker, operation, state, success
- retryable, expected_condition, failure_code
- operator_message, technical_message, recommended_action
- capability, execution_allowed, advisory_allowed
- sanitized data and provenance
- provider_timestamp, received_at, freshness, latency_ms
- correlation_id and deterministic state_hash

All results force `execution_allowed=false`. Secret-looking keys and Bearer
values are redacted before serialization.

## 4. Expected versus unexpected faults

Expected conditions are returned as results and do not require stack traces:

- missing configuration, credentials, authentication, account selection
- expired/refresh-required token
- unsupported capability
- unavailable holdings, market data, or option chains
- provider outage and rate limiting
- execution blocked

Programming errors, corrupt internal state, schema violations, and impossible
transitions are unexpected. `capture_unexpected_fault()` converts them to
`FAILED`, sets `expected_condition=false`, and includes a sanitized correlation
ID. Genuine internal bugs are not relabeled as normal readiness states.

## 5. Capability-specific model

`BrokerCapability` defines:

`ACCOUNT`, `BALANCES`, `HOLDINGS`, `MARKET_DATA`, `HISTORICAL_DATA`,
`LISTED_OPTIONS`, `OPTION_CHAIN`, `FX`, `CRYPTO`, `EQUITIES`, `ETFS`,
`EXECUTION`, `STREAMING`, `REGISTERED_ACCOUNTS`.

Operational readiness and capability support are independent. Coinbase may be
`READ_ONLY_READY` for `CRYPTO` while `OPTION_CHAIN` is
`OPTION_CHAIN_UNAVAILABLE`. Unsupported listed options do not fail the entire
broker.

## 6. Broker mappings

### Coinbase

- No credentials: `CREDENTIALS_REQUIRED`
- No authentication evidence: `AUTHENTICATION_REQUIRED`
- Market-data outage: `MARKET_DATA_UNAVAILABLE` / `PROVIDER_UNAVAILABLE`
- Listed-equity options: `OPTION_CHAIN_UNAVAILABLE`
- Crypto capability remains supported
- Live buy/sell: `EXECUTION_BLOCKED`

### Binance

- No credentials: `CREDENTIALS_REQUIRED`
- Authentication/account/provider/rate-limit states use the canonical contract
- Listed-equity options: `OPTION_CHAIN_UNAVAILABLE`
- Crypto spot role remains supported
- Futures, margin, and execution are not activated

### OANDA

- Missing endpoint: `CONFIGURATION_REQUIRED`
- Missing token: `CREDENTIALS_REQUIRED`
- Missing account: `ACCOUNT_REQUIRED`
- Practice/live mismatch: `CONFIGURATION_REQUIRED` with
  `OANDA_ENVIRONMENT_MISMATCH`
- Listed-equity options: `OPTION_CHAIN_UNAVAILABLE`
- FX capability remains supported; execution authority is unchanged

### Questrade

- Missing OAuth/API-server configuration: `CONFIGURATION_REQUIRED`
- Missing refresh token: `CREDENTIALS_REQUIRED`
- No option-chain connectivity: `OPTION_CHAIN_PROVIDER_REQUIRED`
- Account selection: `ACCOUNT_REQUIRED`
- Holdings/market data/provider/rate-limit states are structured
- Listed-options capability remains true, but readiness requires configuration
- OAuth is not initiated

## 7. State-transition rules

Primary lifecycle:

`NOT_INITIALIZED → CONFIGURATION_REQUIRED → CREDENTIALS_REQUIRED → AUTHENTICATION_REQUIRED → AUTHENTICATING → AUTHENTICATED → ACCOUNT_REQUIRED → ACCOUNT_READY → READ_ONLY_READY`

Token lifecycle:

`AUTHENTICATED → TOKEN_REFRESH_REQUIRED → AUTHENTICATING → AUTHENTICATED`

Recovery:

`READ_ONLY_READY → DEGRADED → PROVIDER_UNAVAILABLE → READ_ONLY_READY`

`validate_transition()` returns `FAILED / INVALID_STATE_TRANSITION` for invalid
transitions. No transition enables execution.

## 8. Readiness and certification

Canonical mapping:

- configuration/credential/auth prerequisites → `NOT_INITIALIZED`
- authenticated/account preparation → `CONFIGURED`
- supported read-only state → `READ_ONLY_READY`
- unexpected fault → `FAILED`

`MICRO_PILOT_READY`, `LIVE_READY`, and execution certification remain false.
Legacy readiness booleans and string reasons are compatibility projections from
the canonical result.

## 9. LIVE_READ_ONLY

The contract now carries structured results for:

- authenticate
- account
- balances
- holdings
- positions
- market data
- products
- health
- readiness

Order submission, modification, cancellation, trade placement, execution
arming, and live-trading enablement remain blocked.

## 10. Mission Control, mobile, API, and reporting

Mission Control broker rows include operational state, capability states,
recommended action, expected-condition flag, retryability, last operation,
latency, freshness, readiness, certification, and execution state.

The mobile broker contract exposes a concise state/action/account/market-data/
option-chain/execution summary and links to Broker Management for detail.

GET-only APIs:

- `/api/brokers/states`
- `/api/brokers/{broker}/status`
- `/api/brokers/{broker}/capabilities`
- `/api/brokers/{broker}/readiness`

Broker and Options Income paginated reports include operational and capability
states. Existing A4, one-page-at-a-time presentation remains unchanged.

## 11. Options Income

The advisory resolver consumes broker operational and option-chain capability
results:

- Questrade unconfigured → `OPTION_CHAIN_PROVIDER_REQUIRED` plus
  `DATA_DEPENDENCY_BLOCKED`
- Coinbase/Binance/OANDA listed-options request →
  `OPTION_CHAIN_UNAVAILABLE`, without global broker failure
- Provider unavailability remains provider-specific and fail-closed

No option chain, collateral, price, or opportunity is fabricated.

## 12. Logging and observability

`operational_observability.py` applies:

- INFO: expected configuration/readiness conditions
- WARNING: degraded, provider unavailable, rate limited, token refresh required
- ERROR: unexpected software faults

Repeated expected states may be deduplicated. Secret values, account numbers,
authorization headers, and raw sensitive payload fields are sanitized.

## 13. Security and backward compatibility

- Operator/report strings are sanitized before serialization
- Credential/token/account-number keys are redacted
- Provider messages are not copied into operator messages
- Capability states are generated by the broker-specific adapter, preventing
  cross-broker capability spoofing
- Legacy booleans, status strings, and failure reasons are marked as
  compatibility fields and derive from canonical states
- The Tier-1 registry remains Coinbase, Binance, OANDA, Questrade; IBKR is not
  reintroduced

## 14. Current source-only Tier-1 states

Without credentials or live evidence:

- Coinbase: `CREDENTIALS_REQUIRED`; crypto supported; option chain unavailable
- Binance: `CREDENTIALS_REQUIRED`; crypto supported; option chain unavailable
- OANDA: `CONFIGURATION_REQUIRED`; FX supported; option chain unavailable
- Questrade: `CONFIGURATION_REQUIRED`; listed-options capability advertised;
  option-chain provider required

Execution state is `EXECUTION_BLOCKED` for all brokers.

## 15. Safety confirmation

- No CSS process restart
- No authentication, token refresh, broker connection, or live data request
- No credential changes or credential values persisted
- No operator-intent or micro-pilot change
- No paper or live execution enabled
- No Health Checker changes
- No staging, commit, push, or runtime evidence generation
