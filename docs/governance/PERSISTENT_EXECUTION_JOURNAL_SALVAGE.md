# Persistent Execution Journal Salvage

Created: 2026-07-14

Working branch: `css-unified-consolidation-2026-07-13`

Baseline before reconstruction: `505545f81342a28f2cf36b7e9d9ab2a0797bf015`

Historical source branch: `phase1-persistence-foundation`

Historical source commit: `bbda834247a7910df561a5db426ac110a7d5c765`

## Historical Source

The historical commit added one file:

- `backend/app/audit/persistent_execution_journal.py`

The historical implementation provided an append-only JSONL journal with:

- UUID record identifiers.
- UTC timestamps.
- asset class, symbol, mode, broker, approval flag, reason, execution ID, dry-run flag, and metadata.
- append-mode file writes.
- best-effort JSONL replay that skipped malformed lines.

No historical retention policy, checksum chain, evidence hash, schema version, formal validation, or current evidence-hashing integration was present.

## Manual Reconstruction Rationale

The historical file was not restored directly because it did not match the current consolidation architecture:

- It used nondeterministic UUIDs.
- It had no journal schema version.
- It printed during append.
- It did not integrate with `dashboard.runtime.evidence_hashing`.
- It did not explicitly keep timestamp and sequence outside the evidence hash.
- It lacked schema validation and a strict malformed-line mode.

The reconstructed journal keeps the valuable append-only audit capability while staying isolated from broker and execution authority.

## Architecture

Implementation file:

- `backend/app/audit/persistent_execution_journal.py`

Test file:

- `tests/dashboard/test_persistent_execution_journal.py`

The journal is a standalone utility. It is not wired into execution routing, broker adapters, live-trading controls, or runtime startup.

## Journal Schema

Each JSONL record includes:

- `journal_version`
- `sequence`
- `timestamp_utc`
- `event_type`
- `strategy_id`
- `asset_class`
- `execution_intent`
- `broker_mode`
- `broker_name`
- `decision`
- `reason`
- `correlation_id`
- `evidence_hash`
- `evidence_hash_id`
- `evidence_algorithm`
- `retention_policy`
- `metadata`

The active journal version is `css.persistent_execution_journal.v1`.

The retention policy is `APPEND_ONLY_NO_AUTOMATIC_RETENTION`.

## Evidence Hashing Integration

The reconstructed journal uses `hash_evidence_payload` from `dashboard.runtime.evidence_hashing`.

The evidence hash is computed from stable execution-intent fields:

- journal version
- event type
- strategy identifier
- asset class
- execution intent
- broker mode
- broker name
- decision
- reason
- correlation ID
- redacted metadata

Timestamp and sequence are intentionally excluded from the evidence hash because they are runtime metadata and would make otherwise identical execution evidence nondeterministic.

If an upstream evidence hash is supplied, the journal preserves it instead of recomputing it.

## Security Model

The module:

- does not import broker adapters.
- does not call broker registries.
- does not import execution routers.
- does not mutate execution decisions.
- does not become a source of trading state.
- does not read credentials, `.env`, PEM files, API keys, runtime databases, or generated artifacts.
- redacts sensitive keys and sensitive string markers before persistence.
- writes only to the explicit path passed by the caller.

## Exclusions

This salvage unit deliberately excludes:

- automatic orchestration integration.
- execution-route integration.
- broker-route integration.
- live-trading controls.
- runtime startup hooks.
- database persistence.
- generated audit artifacts.
- Desktop changes.

## Validation

Validation performed:

```powershell
git diff --check
.\.venv\Scripts\python.exe -m py_compile backend/app/audit/persistent_execution_journal.py tests/dashboard/test_persistent_execution_journal.py
.\.venv\Scripts\python.exe -m pytest tests/dashboard/test_persistent_execution_journal.py -q
.\.venv\Scripts\python.exe -m pytest tests/dashboard/test_evidence_hashing.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_options_lifecycle.py tests/test_futures_lifecycle.py tests/test_asset_lifecycle_integration.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_phase163b3j_broker_state_authority.py -q
```

Results:

- `git diff --check`: passed.
- `py_compile`: passed. The first sandboxed attempt hit the known venv interpreter access-denied condition; the approved rerun passed.
- `tests/dashboard/test_persistent_execution_journal.py -q`: `7 passed in 1.94s`.
- `tests/dashboard/test_evidence_hashing.py -q`: `7 passed in 0.84s`.
- `tests/test_options_lifecycle.py tests/test_futures_lifecycle.py tests/test_asset_lifecycle_integration.py -q`: `13 passed in 5.20s`.
- `tests/test_phase163b3j_broker_state_authority.py -q`: `5 passed in 2.64s`.

Secret scan notes:

- Matches were limited to redaction marker strings in the implementation and a fake `SHOULD_NOT_LEAK` test token used to verify redaction.
- No credentials, `.env`, PEM material, API keys, runtime databases, or generated artifacts were included.

## Rollback Boundary

Rollback is limited to:

- `backend/app/audit/persistent_execution_journal.py`
- `tests/dashboard/test_persistent_execution_journal.py`
- `docs/governance/PERSISTENT_EXECUTION_JOURNAL_SALVAGE.md`
- the corresponding entry in `docs/governance/CSS_CONSOLIDATION_PROGRESS.md`

No broker, execution, runtime, credential, Desktop, or live-trading state should require rollback because none is modified by this salvage unit.
