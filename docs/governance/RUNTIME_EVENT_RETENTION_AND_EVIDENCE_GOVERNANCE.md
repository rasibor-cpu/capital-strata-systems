# Runtime Event Retention And Evidence Governance

Date: 2026-07-14

Status: Governance policy only

Scope: Runtime event retention, export, replay governance, evidence integrity,
archive boundaries, operator approvals, and failure handling.

This policy does not activate runtime event persistence, enable automatic
exports, wire replay logic, modify brokers, modify execution behavior, restart
CSS, deploy CSS, or change live-trading controls.

## Historical Sources Reviewed

The policy consolidates governance concepts from these
`phase1-persistence-foundation` sources:

- `fe43a51` - runtime event retention and export policy
- `e6b0f81` - guarded runtime event persistence approval framework
- `44ecaea` - runtime event persistence architecture
- `293f57e` - runtime event persistence operator checklist
- `d8efba4` - persistence checklist export review surface
- `676950e` - immutable evidence hashing foundation
- `e7918f4` - micro-live pilot evidence bundle manifest
- `7d4877c` - archive naming and retention policy
- `86d5495` - post-pilot evidence archive export package
- `37876df` - immutable archive manifest hashing

## Retention

Runtime event evidence is an operational observability and certification record.
It is not trading state, execution authority, broker state, or a substitute for
the governance audit ledger.

Journal retention policy:

- Persistent execution journal records are append-only and must not be edited in
  place.
- Runtime event records selected for evidence review must preserve their schema
  version, event ID, timestamp, correlation ID, category, source, severity,
  redaction status, and evidence hash metadata.
- Evidence hashes and manifest hashes are integrity metadata only. They do not
  authorize trading, arm execution, approve persistence, or grant replay access.
- Records may be copied into an approved archive bundle, but the copied bundle
  must preserve the original evidence identifiers and chain-of-custody notes.

Archive boundaries:

- Runtime event evidence archive: normalized runtime events, journal references,
  evidence hash records, manifest hashes, export manifests, operator approvals,
  and certification notes.
- Execution journal archive: persistent execution journal entries and any
  runtime event references attached as metadata.
- Certification package: a bounded package for governance review, including
  approval records, export manifests, replay review notes, hash verification
  results, and failure handling notes.
- Runtime databases, broker payload caches, credentials, `.env` files, PEM
  files, generated diagnostics, and temporary runtime reports are outside the
  approved archive boundary unless separately redacted and approved.

Retention periods by artifact type:

| Artifact type | Minimum retention | Notes |
| --- | --- | --- |
| Persistent execution journal | 7 years or governance-defined retention period, whichever is longer | Preserve append-only record order and evidence hash references. |
| Normalized runtime event export | 7 years when used for certification or incident review | Preserve schema version, event ID, correlation ID, and redaction status. |
| Evidence hash record or hash chain | Same period as the evidence it verifies | Preserve hash algorithm, canonical scope, source reference, and generated time. |
| Archive manifest and manifest hash | 7 years or archive retention period, whichever is longer | Required for chain-of-custody and corruption detection. |
| Certification package | 7 years or regulatory/governance requirement, whichever is longer | Include approvals, review decisions, test references, and sign-off notes. |
| Incident record | 7 years and until incident closure plus review period | Extend retention while investigation, remediation, or reconciliation remains open. |
| Operator approval record | Same period as the approved export, replay, or archive | Preserve operator ID/reference, approval time, scope, and reason. |
| Temporary export work files | Until certification package is accepted or rejected | Must be deleted or archived under approval; never retain secrets. |

Operator responsibilities:

- Confirm the requested retention scope before export or archive.
- Confirm redaction before any artifact becomes official evidence.
- Preserve chain-of-custody notes for each official artifact.
- Record exceptions, missing records, hash mismatches, and replay mismatches.
- Escalate unresolved integrity failures before certification sign-off.
- Confirm that archive activity does not activate runtime persistence or modify
  execution behavior.

## Export

Approved export formats:

