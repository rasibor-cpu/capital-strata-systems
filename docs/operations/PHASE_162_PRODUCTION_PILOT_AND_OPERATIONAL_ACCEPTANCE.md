# CSS Phase 162 — Production Pilot & Operational Acceptance

This document details the Production Pilot Framework, Operational Acceptance Testing metrics, and Go/No-Go Engine specifications for the controlled live pilot.

---

## 1. Production Pilot Framework

The Pilot Framework (`ProductionPilotFramework`) restricts live operations to narrow boundaries:
* **Max Capital Allocation:** $1,000 USD limit.
* **Target Pilot Duration:** 24 Hours.
* **Asset Classes:** Strictly limited to FX and CRYPTO.
* **Drawdown Limit:** 2.0% maximum ($20 USD loss threshold). Exceeding this triggers an automatic rollback.
* **Max Connection Drops:** 3 drops allowed before forcing a rollback.

### Approval workflow state transitions:
```
INACTIVE (Requires Operator, Risk Committee, and Deployment Approvals)
  ↓
RUNNING (Active validation checks and connection monitoring)
  ↓
COMPLETED / ROLLED_BACK (Post-pilot summary generated)
```

---

## 2. Operational Acceptance Testing

The Acceptance Framework (`OperationalAcceptanceFramework`) compiles acceptance metrics across eight vectors:
1. **Runtime Stability:** Validates supervisor restart count is under limit (<= 10 restarts).
2. **Broker Connectivity:** Validates OANDA and Coinbase are active and reporting green health.
3. **Portfolio Integrity:** Confirms concentration scores and allocations are available.
4. **Dashboard Integrity:** Verifies state bridge instances are online.
5. **Reporting Integrity:** Verifies historical manifest files are uncorrupted.
6. **Audit Integrity:** Validates audit logs are parsed.
7. **Validation Integrity:** Verifies continuous validation logs are passed.
8. **Readiness Integrity:** Verifies the canonical readiness framework score.

---

## 3. Long Duration Stability (Endurance Validation)

Evaluates platform robustness over extended operational cycles:
* **Memory Growth Boundary:** Process memory leak threshold (< 250MB growth).
* **Connection Flapping Fatigue:** Rollback triggered if adapter reconnects exceed 15 times.
* **Supervisor Recovery Fatigue:** Rollback triggered if recovery limit is exceeded (> 5 times).

---

## 4. Production Go/No-Go Decision Engine

The engine (`ProductionGoNoGoEngine`) aggregates the outputs of three frameworks:
* **Canonical Readiness Framework:** Score >= 90.0% required for GO.
* **Operational Acceptance Framework:** Must be PASS.
* **Production Governance Framework:** Acknowledger, authorization, and approvals must be present.

Returns a single final decision: **GO**, **CONDITIONAL GO**, or **NO GO** with descriptive reasoning.
