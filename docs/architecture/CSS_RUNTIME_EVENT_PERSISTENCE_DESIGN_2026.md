# CSS Runtime Event Persistence Design 2026

Status: Design only  
Scope: Runtime event-bus persistence planning  
Persistence status: Disabled  
Live trading status: Not enabled by this document

## 1. Purpose

CSS now has a canonical in-memory runtime event bus that can normalize events from lifecycle, websocket, alerting, replay, audit, dashboard, mobile, and future integration surfaces. Future persistence is needed so operators can inspect, reconstruct, and certify runtime behavior after process restart, incident review, or production dry-run evaluation.

Runtime event persistence is not the same as the trade lifecycle replay sink. The replay sink records trade lifecycle records for replay and lineage inspection. Runtime event persistence would record selected operational events from the broader runtime bus, including alerts, governance events, websocket-compatible updates, and other non-trade system events.

Runtime event persistence is not the same as the audit ledger. The audit ledger is the authoritative governance and accountability record. Runtime event persistence would be an operational observability layer that can support reconstruction and diagnostics, but it must not replace governance audit records.

Runtime event persistence is not the same as websocket delivery. Websocket delivery is a real-time transport path for active clients. Persistence would be an approved storage path for selected events and must not change, delay, or mutate live runtime delivery behavior.

## 2. Current State

The runtime event bus is currently in-memory only. It supports event publishing, subscription, recent-event inspection, testing clear helpers, JSON-safe serialization, and redaction-safe payload handling.

CSS already includes read-only event inspection and export helpers. Operators can inspect recent in-memory runtime events through the runtime event inspector and read-only API surfaces, subject to retention and export limits.

CSS already defines a runtime event retention/export policy. That policy caps inspection and export limits, requires redaction, and supports JSON-only read-only exports. It does not write runtime event-bus records automatically.

CSS also has a guarded runtime event persistence approval policy. Persistence remains disabled by default. Approval validation is governance-only and never activates storage, queues, or mutation endpoints.

## 3. Future Persistence Architecture

Any future persistence implementation should remain additive and approved through PCNRASS. It must sit behind the existing event bus, retention policy, and persistence approval policy.

### Option A: JSONL Local Event Store

Description: Append approved runtime events to a local JSONL file.

Pros:
- simple to inspect and export
- append-only by default
- compatible with existing replay JSONL patterns
- low dependency footprint

Cons:
- limited indexing
- large-file scanning can become slow
- corruption handling must be explicit
- concurrent writers require careful locking

### Option B: SQLite Local Event Store

Description: Persist approved runtime events into a local SQLite database with indexed columns.

Pros:
- structured indexing by timestamp, subsystem, event type, severity, and correlation id
- better filtering for operator views
- transactional writes
- practical for local desktop and LAN deployments

Cons:
- schema migration discipline is required
- database locking must be tested under runtime load
- export tooling must preserve redaction and governance metadata

### Option C: Append-Only Event Log

Description: Store events in an append-only internal log format with periodic checkpoints.

Pros:
- strong lineage model
- replay-friendly
- clear immutability boundary
- aligns with deterministic reconstruction goals

Cons:
- more implementation complexity
- requires a formal compaction and retention plan
- requires stronger operational tooling before production use

### Option D: Future External Queue or Stream

Description: Publish approved, redacted events to an external event stream.

Pros:
- scalable across processes and deployments
- supports monitoring, analytics, and future sanitized companion-app feeds
- can decouple runtime producers from consumers

Cons:
- substantially higher operational and security risk
- requires credentials and infrastructure governance
- must not be introduced until local persistence is proven
- requires incident response and failure-mode design before use

## 4. Governance Requirements

Runtime event persistence must remain fail-closed. A future persistence request must be denied unless the persistence policy allows it, an operator approval exists, an approval token is present, requested subsystems are approved, requested window limits are valid, redaction is enforced, and audit logging is available.

Required controls:
- operator approval is required
- approval token is required
- only approved subsystems may be persisted
- redaction is required before storage
- audit logging is required for persistence attempts
- retention windows must be capped
- exports must remain JSON-safe and redaction-safe
- unsupported states must fail closed
- persistence failure must not silently weaken governance

No future persistence path may introduce broker calls, execution calls, live-order mutation, credential loading, or direct frontend broker access.

## 5. Data Model

The proposed persisted runtime event record should contain:

- `event_id`: unique event identifier
- `correlation_id`: cross-system correlation identifier
- `event_type`: canonical event type
- `subsystem`: producer or source subsystem
- `severity`: event severity
- `timestamp_utc`: event creation timestamp
- `source_module`: module or service that emitted the event
- `schema_version`: runtime event schema version
- `redaction_status`: redaction marker
- `payload`: redacted JSON-safe event payload
- `persistence_metadata`: storage metadata

Suggested `persistence_metadata` fields:
- `policy_version`
- `approval_request_id`
- `storage_backend`
- `storage_timestamp_utc`
- `retention_window_minutes`
- `export_format`
- `redaction_required`
- `audit_logging_required`

## 6. Safety Rules

Runtime event persistence must never store secrets, broker credentials, raw API tokens, private keys, approval tokens, or unredacted payloads.

Persistence must never place orders, mutate live order state, change broker mode, change engine mode, approve sessions, update RBAC, or alter governance results.

Persistence must never become an alternate execution path. It is an observability and reconstruction layer only.

If redaction status is unknown, storage must be denied. If subsystem approval is unknown, storage must be denied. If the approval window is expired or invalid, storage must be denied.

## 7. Migration Plan

Phase A: Design only. Define architecture, governance, data model, and test plan without enabling persistence.

Phase B: Dry-run persistence simulator. Validate which events would be persisted, where they would go, and why they would pass or fail policy checks. The simulator must not write event-bus records automatically. Initial dry-run simulator support now exists and remains non-persistent.

Phase C: Local append-only storage behind approval. Add a disabled-by-default JSONL or append-only store that requires explicit operator approval and passes PCNRASS.

Phase D: Indexed local store. Add SQLite or equivalent local indexing only after append-only behavior is proven stable.

Phase E: External event stream. Consider external queues only after local persistence, incident response, and sanitization controls are accepted.

## 8. Testing Plan

Required future tests:
- redaction enforcement tests
- malformed payload rejection tests
- retention-window enforcement tests
- approval rejection tests
- missing-token rejection tests
- unsupported-subsystem rejection tests
- export consistency tests
- replay and correlation compatibility tests
- storage backend corruption tests
- restart and recovery tests
- PCNRASS release checks before activation

Tests must prove that persistence cannot activate by accident and that validation-only paths do not write storage records.

## 9. Open Questions

- Should the first approved storage backend be JSONL or SQLite?
- What should the default retention window be for desktop, LAN, and cloud profiles?
- Which subsystems should be approved for the first dry-run simulator?
- How should event indexing be exposed to operators?
- Should the runtime event operator UI include persistence-plan previews?
- How should incident response consume persisted runtime event records?
- What sanitized feed, if any, should be made available to the future CSS companion app?

## 10. Recommendation

Runtime event persistence should remain disabled until:

- the dry-run simulator passes
- the approval workflow is reviewed
- the storage design is accepted
- PCNRASS release check passes
- operator approval is explicit

The recommended next step is to review dry-run simulator output under realistic operator scenarios before selecting a storage backend. Runtime event persistence should remain disabled during this review.