- JSONL for ordered event streams and append-only journal extracts.
- CSV for tabular operator review when the source data is already redacted.
- Evidence bundle for a bounded directory or package containing approved
  artifacts, manifests, hashes, and approvals.
- Certification package for final governance review and sign-off.

Export requirements:

- Export must be explicitly approved by an operator or authorized reviewer.
- Export scope must identify event categories, date/time window, correlation IDs
  when applicable, artifact types, and destination archive boundary.
- Exported data must be redacted before it becomes official evidence.
- Exported artifacts must include schema/version metadata and source references.
- Export manifests must list included files, counts, hash references, missing
  records, redaction status, and approval references.
- Export failures must be recorded and may not be hidden by partial success.

Prohibited export behavior:

- Automatic export without approval.
- Export that includes credentials, API keys, tokens, passwords, PEM contents,
  raw authorization headers, or unredacted secrets.
- Export that mutates runtime state, broker state, order state, execution state,
  authentication state, or live-trading controls.
- Export that claims certification success without evidence hash verification
  and operator sign-off.

## Replay

This policy documents replay governance only. It does not implement replay.

Approval requirements:

- Replay must be requested for a bounded evidence purpose: certification,
  incident review, reconciliation, or governance audit.
- Replay scope must identify event categories, journal references, correlation
  IDs, source archive, expected record count, and reviewer.
- Replay must be approved before use in certification evidence.
- Replay output must be treated as derived evidence and must reference its
  source archive and hash chain.

Read-only replay:

- Replay must be read-only.
- Replay must not publish events to live runtime buses.
- Replay must not write to broker adapters, order stores, execution routers, or
  live-trading controls.
- Replay must not become trading state or the source of current account state.
- Replay must not alter the original journal, normalized event records, or
  evidence hashes.

Prohibited replay uses:

- Placing, amending, cancelling, or simulating live orders in production.
- Granting approvals, bypassing PCNRASS/MAEP controls, or overriding kill
  switches.
- Updating broker state, account state, authentication state, or live mode.
- Filling missing records with fabricated events.
- Treating replay output as proof when source hashes do not verify.

Certification workflow:

- Confirm archive source and chain-of-custody.
- Verify evidence hashes and manifest hashes.
- Run read-only replay against the approved scope.
- Compare replay counts, ordering, correlation IDs, and derived summaries with
  the export manifest.
- Record mismatches, missing records, skipped malformed records, and reviewer
  conclusions.
- Certification may proceed only after unresolved integrity issues are closed or
  explicitly accepted by governance.

## Evidence Chain

Evidence hash usage:

- Evidence hashes verify canonical, redacted evidence payloads.
- Hash metadata must include the algorithm, source type, source reference,
  evidence hash ID, and generated timestamp.
- Hashes are integrity metadata only and do not authorize trading, persistence,
  export, replay, or broker access.
- Runtime timestamps and export timestamps may be record metadata rather than
  hash inputs when the canonical evidence model defines them that way.

Hash verification:

- Recompute the hash from the canonical redacted payload.
- Confirm the algorithm is supported.
- Confirm source reference and evidence hash ID match the manifest.
- Confirm schema versions match the expected policy or migration note.
- Record verification status for each artifact in the certification package.

Chain-of-custody:

- Each official artifact must include creator/reviewer, created time, source,
  branch, commit, tag when applicable, correlation ID or evidence ID, redaction
  status, archive path, and notes.
- Each copied or transformed artifact must preserve a reference to its source
  artifact and hash.
- Manual redaction must be documented as a custody event.

Corruption detection:

- Treat malformed JSONL, non-parseable files, unexpected schema versions,
  missing hashes, duplicate event IDs, unexpected ordering gaps, and manifest
  count mismatches as evidence integrity failures.
- Hash mismatch is a blocking failure until investigated and dispositioned.
- Manifest hash mismatch blocks certification until the source package is
  rebuilt or the discrepancy is documented and accepted.

Missing record handling:

- Missing records must not be fabricated.
- Missing records must be logged with expected source, time range, correlation
  ID, event category, and review status.
- Certification must mark the evidence package incomplete unless governance
  explicitly accepts the missing-record risk.

