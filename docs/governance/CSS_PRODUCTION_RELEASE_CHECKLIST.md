# CSS Production Release Checklist

## Governance Validation
- [ ] Operational Risk Register updated and reviewed.
- [ ] User Risk Disclosure and Limitation of Liability policies are current.
- [ ] Production Readiness Certification Report signed off.

## Test Validation
- [ ] 100% pass rate on all unit, integration, and UI tests (`pytest tests/`).
- [ ] Continuous reconciliation tests pass in staging.
- [ ] Margin engine and kill switch fail-safes verified via automated harnesses.

## Certification Validation
- [ ] Authority, Runtime & Governance Ownership map is accurate.
- [ ] Dashboard read-only constraints verified.
- [ ] No regression in anti-bleed cost-aware trade guard implementations.

## Deployment Approval Requirements
- [ ] Release branch locked and peer-reviewed.
- [ ] Deployment authorized by Operations Manager and Lead Engineer.
- [ ] Explicit verification that no live trading overrides exist in environment variables.

## Rollback Readiness Checks
- [ ] Rollback target commit identified and validated in staging.
- [ ] Database backup taken immediately prior to deployment.
- [ ] On-call engineers are monitoring telemetry.
