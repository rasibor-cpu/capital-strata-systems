# CSS Version 1 Engineering Completion Checklist

## Engineering Complete

- [x] Full pytest collection is required for certification.
- [x] Dashboard tests are part of regression certification.
- [x] Runtime tests are part of regression certification.
- [x] Frontend contract tests are part of regression certification.
- [x] Launcher tests are part of regression certification.
- [x] Mobile dashboard tests are part of regression certification.
- [x] Adaptive intelligence tests are part of regression certification.
- [x] Portfolio tests are part of regression certification.
- [x] Governance tests are part of regression certification.
- [x] Non-live broker integration tests are part of regression certification.
- [x] Reporting tests are part of regression certification.

## Operational Modes

- [x] SAFE mode remains governed.
- [x] CONSERVATIVE mode remains governed.
- [x] BALANCED mode remains governed.
- [x] AGGRESSIVE mode remains governed.
- [x] EXPANSION mode remains governed.
- [x] PAPER mode may simulate execution under paper controls.
- [x] PRACTICE mode may simulate execution under practice controls.
- [x] LIVE mode remains fail-closed unless all live controls authorize execution.

## Dashboards

- [x] Session Command Centre is dashboard-visible.
- [x] Trade Summary is dashboard-visible.
- [x] Portfolio, runtime, alerts, broker, margin, risk, opportunities, adaptive intelligence, reports, and executive summary surfaces remain dashboard-visible.
- [x] Canonical data is preferred where available.
- [x] Missing canonical data is reported as DATA UNAVAILABLE, INSUFFICIENT_HISTORY, or OBSERVATION_ONLY.

## Remaining Non-Engineering Work

The only remaining work before production deployment is:

1. Live broker validation
2. Live micro-pilot broker validation and operator rehearsal
3. Production operational certification

## Phase 151 Audit Integrity

- [x] Phase 150 engineering completion remains implementation-complete.
- [x] Phase 151 verifies independent audit findings before live broker validation.
- [x] AntiBleedGuard development override hardening is certified.
- [x] Live mobile trade gate routing determinism is certified.
- [x] Full-history secret scan runbook is documented for pre-live validation.
- [x] Legacy/archive hygiene recommendations are documented without deleting archive folders.

## Phase 152A Live Micro-Pilot Governor

- [x] Live Micro-Pilot Capital Governor defaults are disabled and fail-closed.
- [x] CAD 20 maximum live test capital and CAD 20 maximum position size are enforced.
- [x] SUPER_USER plus `EXECUTE` confirmation is required for pilot configuration and arming.
- [x] Dashboard, mobile, and launcher surfaces expose read-only pilot status.
- [x] Live broker validation remains separate and is not certified by this checklist.

## Phase 152B Live Readiness Certification

- [x] Live Readiness Certification engine reports PASS/WARNING/FAIL per safety component.
- [x] One canonical GO / GO WITH CONDITIONS / NO GO decision is produced.
- [x] Phase 152A CAD 20 governor safety properties are explicitly verified.
- [x] Certification report exposes warnings, blockers, commit, tag, and timestamp.
- [x] Desktop, mobile, launcher, and API surfaces expose read-only certification status.
- [x] Live broker validation remains a separate operational step.
