# CSS Disaster Recovery Standard

## Recovery Objectives
* **Recovery Time Objective (RTO):** 15 minutes to restore core trading capability; 1 hour for full dashboard restoration.
* **Recovery Point Objective (RPO):** Near zero data loss for canonical PnL and trade events. Maximum acceptable data loss is 1 minute of non-critical telemetry.

## Recovery Priorities
1. **Priority 1:** Broker connection stabilization and portfolio liquidation capabilities.
2. **Priority 2:** Canonical database restoration (trade ledger, PnL snapshot).
3. **Priority 3:** Intelligence and telemetry pipelines.
4. **Priority 4:** Read-only dashboard interfaces.

## Backup Expectations
* Continuous replication of the production database to a warm standby.
* Daily encrypted off-site backups of all operational ledgers.
* Codebase and infrastructure configuration backed up via git version control and IaC (Infrastructure as Code) templates.

## Restoration Procedure
1. Declare Disaster / SEV1.
2. Engage Kill Switch to prevent rogue operations.
3. Failover database to warm standby.
4. Re-deploy stateless application containers to healthy availability zones.
5. Restore canonical database access.

## Verification Procedure
* **Pre-Flight Check:** Run automated readiness verification tests against the restored environment.
* **Reconciliation:** Execute `continuous_reconciliation.py` to ensure local state matches the broker's truth.
* **Approval:** Operations Manager must explicitly lift the kill switch post-verification.
