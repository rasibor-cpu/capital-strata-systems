# CSS Options Sandbox Test Harness – Master Specification
## Phase 1 Sandbox Validation Framework Lock

### Purpose
Defines the testing framework for validating CSS options sandbox trading before production deployment.

This harness validates:

- pricing engine correctness
- greeks engine consistency
- contract selector output
- execution adapter fills
- position manager lifecycle
- expiry lifecycle behavior
- orchestrator integration flow

---

## Scope

Phase 1 supported:

Strategies:
- Long CALL only
- Long PUT only

Underlyings:
- SPY
- QQQ
- AAPL

Sandbox simulation only.

No live broker orders.

---

## Test Harness Objectives

Must simulate:

1. signal generation
2. contract selection
3. option purchase execution
4. position monitoring
5. mark-to-market repricing
6. profit/loss updates
7. expiry closure path

---

## Required Test Scenarios

### Scenario A: Successful CALL Trade
- generate CALL signal
- buy contract
- price rises
- close at profit target

Expected:
positive realized PnL

---

### Scenario B: Successful PUT Trade
- generate PUT signal
- buy PUT
- underlying falls
- close at profit target

Expected:
positive realized PnL

---

### Scenario C: Stop Loss Exit
- open option
- premium declines
- trigger stop loss

Expected:
controlled capped loss

---

### Scenario D: Expiry OTM Worthless
- contract expires worthless

Expected:
premium fully lost
position archived

---

### Scenario E: Expiry ITM Simulated Assignment
- contract expires ITM

Expected:
intrinsic settlement recorded

---

### Scenario F: Theta Decay Stress Test
- flat market
- premium decays daily

Expected:
theta erosion reflected correctly

---

## Test Harness Inputs

Each run accepts:

- symbol
- option type
- strike
- expiry days
- premium paid
- simulated price path

---

## Cycle Engine Rules

Every cycle must execute:

1. update spot price
2. recalc premium
3. recompute greeks
4. refresh unrealized PnL
5. run exit checks
6. run expiry checks

---

## Validation Metrics

Must record:

- win rate
- average gain
- average loss
- max drawdown
- theta loss impact
- expiry closure accuracy

---

## Failure Conditions

Harness fails if:

- negative premium values occur
- greeks invalid
- selector returns illegal strikes
- expired positions remain open
- realized pnl mismatch occurs

---

## Output Reports

Each run generates:

1. trade log
2. position lifecycle log
3. PnL summary
4. expiry audit report

---

## Laptop 1 Next Build Target

Implementation target:

backend/testing/options_sandbox_test_harness.py

After module coding complete.
