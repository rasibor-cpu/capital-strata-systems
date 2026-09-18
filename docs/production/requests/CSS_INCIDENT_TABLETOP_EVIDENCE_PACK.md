# CSS Production Incident Tabletop — Evidence Pack

Status: READY TO RUN — REQUIRES REAL OPERATORS / SIGN-OFF

## Purpose

Run one documented production-readiness incident exercise before authorization.
The exercise does not require live customer funds; it requires accountable
operators to execute the response process using production-like systems and
evidence channels.

## Participants

Record:
- Incident Commander
- Security Lead
- Operations Lead
- Finance/Reconciliation Lead
- Compliance/Legal Contact
- Customer Communications Owner
- Release Owner
- Observer / Evidence Recorder

## Scenario

At T+0, monitoring reports all three conditions:

1. a payment-provider webhook appears duplicated;
2. the customer receivable ledger differs from provider settlement by one
   transaction; and
3. an application release was deployed within the preceding 30 minutes.

Assume no evidence yet of broker/trading compromise.

## Required actions

Operators must demonstrate:

1. declare incident and timestamp;
2. identify affected release SHA/environment;
3. disable payment provider collection capability;
4. preserve provider/webhook/ledger/audit evidence;
5. verify broker/trading execution remains separately blocked/unchanged;
6. quantify affected customers/transactions;
7. reconcile provider event vs CSS ledger;
8. decide whether rollback trigger criteria are met;
9. execute or simulate the documented rollback path;
10. verify post-rollback readiness remains fail-closed;
11. determine customer/regulatory notification obligations;
12. document root cause / corrective action;
13. require revalidation before collection can be re-enabled.

## Pass criteria

- No duplicate collection is permitted.
- No audit/history record is deleted or silently rewritten.
- Reconciliation discrepancy is isolated.
- Payment collection remains disabled until explicit revalidation.
- Trading/broker execution does not become authorized.
- Evidence is sufficient to reconstruct the timeline.
- Owners and escalation contacts are unambiguous.
- Release owner records APPROVE/REJECT for incident closure.

## Evidence to retain

- exercise ID;
- participants/roles;
- UTC start/end;
- environment and release SHA;
- screenshots/log references;
- provider event IDs;
- reconciliation output;
- rollback evidence;
- notification decision;
- corrective-action list;
- participant attestations;
- final incident-owner approval.

Map final evidence to production category INCIDENT_TABLETOP.
