# CSS Options Risk Governor – Master Specification
## Phase 1 Sandbox Risk Governance Lock

### Purpose
Defines portfolio-level risk controls for options trading in CSS Phase 1 sandbox.

This governor controls:

- max premium at risk
- per-position risk caps
- per-symbol concentration
- total open options exposure
- loss containment rules
- options allocation within multi-asset governance

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

Sandbox only.

---

## Core Risk Objectives

The options risk governor must ensure:

1. no single option trade can materially damage equity
2. no single symbol dominates options exposure
3. options risk stays subordinate to whole-portfolio governance
4. premium decay and expiry risk remain bounded
5. options losses cannot silently compound

---

## Required Risk Controls

### 1. Max Premium Risk Per Trade

Default rule:

max premium at risk per trade = 0.5% of equity

Example:
If equity = 10,000
max premium at risk = 50

---

### 2. Max Total Options Premium At Risk

Default rule:

total open options premium at risk <= 2.0% of equity

---

### 3. Max Open Options Positions

Default rule:

max simultaneous open options positions = 3

---

### 4. Per-Symbol Concentration Cap

Default rule:

no more than 50% of total options premium at risk may be allocated to one symbol

---

### 5. Near-Expiry Exposure Cap

Default rule:

positions with days_to_expiry <= 3
must not exceed 25% of total options premium risk

---

### 6. Daily Options Loss Stop

If total realized + unrealized options loss for the day exceeds:

1.0% of equity

then:
- no new options trades allowed for remainder of cycle/day

---

## Entry Approval Rules

A new options trade may open only if all pass:

1. trade premium <= per-trade cap
2. total premium at risk remains <= total cap
3. symbol concentration remains valid
4. daily options loss stop not breached
5. portfolio risk governor grants approval

---

## Mandatory Rejection Conditions

Reject trade if:

- premium too high
- contract count invalid
- total options positions at cap
- symbol exposure cap breached
- near-expiry concentration too high
- portfolio drawdown state forbids new risk

---

## Monitoring Requirements

Every cycle the governor must recompute:

- open options premium at risk
- total options unrealized pnl
- total options realized pnl
- symbol concentration ratios
- near-expiry concentration ratio

---

## Alert States

Governor must classify current options state as:

- NORMAL
- ELEVATED
- RESTRICTED
- BLOCKED

### NORMAL
All caps comfortably within limits

### ELEVATED
Exposure approaching limits

### RESTRICTED
Only highest-confidence options entries allowed

### BLOCKED
No new options positions allowed

---

## Integration Hook

Future orchestrator path:

TradeDecisionOrchestrator
→ PortfolioRiskGovernor
→ OptionsRiskGovernor
→ options execution approval / rejection

---

## Dashboard Outputs Required

Dashboard must show:

- options premium at risk
- options utilization vs cap
- options state: NORMAL / ELEVATED / RESTRICTED / BLOCKED

---

## Non-Regression Rule

This governor:
- must not weaken existing crypto/fx/futures risk controls
- must remain additive to current governance stack
- options risk must remain isolated until implementation validated

---

## Laptop 1 Implementation Target

Future file target:

backend/app/options/options_risk_governor.py

---

## Governance Status

Architecture locked.
Safe for implementation after merge.
No production execution path modified.
