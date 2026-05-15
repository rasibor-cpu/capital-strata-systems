# CSS Micro-Live Pilot Incident Review Worksheet 2026

Status: DOCUMENTATION-ONLY INCIDENT WORKSHEET
Scope: Controlled micro-live pilot preparation, observation, and review
Authority: Capital Strata Systems PCNRASS governance

## 1. Purpose

This worksheet records anomalies, blockers, reconciliation mismatches, failed
checks, safety events, and operational concerns discovered before, during, or
after a controlled CSS micro-live pilot.

It is usable during:

- Pre-pilot readiness review
- Manual evidence packet review
- Controlled pilot observation
- Mandatory post-trade pause
- Post-pilot reconciliation
- Governance review

This worksheet does not authorize trading or resolve blockers by itself. It
does not arm execution, place orders, mutate broker state, override a
kill-switch, bypass governance, replace PCNRASS validation, create an
approval-grant endpoint, enable unrestricted live trading, or activate
persistence.

## 2. Incident Identification

- Incident ID:
- Date detected:
- Time detected:
- Detected by:
- Role:
- Phase: pre-pilot / during-pilot / post-pilot
- Severity: LOW / MEDIUM / HIGH / CRITICAL
- Status: OPEN / UNDER_REVIEW / RESOLVED / ESCALATED / NO_GO
- Related evidence packet ID:
- Related sign-off register entry ID:
- Related checklist ID:
- Related go/no-go record ID:
- Related broker readiness confirmation ID:

## 3. Incident Type

Select all that apply:

- [ ] Broker readiness issue
- [ ] Kill-switch issue
- [ ] PCNRASS failure
- [ ] Order-intent mismatch
- [ ] Dry-run probe mismatch
- [ ] Replay/audit mismatch
- [ ] Ledger/PnL mismatch
- [ ] Slippage/fee discrepancy
- [ ] UI/operator evidence issue
- [ ] Credential/security concern
- [ ] Runtime/system error
- [ ] Other:

## 4. Description

What happened:

-

Expected behavior:

-

Actual behavior:

-

Evidence references:

-

Screenshot or log references:

-

Correlation IDs if available:

-

## 5. Impact Assessment

Trading impact:

-

Broker/account impact:

-

Governance impact:

-

Audit/replay impact:

-

Financial impact:

-

Operator safety impact:

-

## 6. Immediate Action

Record the immediate operational response:

| Action | Status | Notes |
| --- | --- | --- |
| Pilot paused |  |  |
| NO-GO declared |  |  |
| Kill-switch checked |  |  |
| Broker state verified |  |  |
| Evidence packet updated |  |  |
| Issue owner assigned |  |  |
| PCNRASS rerun considered |  |  |
| Operator/reviewer notified |  |  |

Issue owner:

- Name:
- Role:
- Contact:
- Assigned date/time:

## 7. Root Cause Review

Suspected cause:

-

Confirmed cause:

-

Related files/modules:

-

Related evidence IDs:

-

Related commits/tags:

-

Contributing factors:

-

## 8. Resolution Plan

- Required fix:
- Validation required:
- Reviewer:
- Re-test date:
- PCNRASS required before close: YES / NO
- Broker readiness refresh required: YES / NO
- Kill-switch re-confirmation required: YES / NO
- Evidence packet update required: YES / NO

Resolution steps:

| Step | Owner | Due Date | Status | Notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## 9. Closure

- Closure decision:
- Final status: RESOLVED / ESCALATED / NO_GO / DEFERRED
- Closure rationale:
- Operator sign-off:
- Reviewer sign-off:
- Date closed:
- Time closed:
- Lessons learned:
- Follow-up work required:
- Follow-up owner:
- Follow-up due date:

## 10. Safety Disclaimers

- This worksheet does not authorize trading.
- This worksheet does not resolve blockers by itself.
- This worksheet does not arm execution.
- This worksheet does not execute orders.
- This worksheet does not mutate broker account state.
- This worksheet does not override the kill-switch.
- This worksheet does not replace final PCNRASS validation.
- This worksheet does not bypass broker readiness confirmation.
- This worksheet does not create an approval-grant endpoint.
- This worksheet does not enable unrestricted live trading.
- This worksheet does not activate persistence.

Unresolved HIGH or CRITICAL incidents require NO-GO until reviewed and closed.
Unresolved broker readiness, kill-switch, credential/security, or PCNRASS
issues block pilot consideration. Any ledger/PnL mismatch or replay/audit
mismatch must be reconciled or escalated before further pilot review.

