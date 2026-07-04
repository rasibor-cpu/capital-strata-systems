# CSS Phase 153E - Live Operator Workflow Hardening

## Objective

Phase 153E hardens the operator startup workflow for live broker validation. The goal is deterministic, safe, read-only validation startup that is difficult to misuse.

## Canonical Startup Wizard

The live operator startup wizard is:

1. Authentication
2. Global mode selection
3. Global LIVE confirmation if LIVE is selected
4. Broker selection
5. Broker-specific mode selection
6. Broker LIVE read-only confirmation if live read-only is selected
7. Broker execution arming
8. Engine mode selection
9. Cycle mode selection
10. Startup summary confirmation
11. Start runtime cycle

Invalid input does not advance the wizard. Required confirmations must match exactly, including `LIVE` and `ARM LIVE`.

## Hardened Behaviors

- Broker selection cannot be skipped.
- `NONE / PAPER ONLY` is selected only when the operator explicitly chooses it.
- Broker execution cannot be armed when selected broker is `NONE`.
- Live execution arming requires the second exact confirmation phrase `ARM LIVE`.
- A wrong live arming confirmation leaves execution disabled.
- Paper mode cannot use live broker environment settings such as `OANDA_ENV=live`; the operator receives an actionable return-or-exit prompt.
- A final startup summary must be confirmed before Cycle 1 starts.

## Startup Summary

The final summary displays:

- Global mode
- Selected broker
- Broker mode
- Broker connection/authentication status
- Broker execution status
- Live Micro-Pilot state
- CAD 20 canonical pilot cap
- Engine mode
- Cycle mode
- CAN LIVE EXECUTE
- Execution scope

`Y` starts the runtime cycle. `N` safely stops before runtime startup and instructs the operator to rerun the wizard.

## Broker Validation Display

For selected Coinbase/OANDA validation, dashboard and runtime display expose:

- Credential status
- Authentication status
- Connection status
- Product/price status
- Balance/position status
- Order submission status
- Orders sent count
- Orders blocked count
- Canonical live capital authority: Phase 152A CAD 20 Governor

No secret values are printed or exposed.

## Safety Boundary

Phase 153E does not:

- Enable live trading by default.
- Arm broker execution by default.
- Arm the Live Micro-Pilot by default.
- Submit broker orders.
- Weaken RBAC.
- Weaken Unified Trade Gate.
- Weaken Margin Gate.
- Weaken Capital Governor.
- Weaken AntiBleedGuard.
- Weaken kill switches or emergency stops.
- Fabricate readiness evidence.

Coinbase LIVE read-only validation remains order-blocked by default. Broker execution remains disabled unless every required selection and confirmation passes.
