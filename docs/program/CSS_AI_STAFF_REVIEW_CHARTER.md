# CSS AI Staff Review Charter

## Purpose
Independent recurring review of the active CSS completion branch to identify critical omissions, unsafe coupling, hidden regressions, architecture drift, and improvements that materially increase acceptance or live-test readiness.

## Mandatory review dimensions
- broker/auth/read-only safety
- execution and money-movement isolation
- commercialization attribution and fee-entitlement separation
- Decimal/UTC/idempotency correctness
- persistence/restart/reconciliation integrity
- website/mobile contract parity
- security/secrets/privacy
- observability and Mission Control truth
- failure/recovery/rollback
- simulator/intelligence validity
- test coverage and negative tests
- release/certification completeness
- legal/operational dependency gaps

## Severity
P0 blocker: unsafe, incorrect, security-critical, or invalidates certification.
P1 required: material completeness/reliability gap.
P2 improvement: high-value but non-blocking.
P3 polish: optional refinement.

## Review behavior
Reviews must be evidence-based, name affected files/tests, propose the smallest safe corrective action, and never infer live authority from readiness.
