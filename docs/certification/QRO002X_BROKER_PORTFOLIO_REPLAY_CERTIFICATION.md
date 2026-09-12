# QRO-002X Broker Portfolio Replay Certification

## Scope

This increment adds a deterministic, read-only broker boundary for replay and Questrade-shaped data, canonical Decimal portfolio snapshots, reconciliation findings, and Mission Control projection fields.

## Architecture

- `backend/brokers/readonly_domain.py` contains frozen broker and portfolio models plus the read-only protocol.
- `backend/brokers/replay_provider.py` provides deterministic fixture scenarios.
- `backend/brokers/readonly_adapters.py` converts Questrade client payloads at the provider boundary.
- `backend/brokers/readonly_reconciliation.py` reports discrepancies without correcting either source.
- Mission Control exposes snapshot source, freshness, health, P&L summaries, and reconciliation summary fields while retaining fail-closed execution flags.

## Fixture Scenarios

`NORMAL_PORTFOLIO`, `EMPTY_PORTFOLIO`, `MULTI_ACCOUNT`, `STALE_DATA`, `PARTIAL_RESPONSE`, `MALFORMED_PROVIDER_DATA`, `DUPLICATE_ACTIVITY`, `POSITION_MISMATCH`, `PROVIDER_UNAVAILABLE`, and `PROVIDER_RATE_LIMITED` are static and reproducible.

## Portfolio Truth Policy

The broker is authoritative for held quantity, broker cash, broker equity, and buying power. CSS comparison values are reported as findings and are never silently used to overwrite broker holdings.

## Reconciliation Rules

The engine reports account financial mismatches, missing positions, quantity and cost-basis mismatches, stale data, insufficient data, and duplicate activities. Each finding includes category, severity, entity, broker value, CSS value, explanation, and UTC timestamp.

## Mission Control States

`LIVE`, `REPLAY`, `STALE`, and `UNAVAILABLE` remain distinct. Replay is explicitly marked `snapshot_source=REPLAY`; stale data is explicitly marked `STALE`; unavailable data does not become zero-valued data.

## Failure and Recovery

Replay tests cover provider unavailable, rate-limited, malformed, partial, stale, duplicate, mismatch, and recovery scenarios. No scenario arms execution.

## Safety Boundary

No order submission, cancellation, modification, execution, transfer, withdrawal, deposit, funding, or money movement methods were added. Required invariants remain:

- `execution_allowed=False`
- `live_trading_blocked=True`
- `broker_execution_armed=False`
- `advisory_only=True`

## Known Blocker

`LIVE_QUESTRADE_OAUTH=BLOCKED_EXTERNAL_403_CLOUDFLARE_1010`

This certification does not claim real-account validation or live Questrade connectivity.
