# CSS Commercialization Production Rollback Plan

Status: RELEASE ARTIFACT — REQUIRES PRODUCTION-LIKE TEST EVIDENCE

## Trigger conditions

Rollback is initiated when a production release creates or materially risks:

- incorrect customer fee calculation;
- contract/version mismatch;
- unauthorized trial conversion;
- reconciliation divergence;
- duplicate/idempotency failure;
- payment-provider error or unexpected collection;
- security/control regression;
- data integrity failure; or
- release-readiness blocker.

## Immediate containment

1. Disable payment collection provider configuration.
2. Block new collection preflights.
3. Preserve all immutable evidence and external provider references.
4. Keep trading/broker execution authority independent and unchanged.
5. Suspend affected commercialization workflow rather than deleting records.
6. Capture release SHA, incident time, affected accounts/periods and evidence.

## Application rollback

- restore the last certified application release;
- run schema compatibility/rollback procedure;
- verify migrations and canonical commercialization records remain readable;
- re-run governance, compile validation, full regression and critical UAT;
- keep fee collection disabled until reconciliation is complete.

## Financial reconciliation

For every potentially affected account:

- recompute canonical CSS-attributable economics;
- verify independent/customer-directed economics separately;
- reconcile invoice/receivable/payment observations;
- identify any erroneous collection;
- record correction/refund requirements without mutating historical evidence.

## Re-enable criteria

Commercial charging may be re-enabled only after:

- root cause identified;
- corrective release validated;
- security/operations certification current;
- reconciliation clean;
- payment-provider approval current;
- required UAT passed;
- launch dossier updated;
- authorized release owner signs off.

Rollback/re-enable never grants broker or trading execution authority.
