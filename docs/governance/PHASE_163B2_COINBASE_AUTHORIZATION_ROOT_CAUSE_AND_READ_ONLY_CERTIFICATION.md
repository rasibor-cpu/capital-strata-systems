# Phase 163B.2 - Coinbase Authorization Root Cause and Live Read-Only Certification

## Purpose

Phase 163B.2 determines whether the remaining Coinbase `HTTP 401 Unauthorized`
blocker originates in CSS, the Coinbase SDK/API, credential material, operator
configuration, or the local Windows environment.

This phase is read-only. It never submits orders, cancels orders, modifies
broker state, arms execution, enables live trading, bypasses R7/RBAC/NO-GO
controls, or weakens the live execution firewall.

## Repository State Reviewed

Latest committed history at review time:

- `1deaa76 Consolidate canonical broker authentication and readiness evidence`
- `3b1fe7d Implement Phase 163 endurance validation and controlled pilot gate`
- `f8a4eb8 Add missing tracked runtime modules for production validation`
- `0ee3852 Implement Phase 162 production pilot and operational acceptance`
- `911f656 Implement Phase 161 institutional operations intelligence`

Working tree contained the prior Phase 163B.1 Coinbase credential-loader changes
plus runtime report artifacts. No commit or push was performed.

## SDK Verification

Runtime SDK evidence:

- Python: `3.14.3`
- `coinbase-advanced-py`: `1.8.4`
- `cryptography`: `48.0.0`
- `PyJWT`: `2.12.1`
- `requests`: `2.34.2`

Relevant SDK 1.8.4 methods verified:

- `RESTClient.get_unix_time(**kwargs)`
- `RESTClient.get_public_products(...)`
- `RESTClient.get_products(...)`
- `RESTClient.get_product(product_id, ...)`
- `RESTClient.get_accounts(...)`
- `RESTClient.get_portfolios(...)`

JWT generation evidence:

- Signing algorithm: `ES256`
- Issuer: `cdp`
- Token lifetime: `120` seconds
- REST URI format: `GET api.coinbase.com/api/v3/brokerage/accounts`
- `kid` header present
- nonce header present
- no JWT or secret was logged

## Canonical Credential Verification

The canonical loader successfully produced Coinbase credential material:

- canonical loader selected: `PASS`
- JSON path present: `PASS`
- key name present: `PASS`
- key name format: `organizations/.../apiKeys/...`
- key name length: `95`
- private key present: `PASS`
- private key length: `226`
- private key is filesystem path: `FALSE`
- PEM framing present: `PASS`
- escaped newline normalization: `PASS`
- CRLF normalization: `PASS`
- EC key parse: `PASS`
- EC curve: `secp256r1`

The prior Phase 163B.1 defect, where a filesystem path could be passed as
`api_secret`, is not present in the current canonical loader output.

## Authorization Trace

Live read-only Coinbase SDK trace using the canonical credential material:

| Step | SDK method | Endpoint | Auth required | HTTP status | Result |
| --- | --- | --- | --- | --- | --- |
| REST client construction | `RESTClient(...)` | n/a | n/a | n/a | PASS |
| Server time | `get_unix_time` | `/api/v3/brokerage/time` | no | 200 | PASS |
| Public products | `get_public_products` | `/api/v3/brokerage/market/products` | no | 200 | PASS |
| Products | `get_products` | `/api/v3/brokerage/products` | no | 200 | PASS |
| BTC-USD product | `get_product` | `/api/v3/brokerage/products/BTC-USD` | no | 200 | PASS |
| Accounts | `get_accounts` | `/api/v3/brokerage/accounts` | yes | 200 | PASS |
| Portfolios | `get_portfolios` | `/api/v3/brokerage/portfolios` | yes | 200 | PASS |

No order, cancel, allocation, transfer, mutation, arming, or execution method was
called.

## Proven Root Cause

