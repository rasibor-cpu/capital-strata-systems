# Runtime Event Normalization Salvage

Date: 2026-07-14

Working branch: `css-unified-consolidation-2026-07-13`

Source branch: `phase1-persistence-foundation`

Historical candidates reviewed:

- `a766c3a` - canonical runtime event bus foundation
- `44ecaea` - runtime event persistence architecture
- `9f74883` - dry-run runtime event persistence simulator

## Historical Source

The historical runtime-event work introduced an in-memory dashboard runtime event
bus, websocket conversion helpers, replay-envelope conversion, retention and
persistence planning, and a dry-run persistence simulator. The historical event
envelope included event identifiers, correlation identifiers, event type,
subsystem, UTC timestamp, severity, source module, redacted payload, schema
version, and redaction status.

The historical persistence design explicitly treated runtime event persistence
as operational observability, not trade lifecycle replay, not the audit ledger,
and not websocket delivery. It recommended append-only or local indexed storage
only after governance approval and redaction controls.

## Reconstruction Rationale

This milestone reconstructs only the canonical normalization layer. It does not
recreate the historical dashboard event bus, websocket adapters, replay
pipeline, persistence simulator, or approval policy. Those older pieces touched
runtime delivery and UI surfaces that are outside this controlled salvage unit.

Manual reconstruction was selected because the current CSS repository already
contains a broad `backend.events` package and a new persistent execution
journal. Replaying the historical implementation would create a parallel
dashboard runtime framework and could accidentally expand runtime behavior.

## Architectural Improvements

The reconstructed layer is additive and read-only:

- immutable dataclass schema;
- explicit schema version;
- deterministic canonical serialization;
- UTC timestamp normalization;
- correlation ID support;
- event category, severity, and source fields;
- redacted payload and metadata handling;
- deterministic evidence hash compatibility;
- journal metadata adapter for future audit/replay use;
- no event-bus subscription, broker routing, order routing, or live execution
  integration.

## Schema Definition

Schema version: `css.runtime_event.normalized.v1`

Required fields:

- `schema_version`
- `event_id`
- `event_type`
- `event_category`
- `event_severity`
- `event_source`
- `timestamp_utc`
- `correlation_id`
- `payload`
- `metadata`
- `evidence_hash`
- `evidence_hash_id`
- `evidence_algorithm`
- `redaction_status`

Supported severities:

- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

The event evidence hash is computed from the stable event fields, payload, and
metadata. Runtime timestamp and event ID remain record metadata and are not
inputs to the stable evidence payload.

## Security Model

The normalization layer redacts sensitive keys and sensitive marker strings in
payload and metadata. It never reads credential files, `.env` files, PEM files,
runtime databases, or broker configuration. It does not contain broker imports,
execution imports, or live-trading control imports.

## Exclusions

This salvage unit deliberately excludes:

- runtime event persistence activation;
- SQLite or JSONL runtime event stores;
- dashboard runtime event bus rewiring;
- websocket delivery changes;
- replay engine changes;
- broker adapter changes;
- execution routing changes;
- live-trading authority changes;
- Desktop deployment or restart behavior.

## Validation

Target validation for this milestone:

- `git diff --check`
- `git diff --cached --check`
- compile changed Python files
- runtime event normalization tests
- persistent execution journal tests
- evidence hashing tests
- options lifecycle tests
- futures lifecycle tests
- broker state-authority tests

## Rollback Boundary

Rollback is limited to the runtime event normalization module, its focused tests,
and this governance documentation. Since the module is not wired into the event
bus, broker stack, execution path, Desktop launcher, or runtime process, rollback
does not require broker changes, runtime database changes, credential changes, or
live-trading control changes.
