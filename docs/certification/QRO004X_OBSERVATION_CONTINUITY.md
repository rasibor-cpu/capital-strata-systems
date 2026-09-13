# QRO-004X Observation Continuity

## Status

The observation ledger, idempotent normalized ingestion, snapshot lineage, continuity projection, API route, Mission Control parity, reconciliation lifecycle, and safe evidence export are implemented with replay/mocked data.

Live Questrade remains externally blocked by `HTTP 403`, Cloudflare `error code: 1010`. No live validation is claimed.

## Ledger Design

`ObservationLedger` stores only normalized broker observations with deterministic IDs, payload hashes, masked account identifiers, UTC timestamps, schema version, and snapshot references. Writes replace the complete checksummed ledger atomically. Corrupt or unsupported ledgers fail closed.

`ReconciliationLedger` persists evidence-keyed lifecycle state: `CREATED`, `UNCHANGED`, `RESOLVED`, and `REOPENED`. Stale evidence cannot resolve an existing issue.

## Dedupe and Lineage

Provider entity IDs are preferred; the fallback identity is a deterministic hash of normalized observation type, provider, masked account, entity reference, timestamp, snapshot ID, and normalized payload. Repeated entries return `DUPLICATE_SKIPPED` behavior without changing economic data. Portfolio snapshots carry observation IDs and prior snapshot lineage.

## API and Mission Control

`build_continuity_state` is the shared projection. The read-only `/api/v1/broker-continuity` route and Mission Control payload expose the same source, snapshot status, freshness, ledger count, reconciliation counts, duplicate count, recovery timestamp, and fail-closed flags. Replay and stale data remain explicitly labeled.

## Commercialization Separation

Broker holdings and broker P&L remain separate from CSS attribution and fee entitlement. No observation ledger event creates attribution or execution authority.

## Safety

`execution_allowed=False`, `live_trading_blocked=True`, `broker_execution_armed=False`, and `advisory_only=True` remain invariant. No order, transfer, withdrawal, deposit, funding, or money movement methods were added.
