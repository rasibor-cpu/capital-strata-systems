# Phase 178A — Options Income Advisory Data Integration

**Date:** 2026-07-20
**Branch:** `css-unified-consolidation-2026-07-13`
**Scope:** Source-level, read-only, fail-closed advisory data contracts for Options Income.
**Non-goals:** Live trading, paper order execution, micro-pilot arming, credential activation, restart, commit/push.

---

## 1. Source architecture

Options Income advisory inputs flow through provider-neutral adapters into a single resolver, then into the existing runtime snapshot:

```
Provider plugins (optional, registry)
        │
        ▼
Market-data / Option-chain / Holdings adapters
        │
        ▼
options_income_data_resolver ──► OptionsIncomeRuntimeContext
        │                              │
        ▼                              ▼
Collateral authority            options_income_runtime_service
Eligibility / events                   │
        │                              ▼
        └──────── advisory_data ──► MC / mobile / API / report
```

Deployment remains independent of data readiness. An empty provider registry yields `DATA_DEPENDENCY_BLOCKED`, not fabricated opportunities.

---

## 2. Provider responsibilities

| Layer | Module | Role |
| --- | --- | --- |
| Contracts | `options_income_advisory_contracts.py` | Envelopes, provenance, broker capability truth |
| Market data | `options_income_market_data_adapter.py` | Read-only underlying quotes |
| Option chain | `options_income_option_chain_adapter.py` | Read-only chains; rejects demonstration data |
| Holdings | `options_income_holdings_adapter.py` | Sanitized account holdings |
| Collateral | `options_income_collateral_authority.py` | Authority hierarchy |
| Registry | `options_income_provider_registry.py` | Plugin registration (empty by default) |
| Resolver | `options_income_data_resolver.py` | Assembles advisory bundle |
| Cache | `options_income_advisory_cache.py` | Atomic, sanitized, freshness-aware cache helpers |
| Events | `options_income_market_events.py` | Calendar/event disclosure without invented dates |

---

## 3. Broker capability limitations

| Broker | Listed equity options | Role |
| --- | --- | --- |
| Coinbase | **No** | Crypto market/account data |
| Binance | **No** | Crypto market/account data |
| OANDA | **No** | FX market/account data |
| Questrade | **Yes (capability)** | CA/US securities + listed options when authenticated |

IBKR is not registered. Opportunity assignment consults `broker_capability_truth()` before treating a broker as options-compatible.

---

## 4. Questrade readiness

Package: `backend/brokers/questrade/`

- Capability descriptor, endpoint config, rate-limit hints
- Token lifecycle **interface** (not activated)
- Refresh-token store interface (in-memory only)
- Advisory adapter returns `CONFIGURATION_REQUIRED` for accounts, holdings, quotes, chains
- Readiness/health/certification hooks
- Plugin module: `backend.app.brokers.plugins.questrade`

Phase 178B supersedes the original registry placeholder: `broker_registry.get_adapter("questrade")` now returns a source-only structured operational adapter. Advisory data callers may continue to use `QuestradeAdvisoryAdapter`; neither path authenticates or executes.

No credentials required or hard-coded. No authentication initiated in this phase.

---

## 5. Data contracts

Each envelope includes: status, provenance, timestamps, freshness, quality, missing fields, failure reason, `advisory_only=True`, `execution_allowed=False`.

Provenance values: `BROKER`, `MARKET_DATA_PROVIDER`, `OPTION_CHAIN_PROVIDER`, `ACCOUNT_HOLDINGS`, `ACCOUNTING`, `HISTORICAL`, `CACHE`, `CONFIGURATION`, `DERIVED`, `DEMONSTRATION`.

Demonstration/fixture data is never published as live.

---

## 6. Freshness rules (seconds)

| Data type | Limit |
| --- | --- |
| underlying_quote | 120 |
| option_chain_quote | 300 |
| holdings / balances | 900 |
| greeks | 300 |
| volatility_history | 86400 |
| market_calendar | 86400 |

Stale chains surface as `STALE` / certification `STALE_DATA_BLOCKED` and are excluded from “current” opportunity presentation.

---

## 7. Collateral authority

1. Broker-reported collateral / buying power (when reliable)
2. Canonical holdings cash / buying power
3. CSS-derived advisory estimate
4. Unavailable

Simulated smoke/demo fixtures (including historical `10,000` margin fixture markers) are rejected. Every collateral envelope discloses source, currency, basis, timestamp, haircut, and broker-confirmed vs CSS-derived.

---

## 8. Symbol normalization

- Equity / ETF / CA suffixes (`.TO`, `.V`, `.CN`)
- US listings
- OCC option symbols
- Crypto aliases (`BTC_USD`, `BTC-USD`) marked ineligible for listed-equity options

Canonical and provider-native identifiers are retained.

---

## 9. Certification

Extended checks cover provider configuration, quote/chain freshness, holdings/balances, collateral traceability, broker compatibility, Greeks origin, event-data status, and execution blocked.

Outcomes may include: `DATA_DEPENDENCY_BLOCKED`, `PARTIALLY_READY`, `STALE_DATA_BLOCKED`, `ADVISORY_READY`, `CERTIFIED_ADVISORY`, `FAILED`.

`execution_ready` and `live_ready` remain **false**.

---

## 10. Security

- Account IDs sanitized (`***` + last 4)
- Token/secret keys stripped from cache and API holdings payloads
- Provider errors sanitized in Questrade taxonomy
- No credential hard-coding; env presence probed without logging values
- Cache writes atomic; caches not committed
- Cross-broker contamination avoided via separate provider keys and capability truth

---

## 11. Remaining credential / provider dependencies

1. Approved option-chain provider registration (operator approval required for paid vendors)
2. Questrade OAuth refresh token + API server (auth not activated in 178A)
3. Broker-backed holdings sync
4. Optional market calendar / earnings / dividend feeds

Until those exist, readiness remains `DATA_DEPENDENCY_BLOCKED` / `OPTION_CHAIN_PROVIDER_NOT_CONFIGURED`.

---

## 12. Safety confirmation

- Runtime mode unchanged (DISABLED / execution BLOCKED)
- No restarts of `:8090`, `:8765`, launcher, dashboard, supervisor, or brokers
- No authentication, subscription, or live credentialed data requests
- No order path, micro-pilot arming, or operator-intent changes
- No stage/commit/push in this phase
- Tier-1 broker registry and Runtime Resolver left unchanged
- No IBKR reintroduction

---

## 13. Key files

**A. Provider contracts:** `options_income_advisory_contracts.py`, `*_adapter.py`, `*_registry.py`, `*_freshness.py`, `*_symbol_normalization.py`, `*_collateral_authority.py`, `*_eligibility.py`, `*_market_events.py`, `*_advisory_cache.py`, `*_data_resolver.py`
**B. Questrade:** `backend/brokers/questrade/*`, `backend/app/brokers/plugins/questrade.py`
**C. Runtime:** `options_income_runtime_service.py`
**D. API/UI/reporting:** `options_income_api.py`, `options_income_reporting.py`, `dashboard/mission_control/pages/options_income.py`
**E. Tests:** `tests/test_phase178a_options_income_advisory_data.py`
**F. Documentation:** this file
