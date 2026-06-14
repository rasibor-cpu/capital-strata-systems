# CSS Incident Response Runbook

## Purpose

This runbook defines incident classification, response ownership, escalation, and evidence capture requirements for controlled CSS paper-trading operations.

This document is documentation-only. It does not change runtime, broker, execution, dashboard, credential, risk, margin, security, or trading logic.

## Incident Severity Levels

| Severity | Definition | Examples |
| --- | --- | --- |
| LOW | Minor operational issue with no safety impact and no evidence loss. | Cosmetic dashboard mismatch, non-blocking warning, delayed evidence capture. |
| MEDIUM | Operational degradation requiring review but not immediate shutdown. | Dashboard panel unavailable, non-critical run warning, stale non-trading display. |
| HIGH | Safety, session, legal acceptance, risk, margin, PnL, or evidence issue that may invalidate the run. | Legal acceptance unavailable, session state ambiguous, trade gate evidence missing, PnL ledger inconsistency. |
| CRITICAL | Live-execution, credential, broker, or safety-boundary event requiring immediate shutdown and Robert review. | Live mode unexpectedly enabled, broker execution attempted, credential exposure, trade gate bypass. |

## Response Owners

| Role | Responsibility |
| --- | --- |
| Operator | Stop unsafe activity, preserve evidence, classify initial severity, notify reviewer. |
| Developer | Diagnose technical cause after evidence is preserved; no hot fixes during certification run unless separately approved. |
| Governance Reviewer | Confirm evidence completeness and certification impact. |
| Operations Reviewer | Confirm runbook adherence and restart readiness. |
| Robert | Final review for HIGH/CRITICAL incidents and approval before continuation. |

## LOW Incident Response

1. Record the issue in the run notes.
2. Capture screenshot or terminal output if useful.
3. Continue only if safety controls, broker mode, credentials, session, and trade gates remain clear.
4. Include issue in certification summary.

Escalation path: Operator -> Operations Reviewer if repeated.

## MEDIUM Incident Response

1. Pause new paper trade creation if the issue affects monitoring clarity.
2. Preserve runtime and dashboard output.
3. Determine whether evidence remains valid.
4. Resume only if safety and evidence integrity are not compromised.
5. Record the issue and reviewer disposition.

Escalation path: Operator -> Operations Reviewer -> Governance Reviewer.

## HIGH Incident Response

1. Stop new paper trade creation.
2. Preserve logs, dashboard output, terminal output, and evidence files.
3. Capture branch, HEAD, runtime mode, session state, and operator context.
4. Do not modify runtime code, credentials, or database records.
5. Determine whether emergency shutdown is required.
6. Require Robert review before the evidence is used for certification or before restart if the issue affects safety or governance.

Escalation path: Operator -> Operations Reviewer -> Governance Reviewer -> Robert.

## CRITICAL Incident Response

1. Initiate `docs/operations/CSS_EMERGENCY_SHUTDOWN_RUNBOOK.md`.
2. Stop all new activity.
3. Preserve all logs and outputs.
4. Confirm whether live mode, live arm, broker execution, credential exposure, or trade gate bypass occurred.
5. Do not restart until Robert review is complete.
6. Treat certification run as invalid unless Robert and governance review explicitly accept it as partial evidence.

Escalation path: Operator -> Robert immediately, with Developer, Governance Reviewer, and Operations Reviewer engaged.

## Evidence Capture Requirements

For every incident, retain:

* Incident ID.
* Timestamp.
* Severity.
* Operator.
* Branch and HEAD.
* Runtime mode.
* Broker and broker mode.
* Session ID if available.
* Description.
* Immediate action taken.
* Logs/screenshots/output.
* Certification impact.
* Restart decision.
* Robert disposition for HIGH/CRITICAL incidents.

## Incident Record Template

```text
Incident ID:
Timestamp:
Severity:
Operator:
Branch:
HEAD:
Runtime Mode:
Broker:
Broker Mode:
Session ID:
Description:
Immediate Actions:
Evidence Captured:
Certification Impact:
Restart Decision:
Reviewer:
Robert Disposition:
```

## Escalation Rules

* Credential exposure is always CRITICAL.
* Unexpected live mode is always CRITICAL.
* Broker execution during paper certification is always CRITICAL.
* Trade gate bypass is always CRITICAL.
* Legal acceptance failure is HIGH unless paired with attempted trade creation, then CRITICAL.
* Session ambiguity is HIGH unless it suggests live execution or data corruption, then CRITICAL.

## Closure Requirements

An incident can be closed only when:

1. Evidence is preserved.
2. Severity is confirmed.
3. Certification impact is documented.
4. Restart or no-restart decision is recorded.
5. Robert review is recorded for HIGH or CRITICAL incidents.
