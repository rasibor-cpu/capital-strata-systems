# CSS Startup Runbook

## Purpose

This runbook defines the controlled startup sequence for Capital Strata Systems (CSS) paper-trading operations. It is documentation-only and does not change runtime, broker, execution, dashboard, credential, risk, or margin behavior.

## Operating Boundary

* Approved mode: PAPER or PRACTICE only.
* Balances: simulated or approved paper/practice balances only.
* Live mode: not enabled.
* Live arm: not armed.
* Broker execution: not used for controlled paper certification unless separately approved.
* Robert review is required before any production or live-broker operation.

## Prerequisites

1. Confirm branch:

   ```text
   css-evening-consolidation-2026-06-09
   ```

2. Confirm latest approved HEAD for the planned run.
3. Confirm no unreviewed local runtime, broker, credential, execution, or dashboard changes are present.
4. Confirm `.env` and credential files are not modified during startup.
5. Confirm the operator has the approved role for controlled paper operation.
6. Confirm Phase 103A evidence is available for reference:

   ```text
   certification/runtime/PHASE_103A_CONTROLLED_PAPER_RUN/
   ```

## Authentication Steps

1. Start from a clean terminal in the repository root.
2. Authenticate using the approved CSS authentication path for the selected runtime surface.
3. Do not record passwords, tokens, API keys, or credential values in run logs.
4. Confirm the operator identity, role, and paper-operation authority are visible through logs or runtime evidence.
5. If authentication fails, stop startup and record the failure as an operations incident.

## Session Verification

1. Confirm a runtime session initializes successfully.
2. Confirm the session mode is PAPER, PRACTICE, or SIMULATION.
3. Confirm the session is active.
4. Confirm no live session state is active.
5. Confirm any session restoration message is understood before proceeding.
6. If session initialization fails, do not continue to dashboard or trading workflows.

## Legal Acceptance Verification

1. Verify legal and trading-risk acceptance checks are reachable.
2. Confirm required legal acceptance versions are current for the operator or certification context.
3. If acceptance is missing, expired, corrupt, or unreachable, fail closed and stop controlled operation.
4. Retain evidence of allowed or blocked legal acceptance status without exposing private user data.

## Dashboard Startup

1. Start the canonical dashboard or approved runtime visibility path.
2. Confirm the dashboard identifies PAPER, PRACTICE, or SIMULATION mode.
3. Confirm selected broker is NONE, simulated, or approved paper/practice only.
4. Confirm margin, risk, position, and PnL panels are visible where applicable.
5. Confirm dashboard startup does not place orders or mutate broker state.

## Paper-Mode Confirmation

Before any controlled paper operation:

* Broker Mode must read PAPER, PRACTICE, or SIMULATED.
* Live Mode must read NOT ENABLED or equivalent.
* Live Arm must read NOT ARMED or equivalent.
* Broker execution must not be invoked.
* Simulated or paper balances must be clearly identified.

If any display suggests live mode, live broker execution, unknown credentials, or unclear broker state, stop immediately.

## Health Checks

Minimum startup health checks:

| Check | Expected Result |
| --- | --- |
| Git branch | `css-evening-consolidation-2026-06-09` |
| Runtime startup | Completed |
| Authentication | Operator authenticated or certification context verified |
| Session | Active PAPER/PRACTICE/SIMULATION session |
| Legal acceptance | Current and allowed |
| Dashboard | Operational visibility path available |
| Trade gates | AntiBleedGuard, MarginTradeGate, ExecutionGate, and RiskGovernor reachable |
| Broker mode | Paper/practice/simulated only |
| Credentials | Not changed, not printed |

## Startup Stop Conditions

Stop startup if any of the following occur:

* Branch mismatch.
* Unknown runtime mode.
* Live mode is enabled unexpectedly.
* Live arm is armed unexpectedly.
* Authentication fails.
* Legal acceptance blocks or is unreachable.
* Session initialization fails.
* Dashboard cannot clearly distinguish paper from live state.
* Broker credentials are missing in a way that causes runtime instability.
* Any broker order is attempted.

## Evidence To Retain

* Git precheck output.
* Startup logs.
* Authentication status without secrets.
* Session initialization status.
* Legal acceptance status.
* Dashboard startup output or screenshot.
* Paper-mode confirmation.
* Health-check summary.
