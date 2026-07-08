# Phase 156D - Broker Market Data Evidence Harmonization

## Purpose

Phase 156D adds a shared read-only market-data evidence provider for broker
validation, connectivity certification, and continuous health monitoring.

The module normalizes market-data proof from broker adapters that expose
different read-only method names. It is certification evidence only. It never
authorizes trading and never changes broker state.

## Validation Sequence

`backend/runtime/broker_market_data_evidence.py` checks adapters in this order:

1. `get_quote()`
2. `get_ticker()`
3. `get_market_data()`
4. `get_product()`
5. `get_pricing()`
6. `get_candles()`

Each successful read is converted into a normalized advisory payload containing:

- `success`
- `broker`
- `instrument`
- `source`
- `timestamp`
- `latency_ms`
- `advisory_only`
- `execution_allowed`
- `live_trading_blocked`
- `broker_execution_armed`

The harmonizer rejects explicit wrong-symbol evidence. Payloads without a symbol
field may still be accepted when the adapter method itself is instrument-scoped,
such as Coinbase candle retrieval.

## Broker Fallbacks

OANDA keeps the existing read-only pricing fallback used by Phase 156A:

`_request_json("GET", "v3/accounts/{account_id}/pricing?instruments={instrument}")`

Coinbase accepts successful `get_candles()` responses as valid market-data
evidence for products such as `BTC-USD` and `ETH-USD`.

## Safety Guarantees

Phase 156D is strictly advisory and read-only.

It never:

- submits orders
- cancels orders
- closes positions
- modifies broker state
- arms execution
- enables live trading
- bypasses execution firewalls
- weakens R7, RBAC, or NO-GO controls

Every normalized payload preserves:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

## Relationship To Existing Phases

Phase 156A uses the harmonizer for single-symbol live broker readiness
validation.

Phase 156B uses the harmonizer for multi-symbol controlled connectivity
certification.

Phase 156C consumes the normalized market-data evidence produced by Phase 156B
when determining freshness and dashboard-safe broker health.

Broker credential diagnostics, broker bootstrap, broker readiness, the live
execution firewall, execution boundary validation, R7 governance, and RBAC remain
authoritative. Phase 156D provides evidence only.

## Server Health Discovery

The harmonizer also includes an advisory server health discovery helper. It
checks configured runtime settings first, then known default health endpoints.
It never restarts services, binds ports, changes configuration, or alters server
state.

## Certification Boundary

Phase 156D can improve confidence that read-only market data is available. It
does not certify execution authority and must not be treated as permission to
perform live trading.
