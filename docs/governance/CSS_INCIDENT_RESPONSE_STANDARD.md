# CSS Incident Response Standard

## Incident Severity Levels

### SEV1: Critical
* **Definition:** Complete loss of trading capability, broker disconnection, severe data corruption, or immediate financial risk/bleed.
* **Response:** Immediate page to on-call engineers. Trade execution halted (kill switch engaged).

### SEV2: High
* **Definition:** Partial degradation of services, delayed market data, or non-critical feature outage without direct capital risk.
* **Response:** Acknowledge within 30 minutes. Remediate within 4 hours.

### SEV3: Moderate
* **Definition:** Minor UI glitches, cosmetic dashboard issues, or non-trading administrative functions failing.
* **Response:** Addressed in the next deployment cycle.

## Escalation Paths
1. **L1 Support (On-Call):** Triage and attempt immediate stabilization (e.g., kill switch, rollback).
2. **L2 Engineering:** Deep diagnosis and patch creation.
3. **L3 Management:** Invoked for SEV1 incidents to handle broker communications and external reporting.

## Communication Process
* Internal incident channel (#css-incidents) updated every 30 minutes for SEV1, every 2 hours for SEV2.
* Broker/Partner communications handled exclusively by the Operations Manager.

## Evidence Retention
* All audit logs, system states, and chat histories relating to a SEV1 or SEV2 incident must be frozen and archived for a minimum of 7 years.
* PnL snapshots at the time of the incident must be preserved immutably.

## Post-Incident Review (PIR) Process
* A blameless PIR must be conducted within 3 business days of any SEV1 or SEV2 incident.
* Must yield actionable Jira tickets to prevent recurrence.
