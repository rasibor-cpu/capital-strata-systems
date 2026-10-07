# Configurable governed micro-pilot — implementation stage 1

The pilot exposure ceiling is an approved **parameter**, not a permanent code ceiling.
The initial requested value may be CAD 20, but later changes require a new
scoped approval, expiry, independent reconciliation and a new audit record.
No automatic escalation occurs. CAD-only until cross-currency handling is certified.

## What this branch implements
- A typed, strictly validated pilot profile.
- Expiry and session identity checks, one-order restriction, no margin.
- Aggregate exposure test covering existing exposure, pending orders,
  proposed notional and estimated fees.
- Fresh broker reconciliation and minimum net-edge preflight.
- Unit tests for configurable amounts and fail-closed behavior.

## What is NOT implemented (release blockers)
- This module is **not connected to the live order submission path**.
- Existing order_limit_config.py retains its current CAD 20 conservative cap.
- AntiBleedGuard's existing minimum trade-size policy has not been relaxed.
- Pilot profile approval signing/storage, atomic consumption and revocation,
  process-restart invalidation, concurrent-order reservations and FX handling
  still require end-to-end design, tests and evidence.
- Brokerage connectivity, R7 coverage, kill-switch verification and legal
  authorization are not certified by unit tests.

**Live trading remains blocked.** Do not override any existing flags on this basis.
