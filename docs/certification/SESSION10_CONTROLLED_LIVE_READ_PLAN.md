# Session-10 Controlled Live-Read Completion Plan

Status: IN_PROGRESS — SOFTWARE READINESS; LIVE AUTH BLOCKED EXTERNAL

## Existing certified foundation
QRO-001 through QRO-004X, durable portfolio continuity, observation ledger, restart recovery, Mission Control continuity, and integrated regression are certified on the preceding integration line.

## Session-10 completion scope
1. Re-certify all read-only broker surfaces on the integrated completion branch.
2. Verify explicit behavior for 403, 429, timeout, malformed payload, 5xx, stale state, corrupt persistence, restart and recovery.
3. Verify account/balance/position/order/execution/activity projections remain read-only and masked.
4. Verify Mission Control and website/mobile API expose the same canonical readiness state.
5. Verify no credential/token material reaches logs, evidence exports, client payloads or persisted observation data.
6. Produce deterministic replay/mock certification now.
7. Mark real-account validation BLOCKED_EXTERNAL until Questrade authentication succeeds.
8. When provider access succeeds, execute a read-only live validation protocol without enabling execution.

## Completion states
- READY_FOR_LIVE_READ_VALIDATION_BLOCKED_EXTERNAL
- LIVE_READ_VALIDATED
- FAILED_CLOSED

No other state may imply live execution authority.
