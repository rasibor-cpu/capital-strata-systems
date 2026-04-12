# CSS Futures Execution Adapter - Master Specification
## Phase 1 Sandbox Futures Execution Governance Lock

### Purpose
Defines futures execution routing architecture for CSS sandbox futures trading.

This specification governs:

- futures order creation
- long/short execution routing
- contract quantity handling
- fill-price simulation logic
- slippage modeling
- commission modeling
- mark-to-market pnl update routing

---

## Supported Scope (Phase 1)

### Supported Contracts:
- ES
- NQ
- CL

### Supported Directions:
- LONG futures
- SHORT futures

Sandbox only.

---

## Execution Adapter Responsibilities

Adapter must support:

### 1. OPEN POSITION EXECUTION
Inputs:
- symbol
- side
- contracts
- entry_price

Output:
- execution_id
- fill_price
- timestamp

---

### 2. CLOSE POSITION EXECUTION
Inputs:
- position_id
- exit_price
- contracts

Output:
- realized pnl
- close timestamp

---

### 3. PARTIAL CLOSE SUPPORT
Must support partial contract reduction.

Example:
5 ES open
close 2 ES
remaining = 3 ES

---

### 4. SLIPPAGE MODEL

Initial sandbox slippage:

ES:
0.25 tick average

NQ:
0.25 tick average

CL:
0.01 average

Must apply:
entry + exit slippage

---

### 5. COMMISSION MODEL

Per-contract roundtrip estimated:

ES: $4.00
NQ: $4.00
CL: $5.00

Commission deducted from realized pnl.

---

## Fill Logic

Sandbox fills must simulate:

### Market Orders:
Immediate fill at:
best bid/ask adjusted by slippage

### Limit Orders:
Fill only if market crosses limit threshold

---

## Margin Awareness Layer

Adapter must expose:

- initial margin estimate
- maintenance margin estimate
- margin consumed after fill

No broker API required in Phase 1.

---

## Execution Event Outputs

Each fill event must emit:

- EXEC_OPEN
- EXEC_CLOSE
- EXEC_PARTIAL_CLOSE
- EXEC_REJECTED
- EXEC_MARGIN_BLOCKED

---

## Rejection Rules

Reject if:

1. insufficient simulated margin
2. invalid contract size
3. unsupported symbol
4. zero quantity request

---

## Integration Targets

This adapter feeds:

1. futures_position_manager.py
2. trade_decision_orchestrator.py
3. futures_risk_governor.py
4. dashboard futures pnl renderer

---

## Status

- Architecture locked
- Sandbox routing only
- No live broker execution yet
- Safe for implementation conversion on Laptop 1