Evidence integrity checks:

- Verify append-only journal ordering.
- Verify normalized event schema version.
- Verify evidence hash and manifest hash.
- Verify redaction status.
- Verify export count against source count.
- Verify replay count against export count when replay is used.
- Verify all approval records are present.

## Privacy

Credential exclusion:

- Do not export or archive credentials, `.env` contents, PEM files, private
  keys, API keys, broker tokens, passwords, authorization headers, or raw
  credential payloads.
- Do not include runtime credential discovery logs in evidence packages unless
  separately redacted and approved.

PII handling:

- Minimize operator, account, and customer identifiers.
- Prefer operator role/reference over personal identifiers when possible.
- Redact sensitive account identifiers unless required for certified evidence.
- Preserve financial facts, timestamps, statuses, correlation IDs, and evidence
  IDs when safe and necessary for audit.

Redaction policy:

- Redaction must replace sensitive values with `REDACTED`.
- Redaction must not alter financial values, event ordering, event IDs,
  correlation IDs, hash IDs, or certification conclusions.
- Redaction actions must be recorded in chain-of-custody notes.
- If redaction status is unknown, the artifact is not eligible for official
  export, replay, or certification.

## Operator Workflow

Export approval:

- Define export purpose, scope, window, categories, correlation IDs, and format.
- Confirm redaction and credential exclusion.
- Generate or identify export manifest.
- Record approval reference before using the export in certification.

Archive approval:

- Confirm archive boundary and destination.
- Confirm manifest, hash chain, and custody notes.
- Confirm no runtime state, generated diagnostics, credentials, or unapproved
  broker payloads are included.
- Record archive approval and reviewer.

Replay approval:

- Confirm replay is read-only and bounded to approved evidence.
- Confirm replay will not publish to live runtime systems or modify source
  records.
- Confirm expected counts, ordering rules, and mismatch handling.
- Record replay approval before certification use.

Certification approval:

- Confirm export, archive, replay, hash verification, and failure handling notes.
- Confirm unresolved failures are closed or formally accepted.
- Confirm no policy violation occurred.
- Record final PASS, REVIEW REQUIRED, or FAIL conclusion.

## Failure Handling

Journal corruption:

- Stop certification use of the affected journal segment.
- Preserve the corrupted file or segment as evidence.
- Identify last verified record and first corrupted line or record.
- Reconstruct only from approved source evidence; do not edit original journal
  records in place.

Hash mismatch:

- Recompute from canonical redacted payload.
- Confirm algorithm, source reference, and schema version.
- Mark package REVIEW REQUIRED or FAIL until resolved.
- Do not certify evidence that cannot be verified or accepted by governance.

Missing evidence:

- Record missing artifact ID, source, correlation ID, expected time range, and
  likely impact.
- Extend retention if investigation remains open.
- Certification cannot pass unless governance accepts the missing-evidence risk.

Incomplete exports:

- Mark export incomplete.
- Do not use partial export as complete evidence.
- Preserve partial export and error notes.
- Re-run export only under a new approval if needed.

Replay mismatch:

- Record expected count, observed count, ordering mismatch, missing correlation
  IDs, and skipped malformed records.
- Treat mismatch as REVIEW REQUIRED or FAIL.
- Do not use replay output to alter source records or runtime state.

Archive failure:

- Preserve failure logs or operator notes if safe and redacted.
- Confirm no partial archive is treated as complete.
- Rebuild only under approval and record the new archive reference.
- Keep failed archive metadata for incident review when relevant.

## Concepts Deliberately Rejected

The following historical concepts were not reintroduced by this milestone:

- Runtime persistence activation.
- Automatic event-bus persistence.
- Dashboard API export endpoints.
- Websocket or replay wiring.
- Dry-run simulator implementation.
- Approval-token validation code.
- SQLite or JSONL event-store implementation.
- Broker, execution, authentication, Desktop, deployment, or live-trading
  changes.

## Validation Boundary

This policy is documentation only. Validation for this milestone is limited to
Git diff checks and confirmation that only governance documents changed.
