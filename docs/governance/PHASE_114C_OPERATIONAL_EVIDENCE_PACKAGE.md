# Phase 114C: Operational Evidence Package

## Objective
Define the absolute evidentiary artifacts that must be extracted from the system during and after operational validation to satisfy certification requirements.

## 1. Startup Evidence
- Exact terminal output capturing the execution of `scripts/css_live_dashboard.py`.
- Final loaded environment namespace dump (redacted secrets) showing `PAPER` target.

## 2. Authentication Evidence
- Audit log excerpt showing canonical entry point `dashboard.auth.css_sign_on` success.
- Captured RBAC token payload mapping the active operator.

## 3. Dashboard Evidence
- Full screen capture or HTML DOM snapshot of the active dashboard after 1 hour of sustained run time.
- JSON dump of `pnl_snapshot` to verify alignment with displayed metrics.

## 4. Trade Creation Evidence
- `GovernanceDecisionRecord` JSON showing approval rationale for a given trade.
- Expected value, cost calculation, and margin assessment vectors.

## 5. Trade Management Evidence
- Tick logs confirming the evaluation of rolling returns and correlation constraints during the holding period.
- System memory and CPU utilization logs to prove absence of resource exhaustion.

## 6. Trade Exit Evidence
- The discrete event payload triggering the exit mechanism (e.g., stop loss breached, take profit hit, risk governor panic).
- Reconciliation of finalized `realized_pnl` versus the expected calculated outcome.

## 7. Risk Gate Evidence
- Log demonstrating a blocked trade due to `AntiBleedGuard` or margin caps (can be organically observed or intentionally stressed).
- `ExecutionGate` drop reasons clearly serialized.

## 8. Shutdown Evidence
- Clean graceful shutdown logs.
- Proof of final state-save sequence completion without `IOError` or corruption.
