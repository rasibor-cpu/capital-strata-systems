# CSS Launch Evidence Pack

Status: TEMPLATE — COMPLETE ONLY WHEN EVERY REQUIRED EVIDENCE ITEM IS APPROVED

Dossier ID: [DOSSIER-ID]
Target release SHA: [COMMIT-SHA]
Target jurisdiction(s): [JURISDICTIONS]
Target service mode(s): [DISCOVER / CONFIRM / AUTO]
Release owner: [OWNER]
Prepared at: [UTC TIMESTAMP]

## 1. Approved Customer Agreement

Evidence reference: [REFERENCE]
Agreement ID/version: [ID / VERSION]
Approved: [YES/NO]

## 2. Jurisdiction Legal / Regulatory Review

Evidence reference: [REFERENCE]
Jurisdiction: [CODE]
Approved modes: [MODES]
Approved: [YES/NO]

## 3. Technical Validation

Evidence reference: [CI RUN / VALIDATION ID]
Validated SHA: [SHA]
Full regression test count: [COUNT]
Governance validation: [PASS/FAIL]
Commercialization UAT workflow: [PASS/FAIL]
Approved: [YES/NO]

## 4. Security & Operations Certification

Evidence reference: [REFERENCE]
Secrets management: [PASS/FAIL]
TLS: [PASS/FAIL]
Access control: [PASS/FAIL]
Audit logging: [PASS/FAIL]
Monitoring/alerting: [PASS/FAIL]
Backup/restore test: [PASS/FAIL]
Rollback test: [PASS/FAIL]
Reconciliation: [PASS/FAIL]
Incident response: [PASS/FAIL]
Dependency/vulnerability review: [PASS/FAIL]
Approved: [YES/NO]

## 5. Reconciliation Certification

Evidence reference: [REFERENCE]
Customer economics reconciliation: [PASS/FAIL]
Invoice/receivable reconciliation: [PASS/FAIL]
Provider settlement reconciliation: [PASS/FAIL]
Approved: [YES/NO]

## 6. Payment Provider / Collection Authority

Provider ID: [PROVIDER]
Provider configuration evidence: [REFERENCE]
Payment collection authority evidence: [REFERENCE]
Preflight: [PASS/FAIL]
Approved: [YES/NO]

## 7. Production-like UAT

UAT run ID: [UAT-ID]
Environment reference: [REFERENCE]
All mandatory scenarios passed: [YES/NO]
Evidence reference: [REFERENCE]

## 8. Rollback Plan

Plan reference: docs/CSS_COMMERCIAL_ROLLBACK_PLAN.md
Production-like rollback test evidence: [REFERENCE]
Approved: [YES/NO]

## 9. Customer Notification Controls

Notice policy evidence: [REFERENCE]
Delivery provider ID: [PROVIDER]
Delivery provider approval: [YES/NO]
Preflight evidence: [REFERENCE]

## 10. Owner Sign-off

Release owner: [NAME/ROLE]
Decision: [APPROVE / REJECT]
Timestamp: [UTC]
Evidence/sign-off reference: [REFERENCE]

## Release Rule

Every required launch-evidence category must exist and be approved in the
canonical dossier. The commercialization release readiness and payment
collection preflight must both be green.

This dossier never grants broker or trading execution authority. Any AUTO-mode
release requires its own separately approved execution/regulatory controls.
