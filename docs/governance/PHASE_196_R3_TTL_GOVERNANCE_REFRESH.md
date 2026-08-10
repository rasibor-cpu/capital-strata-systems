# Phase 196-R3 — Live-Authority TTL Governance Reconciliation

## Status

**GOVERNANCE REFRESH ONLY — LIVE TRADING NOT AUTHORIZED**

Phase 196-R2 implemented the live-authority lease/TTL control after the earlier
Phase 189-192 governance artifacts classified `BLK-AUTH-TTL` as incomplete.

This reconciliation updates the current blocker posture while preserving the
historical accuracy of the earlier phase documents.

## Resolved blocker

`BLK-AUTH-TTL` is **RESOLVED** by Phase 196-R2.

Current enforcement includes:

- scoped live-authority lease validation;
- expiry enforcement;
- revocation handling;
- consumed/single-use rejection;
- fail-closed integration into live execution authority.

Phase 189 `READ_ONLY_OPERATIONAL` TTL remains a separate read-only control and
must not be cited as live execution authority.

## Unchanged blockers and non-claims

This governance refresh does **not**:

- authorize live trading;
- grant execution authority;
- clear `BLK-RC004-LIVE-UNLOCK`;
- clear `BLK-FX-CONVERSION`;
- certify OANDA LIVE execution;
- complete RC-003R FINAL custody/re-certification;
- clear DIP live readiness;
- designate an RC-LIVE freeze SHA;
- issue founder GO/NO-GO approval;
- contact any broker or use any secret.

The aggregate live-pilot posture therefore remains **NO-GO**.

## Baseline

Candidate branch: `css-rc-live-001-candidate`

Baseline HEAD before this governance refresh:
`1cca2f3091232634268c9ad6a0f9c78b83d76f72`

Phase 196-R2 and the recovery baseline were previously validated with:

- full repository suite: 3733 passed, 5 skipped, 0 failed;
- Phase 196-R2 focused validation: 18 passed;
- authority/safety regression: 51 passed;
- remote parity: 0 0.
