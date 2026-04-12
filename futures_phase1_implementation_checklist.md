# CSS Futures Phase 1 Implementation Checklist
## Execution Build Sequence Lock

This document defines the exact laptop implementation order for CSS futures deployment.

---

## Phase 1 Coding Order

### Step 1: Core Engine Files
1. futures_position_manager.py
2. futures_risk_governor.py
3. futures_audit_ledger.py

---

### Step 2: Orchestrator Integration
4. Integrate FUTURES asset_class into TradeDecisionOrchestrator
5. Add futures routing dispatch path
6. Add futures capital allocation hook

---

### Step 3: Dashboard Integration
7. Add futures open position panel
8. Add futures closed PnL panel
9. Add futures subtotal aggregation line

---

### Step 4: Sandbox Harness
10. Build futures sandbox replay runner
11. Build futures scenario simulation engine
12. Add liquidation trigger test suite

---

### Step 5: Coinbase Capital Safety Gate
Starting capital:
CAD 200 maximum

Rules:
- Initial live futures risk cap = 2% account max exposure
- Max one active futures contract at a time
- Micro-sized test mode only
- No scaling until profitable validation complete

---

## Phase 1 Go-Live Condition

Must satisfy:
- 100 successful sandbox replay passes
- Zero margin breach failures
- Zero liquidation logic defects
- Positive net simulated PnL over test cycle

---

## Status:
Architecture complete
Implementation pending laptop session
