# CSS Phase 153F - Operator Startup State Machine

## Objective

Phase 153F replaces the startup prompt chain with an explicit operator startup state machine. This is workflow hardening only; it does not enable live trading or weaken any safety control.

## State Sequence

The startup state machine uses the canonical sequence:

1. `LOGIN`
2. `GLOBAL_MODE`
3. `GLOBAL_MODE_CONFIRMATION`
4. `BROKER_SELECTION`
5. `BROKER_MODE`
6. `BROKER_MODE_CONFIRMATION`
7. `BROKER_EXECUTION`
8. `ENGINE_MODE`
9. `CYCLE_MODE`
10. `STARTUP_SUMMARY`
11. `FINAL_CONFIRMATION`
12. `START_RUNTIME`

Live validation paths traverse the full confirmation sequence. Paper paths preserve the existing paper workflow while remaining explicit, auditable, and order-blocked.

## Input Hardening

- Startup input is owned by the state machine.
- Confirmation prompts flush pending stdin before reading.
- Buffered ENTER presses are ignored.
- Invalid confirmations stay in retry loops.
- The operator-entered value is displayed in validation messages.
- `Q`, `QUIT`, and `EXIT` cancel startup from every screen.
- Startup timeout defaults to 120 seconds and returns to login.
- Runtime cannot start until final confirmation.

## Startup Summary

Before runtime begins, the state machine displays:

- Global Mode
- Broker
- Broker Mode
- Broker Connected
- Broker Authenticated
- Broker Health
- Broker Execution Status
- Execution Scope
- Live Micro-Pilot State
- Canonical CAD 20 Pilot Limit
- Can Live Execute
- Engine Mode
- Cycle Mode
- Readiness Status

The operator must choose:

- `Y` to start runtime
- `N` to restart startup
- `Q` to exit

## Audit

Every startup state transition and input event emits a structured JSONL audit event with advisory-only metadata and `execution_allowed=false`.

## Safety Boundary

Phase 153F does not bypass or weaken:

- Unified Trade Gate
- Margin Gate
- AntiBleedGuard
- Live Micro-Pilot Governor
- RBAC
- Kill Switch
- Live Readiness Certification
- Broker Execution Controls

Live broker execution remains disabled unless all explicit operator selections, RBAC checks, and required confirmations pass. Live orders cannot be sent by default.
