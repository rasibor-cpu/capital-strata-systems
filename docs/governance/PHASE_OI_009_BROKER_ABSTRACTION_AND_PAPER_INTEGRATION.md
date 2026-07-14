# Phase OI-009 - Broker Abstraction And Paper Integration

Date: 2026-07-14

Branch: `css-unified-consolidation-2026-07-13`

## Purpose

Phase OI-009 adds the canonical broker-neutral abstraction layer for the Options Income Engine. It introduces paper-only provider interfaces for options contracts, option chains, market data, broker capabilities, broker health, provider registration, and simulated order preview.

This phase never creates orders, submits orders, cancels orders, routes execution, calls live broker APIs, changes permissions, modifies live runtime state, or enables live trading.

## Architecture

The implementation is split into additive paper-only modules:

- `backend/options/options_broker_abstraction.py` defines shared paper-safe data records, protocols, validation helpers, and safe posture flags.
- `backend/options/options_contract_provider.py` provides deterministic contract lookup and underlying metadata over canonical option contracts.
- `backend/options/options_chain_provider.py` provides paper option-chain snapshots with expiries, strikes, calls, puts, IV, Greeks, volume, and open interest.
- `backend/options/options_market_data_provider.py` provides read-only quote snapshots, refresh, cache, freshness timestamps, source, status, and quality.
- `backend/options/options_paper_broker.py` composes the paper broker provider and exposes paper quote, contract, chain, account, capability, and order-preview operations.
- `backend/options/options_broker_capabilities.py` reports paper options capabilities and rejects live support.
- `backend/options/options_broker_health.py` reports deterministic broker/provider health.
- `backend/options/options_broker_registry.py` registers paper providers only and prohibits live-provider registration.

## Broker Abstraction

OI-009 uses `CanonicalOptionContract` as the contract boundary. Provider outputs are broker-neutral and include explicit safety flags:

- `paper_only=true`
- `advisory_only=true`
- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`

The abstraction covers option chains, option contracts, quotes, Greeks, expiration calendars, underlying metadata, paper buying power, paper account snapshots, capability discovery, and market status.

## Market Data

The market-data provider supports:

- snapshot
- refresh
- cache reuse
- freshness timestamp
- source
- status
- quality

It is read-only and uses paper/canonical contract data only.

## Paper Broker

The paper broker supports:

- paper quote retrieval
- paper contract lookup
- paper option-chain lookup
- paper buying-power inquiry
- paper account summary
- paper capability reporting
- paper simulated order preview

Order preview never produces an order ID, broker ticket, route, live instruction, or execution authority.

## Capabilities

Paper provider capabilities report support for options, covered calls, cash-secured puts, Greeks, IV, paper mode, market data, order preview, and assignment simulation.

`supports_live_mode` is always false. Attempting to create live-capable options broker capabilities fails closed.

## Broker Health

Broker health tracks:

- availability
- data freshness
- quote latency
- chain latency
- Greeks availability
- IV coverage
- market-data completeness
- health score
- status

Statuses are `ONLINE`, `DEGRADED`, `OFFLINE`, or `UNAVAILABLE`.

## Registry

The registry supports explicit registration of paper options providers. It reports provider name, version, capabilities, status, priority, supported assets, and supported strategies.

No live broker is automatically registered. Unsupported providers, duplicates, live-capable providers, and unsupported strategies fail closed.

## Order Preview

Paper order preview accepts a canonical strategy, paper account, collateral, premium, quantity, option symbol, and optional underlying symbol. It returns estimated collateral, estimated premium, estimated buying-power impact, warnings, reasons, and safe posture flags.

It does not include order IDs, broker tickets, routing fields, execution instructions, or live account mutations.

## Fail-Closed Behavior

OI-009 rejects:

- live broker mode
- missing providers
- missing contracts
- missing chains
- unsupported strategies
- unsupported providers
- duplicate providers
- duplicate contracts
- negative collateral
- negative premium
- negative buying power
- malformed Greeks
- missing IV
- missing mandatory contract fields
- execution-enabled posture

## Relationship To Prior Phases

OI-002 defines covered-call and cash-secured-put strategy summaries.

OI-003 consumes canonical contracts for income opportunity scanning.

OI-004 and OI-005 manage paper lifecycle, health, metrics, and rolling advisory.

OI-006 constructs paper portfolios.

OI-007 provides paper Greeks, risk, and stress governance.

OI-008 exposes dashboard, API, operational, alert, and explainability payloads.

OI-009 provides the paper broker/provider abstraction that can feed those phases without live broker authority.

## Out Of Scope

This phase does not implement live broker options integration, live execution, broker routing, assignment execution, production activation, institutional deployment, live certification, credential handling, runtime database mutation, broker authentication, or permission changes.