The remaining `HTTP 401 Unauthorized` blocker is not reproducible with the
current canonical credential material and SDK 1.8.4 read-only trace.

Two CSS-side issues were found during certification:

1. `CoinbaseLiveReadOnlyAdapter.get_server_time()` did not include SDK 1.8.4's
   `get_unix_time` method in its read-only method discovery order.
2. `diagnose_broker_credentials("coinbase")` checked the raw process environment
   when no explicit `env` mapping was supplied, while the canonical loader could
   successfully load `.env` and Coinbase JSON/PEM material.

These defects could keep CSS readiness in `CLIENT_CREATED`/`AMBER` or
`KEY_MISSING` even when the canonical credential material was usable.

## Remediation Applied

Read-only additive remediation:

- Added `get_unix_time` to Coinbase server-time method discovery.
- Bridged default broker credential diagnostics to the canonical loader when no
  explicit `env` mapping is supplied.
- Preserved explicit `env={}` fail-closed behavior for tests and injected
  environments.

No execution authority code was changed.

## Post-Remediation Certification

Post-remediation CSS live read-only results:

- Phase 156A: `GREEN`
- credentials: `PASS`
- bootstrap: `PASS`
- authentication: `PASS`
- account: `PASS`
- market data: `PASS`
- execution firewall: `PASS`
- execution_allowed: `FALSE`
- live_trading_blocked: `TRUE`
- broker_execution_armed: `FALSE`
- advisory_only: `TRUE`

Phase 156B remained `RED` due to latency thresholds:

- authentication_ms: `2490`
- account_ms: `6327`
- market_data_ms: `3636`
- overall_ms: `28907`
- connectivity_score: `90.0`
- blocker_reasons: none

Phase 156C remained `RED` due to health scoring:

- connectivity_status: `RED`
- market_data_freshness: `stale_quotes`
- firewall: `PASS`
- execution_allowed: `FALSE`
- live_trading_blocked: `TRUE`
- broker_execution_armed: `FALSE`

## Windows Time Validation

Observed Windows time state:

- Windows Time service: `Stopped`
- Start type: `Manual`
- `w32tm /query /status`: failed because the service was not started
- Local time: `2026-07-10T18:41:15.8257400-04:00`
- UTC time: `2026-07-10T22:41:15.8257400Z`
- Time zone: `Eastern Standard Time`

JWT timestamps were internally consistent during local generation, but disabled
Windows time synchronization remains an operational risk for Coinbase JWT auth.

## Coinbase Operator Checklist

If authorization failures recur, verify:

- API key is active and not revoked.
- Key name matches the JSON/private key pair.
- Key belongs to the correct Coinbase organization.
- Key belongs to the correct Coinbase project.
- Advanced Trade API access is enabled.
- Read permissions include accounts, portfolios, and product/market data.
- Any IP allowlist includes this host's outbound public IP.
- Regional/account restrictions do not block Advanced Trade endpoints.
- Key rotation did not leave CSS using stale credential material.
- System clock synchronization is enabled before live read-only validation.

## Safety Guarantees

The Phase 163B.2 remediation preserves:

- R7 execution gates
- RBAC controls
- NO-GO protections
- execution boundary validation
- live execution firewall
- advisory-only broker readiness/certification/health modules
- broker_execution_armed = `FALSE`
- execution_allowed = `FALSE`
- live_trading_blocked = `TRUE`

This phase certifies read-only connectivity evidence only. It never authorizes
live execution.

## Recovery Procedure

1. Keep live execution disarmed.
2. Enable and verify Windows time synchronization.
3. Re-run the read-only Coinbase authorization trace.
4. Re-run Phase 156A, Phase 156B, and Phase 156C.
5. Proceed only when Phase 156A is `GREEN`, Phase 156B is at least `AMBER`, and
   Phase 156C no longer reports stale market data or connectivity RED.

Controlled micro live validation planning remains `NO-GO` while Phase 156B/156C
are RED, even though Coinbase authorization itself now succeeds.
