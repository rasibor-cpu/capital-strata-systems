# Capital Thermostat v1.1
Capital Strata Systems (CSS)

## Purpose
The Capital Thermostat dynamically adjusts trading risk based on system health, equity performance, and drawdown conditions. It ensures rapid capital protection while allowing controlled risk expansion when conditions improve.

This version introduces intraday mode evaluation every 4 hours with a 1-hour dwell requirement for upward transitions.

---

## Operating Principles

1. De-risk immediately when capital conditions deteriorate.
2. Increase risk gradually when performance improves.
3. Never skip intermediate risk modes.
4. Require stability before increasing exposure.
5. Maintain full auditability of all thermostat decisions.

---

## Thermostat Modes

Mode | Risk Level | Purpose
---- | ---------- | -------
HOT | Highest allowed | Strong performance conditions
WARM | Moderately elevated | Positive performance environment
BASE | Normal baseline | Standard operations
COOL | Reduced exposure | Capital protection
HALT | Trading stopped | Severe risk condition

---

## Evaluation Schedule

The thermostat evaluates system conditions at two levels.

### End-of-Day Evaluation

Performed after EOD processing to determine the baseline mode for the next trading session.

### Intraday Evaluation

Performed every 4 hours during the trading day using mark-to-market equity.

Example logic:

if now_utc - last_thermostat_eval >= 4 hours:
    evaluate_mode()

---

## Intraday Transition Rules

### Downward Movement (Risk Reduction)

Downward transitions occur immediately when conditions deteriorate.

Examples:

HOT -> WARM
WARM -> BASE
BASE -> COOL
COOL -> HALT

No dwell time is required for downward transitions.

---

### Upward Movement (Risk Expansion)

Upward transitions require a minimum dwell time of one hour in the immediate lower mode.

Examples:

BASE -> WARM allowed only if the system has spent at least one hour in BASE.

WARM -> HOT allowed only if the system has spent at least one hour in WARM.

---

## Skip-Level Prevention

The thermostat must never skip intermediate modes.

Invalid transitions:

BASE -> HOT
COOL -> WARM
HALT -> BASE

Valid transitions must move step-by-step:

COOL -> BASE -> WARM -> HOT

---

## Mode Tracking

Each mode maintains an entry timestamp.

Example variable:

mode_entered_timestamp

Upward transitions require:

current_time - mode_entered_timestamp >= 1 hour

---

## Capital Protection Triggers

Immediate downgrade or HALT occurs when:

- Daily loss limit breached
- Weekly drawdown limit breached
- Broker connection failure
- Ledger integrity failure
- Risk engine failure

In HALT mode:

new_entries = disabled
position_exits = allowed

---

## Effective Risk Overlay

The thermostat does not modify the base policy configuration.

Instead it produces an effective risk overlay.

Example:

effective_risk_per_trade = min(base_policy_risk_per_trade, thermostat_risk_per_trade)

effective_max_positions = min(base_policy_max_positions, thermostat_max_positions)

This preserves governance controls while enabling adaptive risk management.

---

## Audit Logging

Every thermostat evaluation must record:

- evaluation timestamp
- current equity
- peak equity
- drawdown percentage
- prior mode
- proposed mode
- applied mode
- reason codes

Example log entry:

timestamp: 2026-03-03T04:00Z
equity: 204.35
drawdown: 0.8%
prior_mode: BASE
proposed_mode: WARM
applied_mode: BASE
reason: dwell_time_not_met

---

## Reporting Integration

The Daily Position Screen must display:

- Thermostat evaluation interval
- Last thermostat evaluation timestamp
- Current thermostat mode
- Mode entered timestamp

The Action Hint section should reference thermostat status.

Example:

Action Hint:
System healthy. Thermostat mode BASE.
Risk deployment permitted.

---

## Governance

This document defines the official thermostat policy for Capital Strata Systems.

Any future change requires:

- policy version increment
- documentation update
- governance approval
