# CSS Options Execution Adapter – Master Specification
## Phase 1 Sandbox Architecture Lock

### Purpose
Defines execution architecture for sandbox options trading in Capital Strata Systems.

This adapter governs:
- simulated options fills
- premium debit accounting
- open option position creation
- expiry lifecycle handling
- realized/unrealized PnL tracking

---

## File Target
backend/app/options/options_execution_adapter.py

---

## Supported Scope (Phase 1)
Strategies:
- Long CALL only
- Long PUT only

Underlyings:
- SPY
- QQQ
- AAPL

---

## Required Core Methods

### 1. open_position()
Inputs:
- symbol
- option_type
- strike
- expiry_days
- contracts
- premium

Action:
- debit premium from cash
- create open position record

---

### 2. mark_to_market()
Inputs:
- live underlying price
- updated premium estimate

Action:
- recompute unrealized PnL

---

### 3. close_position()
Inputs:
- position_id
- exit premium

Action:
- realize PnL
- remove open position
- credit cash

---

### 4. expire_position()
Action:
- auto-close expired contracts
- worthless options expire at zero

---

## Position Record Structure

Each open option must store:

- position_id
- symbol
- option_type
- strike
- expiry_date
- contracts
- entry_premium
- current_premium
- delta
- gamma
- theta
- vega
- unrealized_pnl
- realized_pnl

---

## Sandbox Fill Rules

Fill assumption:
- midpoint premium fill

Slippage model:
- default 2%

Commission model:
- configurable flat per contract

---

## Risk Controls

Must enforce:
- max contracts per trade
- max options capital allocation %
- max simultaneous open option positions

---

## Integration Hook

TradeDecisionOrchestrator future flow:

selector
→ pricing engine
→ greeks engine
→ execution adapter

---

## Non-Regression Rule

This module:
- must not alter existing crypto/fx/futures paths
- options path remains isolated until validated

---

## Merge Condition

May merge into main only after:
1. Laptop validation complete
2. sandbox test cases pass
3. orchestrator integration reviewed

---

## Locked By:
CSS Governance Phase – Options Sandbox Expansion
Date: 2026-04-12
Status: APPROVED ARCHITECTURE LOCK
