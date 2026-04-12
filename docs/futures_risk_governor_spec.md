# CSS Futures Risk Governor - Master Specification
## Phase 1 Sandbox Futures Risk Governance Lock

### Purpose
Defines capital risk control framework for CSS futures sandbox trading.

This specification governs:

- per-trade futures exposure limits
- per-symbol concentration caps
- total futures portfolio exposure ceilings
- margin stress controls
- daily futures drawdown protection
- forced liquidation triggers

---

## Supported Scope (Phase 1)

### Contracts:
- ES
- NQ
- CL

Sandbox only.

---

## Risk Governor Responsibilities

Must enforce:

### 1. PER-TRADE CONTRACT LIMITS

Maximum contracts per trade:

ES:
5

NQ:
5

CL:
3

Reject trades above limits.

---

### 2. TOTAL OPEN CONTRACT LIMIT

Maximum simultaneous open futures contracts:

Total portfolio max:
12 contracts

Across all symbols combined.

---

### 3. PER-SYMBOL CONCENTRATION CAP

Maximum open per symbol:

ES:
6

NQ:
6

CL:
4

---

### 4. MAX NOTIONAL EXPOSURE LIMIT

Total futures notional exposure:
Cannot exceed:

25% simulated capital base

---

### 5. INITIAL MARGIN PROTECTION

Before new trade approval:

Required:
Available margin > required initial margin

Else:
Reject trade.

---

### 6. MAINTENANCE MARGIN BREACH RULE

If maintenance breach occurs:

Trigger:
margin_warning = TRUE

If unresolved:
force liquidation sequence begins.

---

### 7. DAILY FUTURES LOSS STOP

If daily realized + unrealized futures pnl loss exceeds:

5% of total equity

Then:
Block all new futures trades for remainder of day.

---

### 8. FORCED LIQUIDATION RULE

Immediate forced close if:

- margin deficit unresolved
OR
- equity breach exceeds hard threshold

---

## Risk Event Outputs

Emit:

- FUTURES_RISK_APPROVED
- FUTURES_RISK_REJECTED
- FUTURES_MARGIN_WARNING
- FUTURES_MARGIN_BREACH
- FUTURES_DAILY_STOP_TRIGGERED
- FUTURES_FORCE_LIQUIDATION

---

## Integration Targets

Feeds:

1. futures_execution_adapter.py
2. futures_position_manager.py
3. trade_decision_orchestrator.py
4. futures_dashboard_pnl_renderer

---

## Override Modes

Supported future profiles:

- SAFE
- CONSERVATIVE
- BALANCED
- AGGRESSIVE

Phase 1 default:
BALANCED

---

## Status

- Architecture locked
- Sandbox governance only
- No live broker risk path modified
- Safe for Laptop 1 implementation conversion
