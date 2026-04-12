# CSS Futures Audit Ledger - Master Specification
## Phase 1 Sandbox Futures Audit Governance Lock

### Purpose

Defines institutional-grade audit traceability for futures trading activity inside CSS sandbox futures engine.

This specification governs:

- event-level futures trade logging
- contract lifecycle traceability
- realized/unrealized pnl attribution
- margin debit/credit audit records
- liquidation event recording
- reconciliation support

---

## Supported Scope (Phase 1)

### Futures Instruments:
- ES
- NQ
- CL

Sandbox only.

---

## Audit Objectives

Every futures event must produce immutable ledger records.

Ledger must support:

1. full trade replay reconstruction
2. pnl attribution verification
3. margin audit review
4. liquidation event traceability
5. reconciliation against dashboard summaries

---

## Required Event Types

Ledger must support these event classes:

### Trade Events
- FUTURES_ORDER_ACCEPTED
- FUTURES_ORDER_REJECTED
- FUTURES_POSITION_OPENED
- FUTURES_POSITION_PARTIAL_CLOSE
- FUTURES_POSITION_CLOSED

### Mark-to-Market Events
- FUTURES_MARK_TO_MARKET_UPDATED
- FUTURES_UNREALIZED_PNL_UPDATED

### Margin Events
- INITIAL_MARGIN_RESERVED
- VARIATION_MARGIN_ADJUSTED
- MAINTENANCE_MARGIN_WARNING
- MARGIN_BREACH_TRIGGERED

### Risk Events
- STOP_LOSS_TRIGGERED
- TAKE_PROFIT_TRIGGERED
- FORCED_LIQUIDATION_TRIGGERED

### Contract Events
- CONTRACT_EXPIRY_WARNING
- CONTRACT_ROLLOVER_REGISTERED

### Reconciliation Events
- DAILY_LEDGER_RECONCILED

---

## Ledger Record Structure

Each ledger record must store:

- ledger_id
- timestamp_utc
- event_type
- symbol
- contract_month
- side
- contracts
- entry_price
- exit_price
- mark_price
- realized_pnl
- unrealized_pnl
- margin_delta
- account_equity_snapshot
- strategy_source
- risk_state_snapshot
- notes

---

## PnL Attribution Rules

### Unrealized PnL:
Updated continuously from mark price changes.

### Realized PnL:
Booked only upon:
- partial close
- full close
- liquidation close

Formula:
(realized exit - entry) × contracts × multiplier

---

## Margin Audit Rules

Ledger must track:

### Initial Margin:
Recorded at entry.

### Variation Margin:
Recorded each MTM cycle.

### Margin Breach:
Must generate breach record immediately.

---

## Forced Liquidation Logging

If liquidation occurs:

Ledger must record:
- trigger reason
- breach threshold
- liquidation timestamp
- liquidation execution price
- realized forced pnl

---

## Reconciliation Requirements

Daily reconciliation must verify:

1. Open positions match position manager state
2. Realized pnl totals match dashboard totals
3. Unrealized pnl matches MTM engine
4. Margin balances reconcile exactly

---

## Dashboard Reporting Link

Dashboard must consume ledger totals for:

FUTURES TOTAL UPNL
FUTURES TOTAL RPNL
FORCED LIQUIDATIONS TODAY
MARGIN BREACH COUNT

---

## Governance Lock Status

Status:
- Architecture locked
- Sandbox governance only
- No live broker execution modified
- Safe for merge after review
