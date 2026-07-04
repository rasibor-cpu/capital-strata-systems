# CSS Phase 153B - Broker Selection Startup Gate

## Objective

Phase 153B separates live broker selection from broker execution arming. CSS can now start in Coinbase LIVE read-only validation mode while broker execution remains disabled.

## Startup Flow

Use `launch_css.bat`, then select:

1. Global broker mode: `2` for LIVE.
2. Startup broker selection: `2` for COINBASE.
3. Broker mode: `2` for LIVE / READ-ONLY VALIDATION.
4. Confirmation: type `LIVE`.
5. Broker execution arming: `1` for DISABLED / READ-ONLY VALIDATION.
6. Continue engine mode and cycle mode selection as usual.

This produces:

- Selected Broker: `COINBASE`
- Broker Mode: `live`
- Broker Execution: `DISABLED`
- Live Micro-Pilot: `DISARMED`
- Broker submission guard: `REJECT_BEFORE_BROKER`

## Allowed In This State

- Coinbase read-only authentication.
- Read-only balance, buying power, positions, quote, and market-data validation.
- Dashboard and certification evidence updates.

## Not Allowed In This State

- Broker order submission.
- Live micro-pilot arming.
- Any bypass of RBAC, Unified Trade Gate, Margin Gate, AntiBleedGuard, or Capital Governor.

## Certification Behavior

Broker authentication and broker health blockers clear only when real read-only evidence shows Coinbase LIVE is connected and authenticated. Execution blockers remain until separate operational approval, broker execution arming, and pilot arming are completed.
