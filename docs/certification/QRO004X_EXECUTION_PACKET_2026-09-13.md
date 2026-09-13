# QRO-004X Execution Packet — Durable Observation Ledger, Idempotent Ingestion, API Continuity & Evidence Export

Prepared: 2026-09-13

Status: READY_FOR_EXECUTION_AFTER_LOCAL_QRO_SYNC

This packet defines the next approved CSS core increment. It is intentionally not implemented against the stale cloud tree.

## Preconditions

QRO-004X may begin only when all of the following are true:

- local QRO branch is pushed and remote SHA equals `feaa42bd036bf1dc945aef09c306b6d28f82530f`;
- phone-work branch has been staged/merged onto a new integration branch;
- protected runtime files are untouched;
- no credential/token material appears in the integration diff;
- focused QRO continuity tests and the existing cloud baseline are green.

Use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ops\verify_qro004x_prerequisites.ps1
```

## Workstream A — Durable Observation Ledger

Create an append-safe broker observation ledger for normalized observations only.

Required observation types:

- ACCOUNT
- BALANCE
- POSITION
- ORDER
- EXECUTION
- ACTIVITY
- RECONCILIATION

Required fields:

- observation_id
- observation_type
- provider
- masked_account_id
- provider_entity_id
- observed_at_utc
- ingested_at_utc
- snapshot_id
- payload_hash
- schema_version

Rules:

- Decimal-safe serialization;
- timezone-aware UTC only;
- no raw Questrade payload persistence;
- no credentials, tokens, authorization headers, or secrets;
- deterministic identity;
- atomic writes;
- explicit schema/version handling;
- corruption must fail closed and become visible state.

## Workstream B — Idempotent Ingestion

Duplicate observations must not create duplicate economic or audit effects.

Required evidence:

- duplicate execution -> `DUPLICATE_SKIPPED=True`;
- duplicate activity -> `DUPLICATE_SKIPPED=True`;
- duplicate reconciliation -> no duplicate lifecycle transition;
- restart + same provider event -> exactly-once normalized effect.

Preferred execution identity:

1. provider execution ID;
2. deterministic fallback over masked account, symbol, side/type, quantity, price, timestamp, and provider reference.

Activity identity follows the same principle.

## Workstream C — Reconciliation Lifecycle

Lifecycle states:

- CREATED
- UNCHANGED
- RESOLVED
- REOPENED

Rules:

- stale/replayed state may not resolve a discrepancy;
- only fresh provider-confirmed state may resolve;
- unresolved discrepancy survives restart;
- reopening preserves lineage.

## Workstream D — Observation-to-Snapshot Lineage

Each canonical snapshot must expose:

- snapshot_id
- observation_ids
- prior_snapshot_id
- source
- as_of_utc
- ingested_at_utc

Persisted/reloaded snapshots must never be labeled LIVE. Use explicit source/status such as REPLAY, STALE, UNAVAILABLE, or CORRUPT.

## Workstream E — API / Mission Control Continuity

API and Mission Control must consume one canonical continuity projection.

Required fields:

- provider
- account_masked
- snapshot_id
- source
- status
- age
- last_successful_sync
- last_observation
- ledger_status
- ledger_count
- freshness
- broker_health
- reconciliation_counts
- reconciliation_severity
- duplicate_count
- recovery_timestamp
- execution_allowed
- live_trading_blocked
- broker_execution_armed
- advisory_only

No duplicated business logic between API and Mission Control.

## Workstream F — Restart / Failure Matrix

Required scenarios:

- clean restart reload;
- duplicate event after restart;
- unresolved reconciliation survives restart;
- corrupt ledger;
- missing ledger;
- fresh provider recovery after restart;
- provider unavailable;
- timeout;
- HTTP 403;
- HTTP 429;
- HTTP 500/502.

Each scenario must classify the result as one or more of:

- FAIL_CLOSED
- IDEMPOTENT
- STATE_EXPLICIT

## Workstream G — Commercialization Regression

QRO-004X must prove:

- duplicate execution/activity cannot create duplicate CSS attribution;
- stale reload cannot create fee entitlement;
- broker P&L remains separate from CSS-attributed performance;
- no provenance -> no CSS-attributed performance;
- no CSS-attributed performance -> no downstream compensation.

## Evidence Outputs

Create:

- `docs/certification/QRO004X_OBSERVATION_CONTINUITY.md`
- `docs/certification/QRO004X_OBSERVATION_CONTINUITY.json`

Evidence must include:

- before/after commit SHAs;
- branch;
- focused test counts;
- existing QRO regression counts;
- full-suite count;
- static safety scan result;
- restart/failure matrix result;
- explicit live-execution safety fields.

## Commit Budget

Maximum two implementation commits:

1. `add durable broker observation ledger`
2. `certify broker continuity API projection`

Use explicit staging only. Do not use `git add .`.

## Immutable Safety Boundary

QRO-004X must not add or enable:

- order submit;
- order cancel;
- order replace;
- transfer;
- withdrawal;
- deposit;
- funding;
- money movement;
- live Questrade authentication attempts;
- real credentials.

Required end-state safety:

- execution_allowed=false
- live_trading_blocked=true
- broker_execution_armed=false
- advisory_only=true
