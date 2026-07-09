# RC1 Release Checklist

This checklist tracks mandatory verification steps required before staging deployments.

---

## Staging Deployment Readiness

### 1. Code Base & Checks
- [ ] No compilation errors or warnings.
- [ ] Pytest test suites run successfully (51+ cases green).
- [ ] All previous regression milestones (157A-C, 158A, 159A-C) pass.

### 2. Safety Gate Constraints
- [ ] Verify `advisory_only` is hardcoded to `True`.
- [ ] Verify `execution_allowed` is hardcoded to `False`.
- [ ] Verify `live_trading_blocked` is set to `True`.
- [ ] Verify `broker_execution_armed` is set to `False`.

### 3. Subsystem Health Checks
- [ ] Validate runtime supervisor process restarts cleanly.
- [ ] Check sandbox OANDA and Coinbase connectivity logs.
- [ ] Execute `RC1PlatformCertifier` audit report and confirm a final status of **PASS**.

---

## Release Staging Gate Sign-off

- **Target Staging Environment**: Read-only Pilot Staging
- **Sign-off Date**: ____________________
- **Framework Status**: [ PASS / PASS WITH WARNINGS / FAIL ]
- **Approved By**: ____________________
