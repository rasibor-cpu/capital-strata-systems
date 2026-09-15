# CSS Release Candidate — Full-Test Readiness

Target branch: css-v1-completion-2026-09-13

Engineering objective: COMPLETE CSS SOFTWARE AND TEST INFRASTRUCTURE TO THE
POINT WHERE A CLEAN RELEASE CANDIDATE CAN ENTER FULL SYSTEM / UAT TESTING.

## Required technical state

- Full regression: must pass.
- Governance validation: must pass.
- Commercialization UAT suite: must pass.
- Integrated full-test readiness runner: must pass.
- Sandbox payment simulation: must pass and be idempotent.
- Sandbox notification simulation: must pass and be idempotent.
- Mandatory UAT matrix: complete in the isolated full-test fixture.
- Synthetic launch dossier: complete in the isolated full-test fixture.
- Production-commercial readiness: must remain false in the isolated fixture.
- Broker/trading execution authority: must remain false.
- External money movement: must remain false.

## Definition of ready for full testing

CSS is READY FOR FULL TESTING when all four CI gates above pass on the same
release-candidate SHA and the integrated runner reports
ready_for_full_testing=true.

This status means the software is ready to be exercised end-to-end in a
controlled test environment. It does not mean CSS is legally or operationally
approved for production launch.
