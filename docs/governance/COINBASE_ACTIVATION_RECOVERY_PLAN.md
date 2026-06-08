# Coinbase Activation Recovery Plan

## Purpose

This document records the currently understood root cause, recovery strategy, and validation steps for Coinbase activation within Capital Strata Systems (CSS).

---

## Current Situation

The Coinbase account exists and has been funded.

API credentials have been created and loaded.

Previous testing demonstrated that CSS can detect and communicate with Coinbase services.

However, live activation has not consistently progressed to a fully usable trading state.

---

## Working Hypothesis

The most likely root cause is startup sequencing.

Specifically:

1. CSS startup begins.
2. Broker initialization begins.
3. R11 live-capital validation executes.
4. Real balance has not yet been activated.
5. R11 blocks progression.
6. Coinbase activation never completes.

Result:

A valid Coinbase account may appear unavailable even though connectivity and credentials are functioning correctly.

---

## Evidence Supporting This Theory

- Coinbase keys were successfully created.
- Bootstrap communication was previously observed.
- OANDA contamination issues were largely eliminated.
- Static simulated balances were removed.
- Live-mode capital validation remains one of the final gating mechanisms.

---

## Desired Startup Sequence

The preferred order is:

1. Load configuration.
2. Load broker credentials.
3. Connect to Coinbase.
4. Retrieve real account balances.
5. Activate capital source.
6. Validate live balances.
7. Execute R11 live-capital checks.
8. Permit runtime startup.

---

## Validation Requirements

The following must be verified:

### Connectivity

- Coinbase authentication succeeds.
- Account information is retrieved.
- Portfolio balances are visible.

### Capital Source

- Real balance loaded.
- No fallback simulated balance.
- No hard-coded paper balance.

### Governance

- R11 executes after activation.
- Live mode remains blocked if real balance is unavailable.
- Live mode proceeds when balance is confirmed.

---

## Success Criteria

The issue is considered resolved when:

- Coinbase account is detected.
- Real balance is loaded.
- Capital source activates.
- R11 passes.
- CSS enters live-ready state.
- Dashboard reflects actual broker balances.

---

## Laptop Verification Commands

```text
git fetch
git branch --show-current
git rev-parse HEAD
