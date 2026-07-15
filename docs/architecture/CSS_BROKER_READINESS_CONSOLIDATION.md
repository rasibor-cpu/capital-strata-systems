# CSS Broker Readiness Consolidation

Phase: OP-002

Baseline: `5dc01b76b8d5de6c05bee057524329d5d41194d3`

## Canonical Owner

The canonical broker readiness projection owner is:

`backend.runtime.broker_readiness_consolidation`

The canonical function is:

`build_canonical_broker_readiness(...)`

## Inputs

The projection consumes existing read-only evidence:

- frontend broker section
- canonical broker runtime state
- runtime snapshot broker evidence
- runtime certification snapshot

It does not call broker APIs and does not perform authentication, account, balance, market-data, order, or cancellation operations.

## Consolidated Fields

The projection normalizes:

- broker
- mode
- credential status
- transport status
- authentication status
- account status
- balance status
- buying-power status
- margin status
- market-data status
- product status
- latency
- market-data freshness
- readiness score
- overall status
- failure reason
- warnings
- provenance
- safety flags

## Consumer Integration

`dashboard.runtime.frontend_contract.broker(...)` now exposes:

- `canonical_broker_readiness`
- `broker_readiness`

Both reference the OP-002 canonical projection. This preserves the legacy `broker_readiness` key while preventing a separate dashboard-specific readiness calculation from becoming authoritative.

## Mission Control Relationship

Mission Control continues to consume broker readiness through the frontend/runtime state contract and canonical broker runtime state. Mission Control remains display-only and cannot select credentials, arm brokers, override readiness, or enable live trading.

## Safety Rule

The projection always emits:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`
- `ready_for_execution=false`

`ready_for_read_only_validation` can be true for `GREEN` or `AMBER` readiness, but it never implies execution authority.
