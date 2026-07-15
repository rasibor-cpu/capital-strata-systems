# CSS Canonical Runtime Consolidation

Phase: OP-002

Baseline: `5dc01b76b8d5de6c05bee057524329d5d41194d3`

## Canonical Owner

The canonical runtime snapshot owner is:

`backend.runtime.canonical_runtime_snapshot`

The canonical function is:

`build_canonical_runtime_snapshot(...)`

It normalizes existing frontend payloads and runtime artifacts into one read-only snapshot. It never queries brokers, writes artifacts, starts runtime processes, or grants execution authority.

## Compatibility Wrapper

The previous Mission Control normalizer remains available at:

`dashboard.mission_control.runtime_snapshot_normalizer.normalize_runtime_snapshot`

In OP-002 this module delegates to the backend canonical owner. Existing Mission Control imports continue to work while the canonical ownership moves to `backend.runtime`.

## Consolidated Fields

The canonical snapshot includes:

- runtime identity
- session identity
- runtime status
- engine/runtime/cycle mode
- heartbeat status and age
- supervisor counters
- broker readiness projection source fields
- portfolio equity, cash, buying power, exposure, PnL, drawdown
- risk status and gate state
- market state
- decision intelligence visibility
- Options Income visibility
- certification state
- alert summary
- state hash
- provenance
- safety flags

## Duplicate Producers Addressed

| Legacy/duplicate producer | OP-002 treatment |
| --- | --- |
| Mission Control runtime normalizer | Converted to compatibility wrapper. |
| Dashboard frontend payload | Remains a source payload, not a canonical runtime owner. |
| Runtime artifact readers | Remain source readers consumed by the canonical snapshot. |
| Mission Control page projections | Consume canonical runtime state and must not recalculate runtime evidence. |

## Hash Rule

Each canonical runtime snapshot carries `state_hash`, generated from the normalized snapshot excluding the `state_hash` field itself. OP-002 validation recomputes Mission Control runtime snapshot hashes to detect divergence.

## Safety Rule

Every canonical runtime snapshot emits:

- `execution_allowed=false`
- `live_trading_blocked=true`
- `broker_execution_armed=false`
- `advisory_only=true`

Missing or malformed source evidence produces an offline fail-closed snapshot.
