# CSS Phase 153D - Coinbase Live Read-Only Credential Readiness

## Objective

Phase 153D prepares CSS for Coinbase LIVE read-only validation without enabling live trading or submitting broker orders.

## Scope

- Detect Coinbase credential readiness from supported environment/config names.
- Report credential presence as `PRESENT` or `MISSING` only.
- Report exact missing credential groups without printing secret values.
- Accept Coinbase LIVE read-only confirmation only when the operator types `LIVE`.
- Preserve paper fallback when confirmation is missing or invalid.
- Allow read-only Coinbase authentication/account/balance/position/product checks when credentials are present.
- Keep broker execution disabled and Live Micro-Pilot disarmed.
- Reconcile the legacy Coinbase `$1.00` live-order limit with the Phase 152A CAD 20 Live Micro-Pilot Governor.

## Credential Diagnostics

The runtime reports:

- Coinbase key present: YES/NO
- Coinbase private key or key file present: YES/NO
- Missing credential groups
- Authentication reason
- Broker connected/authenticated status
- Execution scope

Secret values are never printed or exposed in dashboard/API payloads.

## Limit Reconciliation

Phase 152A remains the canonical live capital authority:

`PHASE_152A_LIVE_MICRO_PILOT_GOVERNOR`, CAD 20.00

The legacy Coinbase USD limit remains only as:

`LEGACY_SECONDARY_LIMIT`

It is an additional stricter broker-side guard if live execution is separately authorized later. It does not replace, weaken, or confuse the CAD 20 governor.

## Safety Boundary

Phase 153D does not:

- Enable live trading.
- Arm broker execution.
- Arm the Live Micro-Pilot.
- Submit orders.
- Bypass RBAC.
- Bypass Unified Trade Gate.
- Bypass Margin Gate.
- Bypass Capital Governor.
- Weaken AntiBleedGuard.
- Disable kill switches or emergency stops.

Successful Coinbase read-only authentication may provide broker readiness evidence for authentication/health checks. Execution blockers remain until separate operational approval, broker execution arming, and pilot arming occur.

## Startup Steps For Coinbase LIVE Read-Only Validation

1. Run `launch_css.bat`.
2. Authenticate normally.
3. Select global mode `LIVE` and type `LIVE` when prompted.
4. Select broker `2 = COINBASE`.
5. Select broker mode `2 = LIVE / READ-ONLY VALIDATION`.
6. Type exactly `LIVE` for Coinbase read-only confirmation.
7. Keep broker execution `DISABLED`.
8. Keep the Live Micro-Pilot `DISARMED`.
9. Select engine and cycle modes.

Expected safety state:

- Selected Broker: COINBASE
- Broker Mode: live or live-read-only
- Broker Execution: DISABLED
- Can Live Execute: NO
- Execution Scope: LIVE READ-ONLY VALIDATION
- Live Micro-Pilot: DISARMED
- Broker orders: blocked before submission
