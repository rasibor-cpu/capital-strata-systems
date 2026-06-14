# CSS Recovery and Restart Runbook

## Purpose

This runbook defines controlled recovery and restart procedures after a stopped, failed, interrupted, or emergency-shutdown CSS paper-trading operation.

This document is documentation-only and does not alter runtime, broker, execution, dashboard, credential, risk, margin, or trading logic.

## Restart Preconditions

Before restart:

1. Confirm the incident or shutdown reason is documented.
2. Confirm branch and HEAD are known.
3. Confirm no live mode was enabled.
4. Confirm live execution is not armed.
5. Confirm no broker order was placed.
6. Confirm credentials and `.env` files were not modified.
7. Confirm logs and evidence from the prior run are preserved.
8. Confirm Robert review if the incident was HIGH or CRITICAL.

## Restart Sequence

1. Open a clean terminal in the repository root.
2. Confirm:

   ```text
   git remote -v
   git branch --show-current
   git rev-parse HEAD
   ```

3. Confirm target branch:

   ```text
   css-evening-consolidation-2026-06-09
   ```

4. Confirm no runtime, broker, credential, execution, dashboard, or risk files are unexpectedly modified.
5. Start in PAPER, PRACTICE, or SIMULATION mode only.
6. Re-run startup, session, legal acceptance, and dashboard health checks.

## Session Validation

Validate:

* New or restored session ID is visible.
* Session state is active only for the controlled run.
* Prior session is closed, paused, or deliberately marked for review.
* Session mode is PAPER/PRACTICE/SIMULATION.
* No live session state is active.

If session state is ambiguous, stop and escalate.

## Database Validation

Validate:

* Database connection initializes.
* Migrations are available.
* Required session schema exists.
* Legal acceptance persistence is reachable.
* PnL/trade evidence storage is reachable where used.

Do not manually edit database records during restart unless a later approved remediation phase requires it.

## Legal Acceptance Validation

1. Confirm legal acceptance service is reachable.
2. Confirm required acceptance versions are current.
3. Confirm legal acceptance result is `ALLOW` before controlled paper operation.
4. If legal acceptance is missing, stale, invalid, or unavailable, fail closed and stop.

## Dashboard Validation

1. Confirm canonical dashboard or approved visibility path is used.
2. Confirm mode clearly reads PAPER, PRACTICE, or SIMULATION.
3. Confirm selected broker state is simulated, none, or approved paper/practice.
4. Confirm dashboard does not place orders.
5. Confirm risk, margin, position, and PnL visibility are coherent.

## Paper-Trading Validation

Before resuming:

* Confirm signals are being generated from approved simulated/paper context.
* Confirm AntiBleedGuard is reachable.
* Confirm MarginTradeGate is reachable.
* Confirm RiskGovernor is reachable.
* Confirm ExecutionGate returns auditable allow/block decisions.
* Confirm paper positions are created only after gate `ALLOW`.
* Confirm PnL lifecycle updates are visible.

## Recovery Evidence To Retain

* Prior incident or shutdown notes.
* Restart git precheck.
* Session validation output.
* Database validation output.
* Legal acceptance validation output.
* Dashboard validation output.
* Paper-trading validation output.
* Final restart decision.

## Restart Decision

| Condition | Decision |
| --- | --- |
| All checks pass | Resume controlled paper operation |
| Legal acceptance blocks | Stop |
| Session state ambiguous | Stop and escalate |
| Live mode appears | Emergency shutdown |
| Broker execution attempted | Emergency shutdown and critical incident |
| Credentials changed or exposed | Stop and security incident |

## Post-Recovery Monitoring

For the first run after restart, increase operator attention to:

* Session status.
* Dashboard mode labels.
* Trade gate decisions.
* Paper position lifecycle.
* PnL integrity.
* Audit log continuity.
