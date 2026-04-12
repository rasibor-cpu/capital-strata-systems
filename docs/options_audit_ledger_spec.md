# CSS Options Audit Ledger – Master Specification
## Phase 1 Sandbox Auditability Governance Lock

### Purpose
Defines the audit ledger architecture for CSS options sandbox trading.

This ledger governs:

- option trade event logging
- entry and exit audit records
- expiry event recording
- premium debit/credit tracking
- realized and unrealized pnl snapshots
- compliance-grade traceability for sandbox review

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

## Core Audit Objectives

The audit ledger must ensure:

1. every options trade can be reconstructed later
2. every premium movement is traceable
3. every close reason is preserved
4. expiry events are explicitly recorded
5. pnl attribution is reviewable by symbol and trade

---

## Required Event Types

The ledger must support these event classes:

- SIGNAL_ACCEPTED
- CONTRACT_SELECTED
- ORDER_OPENED
- POSITION_REGISTERED
- MARK_TO_MARKET_UPDATED
- STOP_LOSS_TRIGGERED
- PROFIT_TARGET_TRIGGERED
- MANUAL_EXIT
- EXPIRED_ITM
- EXPIRED_OTM
- POSITION_CLOSED
- AUDIT_RECONCILED

---

## Required Ledger Fields

Every options audit record must store:

- event_id
- timestamp
- symbol
- option_type
- strike
- expiry_date
- contracts
- event_type
- entry_premium
- current_premium
- exit_premium
- realized_pnl
- unrealized_pnl
- close_reason
- cycle_id
- orchestrator_decision_id

---

## Entry Event Requirements

At option open, ledger must record:

- approved signal source
- selected contract
- premium paid
- contract count
- projected risk amount
- initial Greeks snapshot

---

## Mark-to-Market Event Requirements

Each update cycle must optionally log:

- current premium
- updated unrealized pnl
- updated Greeks
- days to expiry

This may be full-detail or summary mode depending on dashboard cadence.

---

## Exit Event Requirements

At close, ledger must record:

- exit premium
- realized pnl
- exit reason
- final days to expiry
- final underlying spot price

---

## Expiry Event Requirements

At expiry, ledger must record:

### If OTM:
- option expired worthless
- full premium loss realized

### If ITM:
- intrinsic settlement value
- realized pnl after settlement logic

---

## Reconciliation Rules

The ledger must reconcile against:

- options_position_manager open ledger
- options closed positions ledger
- dashboard pnl summaries

Mismatch condition must raise:
AUDIT_RECONCILED = FALSE

---

## Query Requirements

Ledger must support filtering by:

- symbol
- date range
- event type
- option type
- close reason
- cycle id

---

## Output Reports Required

The ledger must enable reporting for:

1. all options trades by day
2. pnl by symbol
3. expiry outcomes
4. stop-loss frequency
5. profit-target frequency
6. options trade win/loss ratio

---

## Data Storage Target

Future implementation target:

audit_logs/options_audit_ledger.jsonl

Optional later phase:
database-backed ledger storage

---

## Non-Regression Rule

This ledger:
- must not disturb existing crypto/fx/futures audit logs
- must remain additive to current audit framework
- options audit must remain isolated until validated

---

## Laptop 1 Implementation Target

Primary implementation file:

backend/app/options/options_audit_logger.py

Secondary storage target:

audit_logs/options_audit_ledger.jsonl

---

## Governance Status

Architecture locked.
Safe for merge after review.
No production execution path modified.
