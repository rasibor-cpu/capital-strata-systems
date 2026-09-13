# CSS Owner Standing Authorization — 2026-09-13

Owner authorization:

> Authorize autonomous completion of CSS, including all repository work, CI/CD, testing, safe architecture and UX changes, TMJ/AI review corrections, release-candidate preparation, and promotion to the certified release branch once all acceptance gates pass. Deployment to connected staging/test environments is also authorized. Real trading, money movement, fee collection, and production live execution remain prohibited unless separately approved.

## Scope granted
- repository work and safe refactoring
- CI/CD and automated validation
- testing and regression closure
- safe architecture changes
- website and mobile UX changes
- TMJ/AI review remediation
- release-candidate preparation
- promotion to certified release branch after acceptance gates pass
- deployment to connected staging/test environments

## Explicitly prohibited without separate authorization
- real trading
- broker order execution
- broker execution arming
- money movement
- deposits/withdrawals/transfers
- client-fund deduction
- fee collection
- production live execution

## Standing safety invariants
- execution_allowed = false
- live_trading_blocked = true
- broker_execution_armed = false
- advisory_only = true

This authorization is intended to minimize owner intervention for routine, reversible, and fully testable engineering work while preserving explicit approval gates for live financial authority.
