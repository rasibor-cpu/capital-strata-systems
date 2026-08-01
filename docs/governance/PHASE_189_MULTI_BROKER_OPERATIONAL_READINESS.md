# PHASE 189 — Multi-Broker Operational Readiness, Capability Certification, and Controlled Online Validation

## Explicit safety statement

**NO BROKER AUTHENTICATION. NO RUNTIME. NO LIVE EXECUTION. NO FREEZE SHA.**

Phase 189 creates a broker-agnostic certification framework for every supported
broker and asset class. It does not unlock live trading, does not submit orders,
and does not re-arm authority on restart.

## 1. Package

`backend/app/brokers/multi_broker_readiness/`

Contracts: `BrokerType`, `AssetClass`, `BrokerCapabilityProfile`,
`BrokerReadOnlyCertification`, `BrokerOperationalReadiness`,
`BrokerProviderFingerprint`, `BrokerCertificationEvidence`,
`BrokerCertificationGeneration`, `BrokerCertificationStateMachine`.

Certification scope = **broker + asset class + provider version**.

## 2. Broker capability matrix (declared, not inferred)

| Broker | Equities | ETFs | FX | Crypto | Futures | Options | CFDs | Indices | Commodities | Account | MD | Paper | Live\* | Margin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OANDA | | | Y | | | | Y | Y | Y | Y | Y | Y | Y | Y |
| Coinbase | | | | Y | | | | | | Y | Y | Y | Y | |
| IBKR | Y | Y | Y | | Y | Y | | Y | Y | | | stub | | Y |
| Binance | | | | Y | | | | | | Y | Y | Y | Y | |
| Questrade | Y | Y | | | | Y | | | | Y | Y | | Y | Y |
| PLUGIN | (declared on register) | | | | | | | | | | | | | |

\* `live_trading` is a **declared product capability only**. Phase 189 never grants
`execution_authority`.

## 3. Operational readiness matrix

| Broker | Auth model | Connectivity | Classification |
|---|---|---|---|
| OANDA | bearer env | RO adapter + 187A/188 | **PARTIAL** |
| Coinbase | CDP JWT/PEM | historical live RO PASS | **PARTIAL** |
| IBKR | none (placeholder) | none | **BLOCKED** |
| Binance | API key env | registry only | **NOT_STARTED** |
| Questrade | OAuth refresh refs | injected transport | **PARTIAL** |
| PLUGIN | plugin-declared | none until registered | **NOT_STARTED** |

## 4. Certification framework

Generalizes Phase 187A/188 patterns to all brokers. State machine mirrors RO
certification + revalidation states. Precheck failures force **BLOCKED** without
authentication.

## 5. Authorization TTL

Broker-independent, asset-independent `AuthorizationTTLRegistry`:

- immutable `expires_at`
- automatic expiry
- durable reload after restart **does not re-arm**
- `trading_authorization` always false
- audited issue/expiry events

## 6. RC-004 readiness

Generalized `evaluate_rc004_readiness()`:

- acknowledges paper baseline `b0703f3`
- always `live_trading_authorized=False`
- blockers include `BLK-RC004-SIGNOFF`, `LIVE_TRADING_NOT_AUTHORIZED`
- no order submission / runtime modification

## 7. Controlled online precheck

Checks only: credentials present, endpoint, environment, configuration, provider
compatibility, schema compatibility, capability compatibility.

Any failure → **BLOCKED**. Never authenticates.

## 8. Execution firewall

AST/static verification: package cannot place/edit/cancel orders, arm execution,
or bypass AntiBleed / Margin / RiskGovernor / Phase152A / Live Authority.

## 9. Evidence

Includes broker, asset class, fingerprint, capability profile, generation,
operational readiness, TTL, RC-004, versions, gates, hashes. Secrets redacted.

## 10. Broker onboarding requirements

1. Declare immutable `BrokerCapabilityProfile` (no inference).
2. Register via `register_plugin_capability` or matrix update.
3. Map credential/endpoint env keys for precheck.
4. Pass Phase 189 offline certification + firewall.
5. Future online cert remains a separate phase under RO constraints.

## 11. Future online certification

A later phase may perform controlled online validation per broker+asset using
this framework’s precheck → RO adapter path, still without enabling execution.
