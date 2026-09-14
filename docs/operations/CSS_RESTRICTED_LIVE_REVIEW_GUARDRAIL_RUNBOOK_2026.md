# CSS Restricted Live-Review Guardrail Runbook — Phase 45

## Purpose

This runbook converts readiness evidence into a repeatable **human review gate**.
It does not arm trading and it does not grant execution authority.

## Mandatory pre-review checks

All of the following must be true before the system may report
`READY_FOR_HUMAN_REVIEW`:

1. Current operator approval exists, is scoped to `RESTRICTED_LIVE_REVIEW`,
   is signed by ADMIN/SUPER_USER, and has not expired.
2. Broker dry-run certification is PASS.
3. Broker/CSS reconciliation is confirmed.
4. Kill switch is available and testable.
5. Release/PCNRASS check is PASS.
6. Broker readiness is PASS.
7. No unresolved HIGH/CRITICAL incident exists.
8. No credential or token is present in exported evidence.

A failed or missing check means **BLOCKED**.

## Mandatory evidence

Retain:

- approval audit event;
- dry-run certification reference;
- reconciliation reference;
- kill-switch verification reference;
- release-check reference;
- broker-readiness reference;
- branch and commit;
- UTC timestamp;
- reviewer disposition.

## Safety semantics

Even when every check passes:

- `execution_allowed=false`
- `broker_execution_armed=false`
- `live_trading_authorized=false`

The only positive state produced by this phase is
`READY_FOR_HUMAN_REVIEW`.

Any later activation of a live execution path requires a separate, explicit,
approved assignment and cannot be inferred from this runbook.
