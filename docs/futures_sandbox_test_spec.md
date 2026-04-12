# CSS Futures Sandbox Test Harness - Master Specification
## Phase 1 Sandbox Futures Validation Lock

### Purpose

Defines the complete futures sandbox validation framework for CSS before live futures activation.

This specification governs:

- futures simulated trade replay tests
- order execution simulation paths
- pnl correctness verification
- margin stress testing
- liquidation trigger validation
- multi-contract scenario replay testing

---

## Supported Scope (Phase 1)

### Instruments:
- ES
- NQ
- CL

Sandbox only.

No live broker execution.

---

## Core Test Objectives

The sandbox harness must verify:

1. Futures order routing correctness
2. Position open/close accuracy
3. Partial close integrity
4. Realized/unrealized pnl correctness
5. Margin reservation accuracy
6. Risk governor enforcement correctness
7. Forced liquidation trigger behavior

---

## Required Test Classes

### 1. Order Entry Tests

Validate:
- long entry
- short entry
- multi-contract entry
- rejected order path

Example:
BUY ES x2 accepted

---

### 2. Position Lifecycle Tests

Must validate:
- open position creation
- mark-to-market updates
- partial close handling
- full close completion

---

### 3. PnL Validation Tests

Verify:
- tick movement conversion accuracy
- multiplier application correctness
- realized pnl booking accuracy
- unrealized pnl live update accuracy

---

### 4. Margin Stress Tests

Must simulate:
- margin near-limit warning
- margin breach trigger
- insufficient margin rejection

---

### 5. Forced Liquidation Tests

Simulate:
- drawdown breach liquidation
- margin breach liquidation
- liquidation event ledger recording

---

### 6. Risk Governor Enforcement Tests

Verify:
- per-trade contract cap enforcement
- portfolio exposure ceiling enforcement
- symbol concentration block rules

---

## Replay Simulation Modes

Harness must support:

### Mode A:
Historical replay candles

### Mode B:
Synthetic stress scenario replay

### Mode C:
Fast volatility spike simulation

---

## Required Scenario Set

Minimum scenario library:

1. Winning ES trend trade
2. Losing NQ stop-loss trade
3. CL volatile whipsaw scenario
4. Partial close scale-out test
5. Margin breach liquidation test
6. Consecutive loss drawdown stop test

---

## Pass Criteria

A test batch passes only if:

- pnl math error rate = zero
- liquidation triggers behave correctly
- margin calculations reconcile
- no orphan positions remain open
- audit ledger reconciles fully

---

## Failure Conditions

Sandbox test batch fails if:

- pnl mismatch detected
- liquidation not triggered when required
- negative margin balance occurs improperly
- orphan contracts remain unresolved

---

## Dashboard Test Output Requirements

Harness must report:

- tests run
- tests passed
- tests failed
- liquidation events triggered
- margin breaches triggered
- pnl variance anomalies

---

## Required Output Summary Example

FUTURES SANDBOX TEST REPORT:
Passed: 28
Failed: 0
Liquidations: 2
Margin Breaches: 3
PnL Errors: 0

---

## Primary Laptop 1 Implementation Targets

Primary:
- futures_sandbox_test_runner.py

Secondary:
- futures_position_manager.py
- futures_risk_governor.py
- futures_audit_ledger.py
- futures_execution_adapter.py

---

## Governance Status

Architecture locked.
Ready for Laptop 1 implementation.
No production execution path modified.
