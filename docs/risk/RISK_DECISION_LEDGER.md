# Risk Decision Ledger
Capital Strata Systems (CSS)

## Purpose

The Risk Decision Ledger records every governance decision made by the system.  
It acts as the permanent audit trail for all capital governance actions.

This ledger ensures that every risk-related decision can be explained,
reproduced, and audited.

It functions as the **flight recorder for the trading engine**.

---

## Storage Location

All decision records are stored in:

logs/risk_decisions.jsonl

The file uses **JSON Lines format**, meaning each line is a complete JSON record.

This format allows easy streaming, indexing, and audit retrieval.

---

## Logging Policy

CSS records **every evaluation**, not only changes.

This includes:

- Thermostat evaluations
- Risk governor approvals
- Regime gate decisions
- Capability gate decisions
- Execution accept/reject decisions

Recording every evaluation ensures complete forensic traceability.

---

## Record Structure

Each record contains the following fields.

timestamp  
module  
decision  
prior_state  
proposed_state  
applied_state  
reason_codes  
equity  
drawdown  
additional_context  

Example:

{
 "timestamp": "2026-03-03T04:00Z",
 "module": "thermostat",
 "decision": "mode_evaluation",
 "prior_state": "BASE",
 "proposed_state": "WARM",
 "applied_state": "BASE",
 "reason_codes": ["dwell_time_not_met"],
 "equity": 204.35,
 "drawdown": 0.8
}

---

## Thermostat Logging

Every thermostat evaluation must create a record.

Example:

{
 "timestamp": "2026-03-03T08:00Z",
 "module": "thermostat",
 "decision": "evaluation",
 "prior_state": "BASE",
 "proposed_state": "COOL",
 "applied_state": "COOL",
 "reason_codes": ["drawdown_threshold"],
 "equity": 198.40,
 "drawdown": 2.8
}

---

## Risk Governor Logging

Position sizing approvals or rejections must be recorded.

Example:

{
 "timestamp": "2026-03-03T09:15Z",
 "module": "risk_governor",
 "decision": "position_size_check",
 "prior_state": "request",
 "proposed_state": "approve",
 "applied_state": "approve",
 "reason_codes": ["within_risk_limits"]
}

---

## Regime Gate Logging

Market regime checks must be recorded.

Example:

{
 "timestamp": "2026-03-03T10:00Z",
 "module": "regime_gate",
 "decision": "market_condition_check",
 "prior_state": "unknown",
 "proposed_state": "block",
 "applied_state": "block",
 "reason_codes": ["insufficient_market_data"]
}

---

## Capability Gate Logging

Instrument capability validation must be recorded.

Example:

{
 "timestamp": "2026-03-03T11:20Z",
 "module": "capability_gate",
 "decision": "instrument_validation",
 "prior_state": "check",
 "proposed_state": "allow",
 "applied_state": "allow",
 "reason_codes": ["instrument_supported"]
}

---

## Execution Logging

Order acceptance or rejection must be recorded.

Example:

{
 "timestamp": "2026-03-03T12:05Z",
 "module": "execution_engine",
 "decision": "order_submission",
 "prior_state": "request",
 "proposed_state": "accept",
 "applied_state": "accept",
 "reason_codes": ["risk_governor_approved"]
}

---

## Audit Retrieval

The ledger allows full reconstruction of system decisions.

Example queries:

- Why was trading halted?
- Why was a position rejected?
- Why did the thermostat reduce risk?

Since every evaluation is recorded, the ledger provides
complete chronological traceability.

---

## Governance

The Risk Decision Ledger is part of the **core governance layer** of CSS.

Any modification to logging policy requires:

- documentation update
- policy version update
- governance approval
