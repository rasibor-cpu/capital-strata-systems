# Phase 178D — Questrade Secure Read-Only Connectivity

## Status and safety boundary

Phase 178D establishes source-level Questrade OAuth metadata, secure-store,
account-data, market-data, option-chain, readiness, and presentation contracts.
It does not initiate OAuth, read an operator token, call Questrade, select a real
account, restart CSS, or authorize execution.

- Runtime remains `DISABLED`.
- Broker execution remains `EXECUTION_BLOCKED`.
- Micro-pilot remains `DISARMED`.
- Default Questrade state remains `CONFIGURATION_REQUIRED`.
- All network behavior requires an explicitly injected transport and valid
  in-memory token metadata. The production default transport is disabled.

## Existing implementation map

Before 178D, `backend/brokers/questrade/` provided capability declarations,
presence-only environment checks, a non-persistent token interface, and an
adapter that returned structured `CONFIGURATION_REQUIRED` results. Account,
balance, holding, quote, and option-chain methods were placeholders. API-server
validation, account selection, response mapping, retries, and a GET allowlist
did not exist.

The Phase 178B operational adapter and Tier-1 registry remain canonical for
cross-broker states. The Phase 178D adapter supplies Questrade-specific detail
without changing the Tier-1 broker set.

## Secure configuration

`QuestradeSecureConfiguration` stores references only:

- refresh/access token reference;
- secure token-store identifier;
- selected account hash;
- preferred account type;
- API environment;
- callback metadata reference;
- secret-store provider;
- fixed `READ_ONLY` scope.

Sanitized summaries expose presence and validity only. Plaintext credential
files, credential forms, API token output, and OAuth callback activation are not
supported.

## Onboarding sequence

1. Review read-only capabilities and the execution boundary.
2. Configure approved secret-store references.
3. Complete OAuth externally in a separately authorized phase.
4. validate externally supplied token metadata;
5. discover accounts;
6. select one masked account explicitly;
7. validate balances and holdings;
8. validate quotes and option-chain metadata/quotes;
9. run read-only certification;
10. remain execution-blocked.

Canonical onboarding states are `NOT_CONFIGURED`, `CONFIGURATION_REQUIRED`,
`AUTHORIZATION_REQUIRED`, `TOKEN_AVAILABLE`, `TOKEN_REFRESH_REQUIRED`,
`AUTHENTICATING`, `AUTHENTICATED`, `ACCOUNT_SELECTION_REQUIRED`,
`READ_ONLY_VALIDATION_REQUIRED`, `READ_ONLY_READY`, `DEGRADED`, and `FAILED`.
They map to Phase 178B broker operational states at integration boundaries.

## Token lifecycle

`TokenLifecycle` tracks token presence, acquisition/expiry timestamps, API
server metadata, generation, and bounded refresh intent. Token values are
excluded from dataclass representations and all operation results.

`record_external_token_response()` validates metadata but performs no OAuth
request. Recording is disabled unless an explicit caller authorizes an injected
secure store. The in-memory store is test-only. Durable implementations must
provide atomic `replace()` semantics in an approved OS/vault secret store.

Refresh remains an expected structured state. There is no automatic refresh
loop and no retry for invalid authorization.

## API server discovery and HTTP boundary

The API server is taken from validated token-response metadata. Validation
requires:

- HTTPS;
- port 443/default;
- no user information;
- `api[0-9]+.iq.questrade.com`;
- `/v1/` base path;
- no IP literals, localhost, arbitrary hosts, path traversal, or redirects.

`QuestradeReadOnlyClient` permits only GET requests to allowlisted account,
balance, position, activity, market, symbol, quote, and option metadata paths.
Order, cancellation, replacement, exercise, assignment, preference, and any
other write/path request is rejected as `EXECUTION_BLOCKED` before dispatch.

Retries are bounded to three total attempts, use capped backoff and
`Retry-After`, support cancellation, and return structured `RATE_LIMITED`,
`PROVIDER_UNAVAILABLE`, or authentication states. Unexpected transport failures
receive correlation IDs without exception, token, URL, or authorization-header
text.

## Account and strategy contracts

Account discovery returns process-keyed opaque account hashes and masked identifiers,
never full account numbers. Multiple accounts require explicit selection.
Account types include cash, margin, TFSA, RRSP, RESP, and provider-defined
values. Registered status and strategy restrictions are descriptive only;
options, short-option, margin, and cash-secured-put permissions remain
unconfirmed until broker evidence exists.

Balances preserve cash, settled/available cash, equity, market value, buying
power, maintenance excess, currency, timestamp, freshness, and provenance.
Broker buying power is never relabelled as cash.

Positions preserve canonical/provider symbols, security type, quantities,
cost/price/value, currency, unrealized P&L, and option attributes. Missing
quantities are not converted to zero.

## Quotes and option chains

Symbol lookup uses the Phase 178A listed-security normalization contract.
Quotes expose bid, ask, last, midpoint, volume, prior close, timestamp, exchange,
currency, and market status.

Option-chain mapping separates metadata availability from contract-quote
availability. Expirations, strikes, call/put IDs, quotes, open interest, IV,
Greeks origin, multiplier, exercise style, currency, exchange, timestamps, and
freshness remain explicit. Provider and CSS-derived Greeks are never conflated.

## Readiness and certification

Read-only certification checks secure configuration, token health, validated
API server, account discovery/selection, fresh balances/holdings/quotes,
option-chain readiness, account restrictions, GET allowlisting, write blocking,
execution authority false, and micro-pilot disarmed.

Outcomes are configuration/authorization/account-selection required,
data-dependency blocked, partially ready, certified advisory, degraded, or
failed. `LIVE_READY` and execution certification are prohibited.

## Options Income, UI, API, and reporting

The Options Income resolver can use the Questrade adapter as its provider only
when Questrade is selected and no explicit provider is registered. In the
current no-credential state it returns no holdings, collateral, quotes, chains,
or opportunities and remains `DATA_DEPENDENCY_BLOCKED`.

Mission Control exposes a sanitized onboarding panel. Mobile exposes only state,
required action, masked selection state, holdings/chain status, last refresh,
and the Broker Management link. Broker reports include an A4 Questrade
read-only section.

Authenticated GET-only diagnostic routes are available under
`/api/brokers/questrade/diagnostics/{section}`. There are no credential submission, OAuth
callback, token output, account mutation, or order routes.

## Future controlled live validation

A separate approved phase must inject an OS/vault secret store and transport,
authorize OAuth externally, record token metadata, validate the discovered API
server, discover and select a masked account, perform bounded GET-only calls,
and capture sanitized certification evidence. That phase must independently
approve any CSS restart. It must not infer execution authority from successful
read-only validation.
