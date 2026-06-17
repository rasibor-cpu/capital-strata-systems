# CSS Rollback and Recovery Standard

## Rollback Triggers
A production rollback must be initiated if any of the following occur within 2 hours of deployment:
* Broker connection instability (increased timeouts/errors).
* Critical feature degradation (e.g., dashboard unable to render portfolio).
* Unintended order generation or logic bugs detected in dry-run mode.
* Alerts from the continuous reconciliation engine indicating ledger drift.

## Rollback Procedure
1. **Engage Kill Switch:** Immediately halt all trade execution capability.
2. **Execute Revert:** Trigger the CI/CD pipeline to deploy the designated previous stable commit.
3. **Verify Restoration:** Confirm system starts correctly and connects to broker.
4. **Reconcile:** Run `continuous_reconciliation.py` to ensure no orphaned orders exist.
5. **Resume:** Disengage kill switch only after full verification.

## Recovery Verification
* After rollback, the designated on-call engineer must manually verify core system flows using read-only dashboard interfaces.
* Run a health snapshot from the intelligence engine.

## Post-Recovery Validation
* Confirm telemetry reflects standard operating baselines.
* Update the incident log with the rollback reason.
* Conduct a PIR (Post-Incident Review) to determine the root cause of the deployment failure.
