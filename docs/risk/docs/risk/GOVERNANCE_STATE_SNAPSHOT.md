# Governance State Snapshot
Capital Strata Systems (CSS)

## Purpose

The Governance State Snapshot records the operational state of the system at regular intervals.  
It allows reconstruction of what the system knew at any moment in time.

This snapshot complements the Risk Decision Ledger.

Together they provide:

• system state history  
• decision traceability  
• execution verification  
• forensic debugging capability

The snapshot functions as the **system heartbeat**.

---

## Storage Location

Snapshots are stored in:

logs/governance_state.jsonl

The file uses JSON Lines format where each line represents a full system state snapshot.

---

## Snapshot Frequency

The system records snapshots:

• every 5 minutes  
• whenever a major governance state change occurs  
• immediately before and after EOD processing

---

## Snapshot Fields

Each snapshot record should include the following fields.

timestamp  
thermostat_mode  
mode_entered_timestamp  
risk_per_trade  
max_concurrent_positions  
equity  
peak_equity  
drawdown  
cash_balance  
open_positions  
daily_loss_used  
weekly_drawdown_used  
trading_permission  
regime_gate_status  
capability_gate_status  
risk_governor_status  
broker_connection_status  
market_data_status

---

## Example Snapshot Record

{
 "timestamp": "2026-03-03T08:00Z",
 "thermostat_mode": "BASE",
 "mode_entered_timestamp": "2026-03-03T06:00Z",
 "risk_per_trade": 2.00,
 "max_concurrent_positions": 5,
 "equity": 204.35,
 "peak_equity": 204.35,
 "drawdown": 0.0,
 "cash_balance": 146.00,
 "open_positions": 2,
 "daily_loss_used": 0.00,
 "weekly_drawdown_used": 0.00,
 "trading_permission": "ALLOW",
 "regime_gate_status": "ALLOW",
 "capability_gate_status": "ALLOW",
 "risk_governor_status": "ALLOW",
 "broker_connection_status": "CONNECTED",
 "market_data_status": "OK"
}

---

## Relationship to Decision Ledger

The Governance State Snapshot records **system facts**.

The Risk Decision Ledger records **governance decisions**.

Example workflow:

1) Snapshot records the current system state.  
2) A governance module evaluates conditions.  
3) The decision is recorded in the Risk Decision Ledger.  
4) The next snapshot reflects the new state.

This separation ensures clean architecture between **state**, **decisions**, and **execution**.

---

## Audit Benefits

The snapshot system allows reconstruction of any point in time.

Example questions that can be answered:

• What was the thermostat mode when a trade occurred?  
• What was the drawdown when risk was reduced?  
• Was the broker connected when execution was attempted?  
• What positions existed when the system halted?

Snapshots combined with decision logs provide full chronological traceability.

---

## Governance

The Governance State Snapshot is part of the CSS risk governance framework.

Any modification requires:

• documentation update  
• policy version change  
• governance approval
