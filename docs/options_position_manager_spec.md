# CSS Options Position Manager – Master Specification
## Phase 1 Sandbox Architecture Lock

### Purpose
Defines the position management architecture for sandbox options trading in Capital Strata Systems.

This module governs:
- open option position storage
- active position updates
- expiry countdown tracking
- unrealized and realized PnL handling
- dashboard position summaries

---

## File Target
backend/app/options/options_position_manager.py

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

### 1. add_position()
Inputs:
- symbol
- option_type
- strike
- expiry_date
- contracts
- entry_premium
- entry_cost

Action:
- create new open position record
- assign unique position_id

---

### 2. update_position_mark()
Inputs:
- position_id
- current_premium
- updated_greeks

Action:
- recompute unrealized PnL
- refresh delta/gamma/theta/vega

---

### 3. close_position()
Inputs:
- position_id
- exit_premium
- exit_cost

Action:
- compute realized PnL
- move record from open to closed state

---

### 4. decrement_expiry()
Action:
- reduce days_to_expiry as time advances
- flag expiring positions

---

### 5. expire_position()
Action:
- close expired option position
- worthless positions expire at zero value

---

## Position Record Structure

Each position must store:

- position_id
- symbol
- option_type
- strike
- expiry_date
- days_to_expiry
- contracts
- entry_premium
- current_premium
- entry_cost
- exit_cost
- delta
- gamma
- theta
- vega
- unrealized_pnl
- realized_pnl
- status

---

## State Categories

Positions must exist in one of:
- OPEN
- CLOSED
- EXPIRED

---

## Dashboard Outputs Required

The position manager must expose:
- total open positions
- total options premium at risk
- total unrealized PnL
- total realized PnL
- nearest expiry countdown
- per-symbol options exposure

---

## Governance Rules

Must enforce:
- no duplicate position_id
- no negative contracts
- no negative days_to_expiry
- no updates to already closed positions
- no silent expiry bypass

---

## Integration Hook

Future flow:

execution adapter
→ options position manager
→ dashboard summary layer

---

## Non-Regression Rule

This module:
- must not alter crypto/fx/futures position tracking
- remains isolated to sandbox options path until validated

---

## Merge Condition

May merge into main only after:
1. documentation review complete
2. Laptop implementation plan approved
3. dashboard summary fields confirmed

---

## Locked By:
CSS Governance Phase – Options Sandbox Expansion
Date: 2026-04-12
Status: APPROVED ARCHITECTURE LOCK
