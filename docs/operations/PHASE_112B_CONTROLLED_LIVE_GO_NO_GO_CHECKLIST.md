# Phase 112B: Controlled Live Go/No-Go Checklist

## 1. Launch Objective
Safely transition Capital Strata Systems (CSS) from a strictly simulated execution environment into a controlled, micro-live production state, enforcing all verified governance, risk, and broker guardrails.

## 2. Preconditions
- **Branch Status:** `css-evening-consolidation-2026-06-09` must be the active deployment branch.
- **Test Status:** 100% of integration and unit tests must pass (currently 387/387).
- **Governance Status:** AI Governance, RBAC, and Legal Acceptance controls must be active and enforcing fail-closed constraints.
- **Certification Status:** `PHASE_112A_FINAL_PRODUCTION_CERTIFICATION_READINESS_REPORT` must reflect a "CERTIFIED FOR CONTROLLED LIVE OPERATION" status.
- **Broker Status:** Live credentials must be isolated and loaded exclusively under `LIVE` broker modes.
- **Operational Status:** All operational runbooks (Startup, Shutdown, Recovery, Incident) must be documented and accessible to the operator.

## 3. Go / No-Go Criteria
- **PASS Criteria:** All 387 test assertions succeed. No critical or high-severity vulnerabilities are present in the AI Governance sweep. Broker environments respond to initialization checks without emitting raw credentials.
- **FAIL Criteria (NO-GO if any are true):**
  - Any single pytest failure.
  - Absence of OANDA/Coinbase explicit `ENABLE_LIVE_ORDERS` flags.
  - Active `SIMULATED` capital labels detected in the `LIVE` capital pool.
  - Unapproved or pending operator session tokens.

## 4. Launch-Day Checklist
- [ ] **Environment Validation:** Verify `.env.live` contains correct keys, strictly segregated from `.env.paper`.
- [ ] **Broker Validation:** Confirm API connectivity to the live broker endpoints in dry-run mode.
- [ ] **Risk Validation:** Ensure `AntiBleedGuard` and `MarginTradeGate` snapshots are pre-loaded and reading non-stale data.
- [ ] **Dashboard Validation:** Start `css_live_dashboard.py` and verify metrics bind to real-time feeds without throwing unhandled exceptions.
- [ ] **Logging Validation:** Confirm audit trails write to persistent storage and contain properly `REDACTED` secrets.

## 5. First Controlled Live Session Procedure
1. **Startup Sequence:** Execute `CSS_STARTUP_RUNBOOK.md` using the strictly controlled `python -m engine.engine_loop --mode live --micro-limits` flags.
2. **Monitoring Sequence:** Maintain constant visual contact with the `css_live_dashboard.py` HUD. Monitor the event router for `SEVERITY_HIGH` and `SEVERITY_CRITICAL` emissions.
3. **Escalation Path:** If unhandled exceptions surface, the operator must immediately trigger the standard incident response path.
4. **Stop Conditions:** The session must be gracefully terminated if any risk thresholds exceed 50% of their catastrophic ceilings (e.g., Margin limit warning, rapid drawdown).

## 6. Emergency Abort Conditions
Execute `CSS_EMERGENCY_SHUTDOWN_RUNBOOK.md` immediately if any of the following occur:
- **Execution Anomalies:** A position size exceeds the Micro-Live limits, or a trade fires without Unified Gate trace evidence.
- **Broker Anomalies:** API returns HTTP 401/403 despite active session, or latency exceeds 5000ms consistently.
- **Data Anomalies:** Price feeds stale for > 15 seconds.
- **Governance Anomalies:** RBAC drops the operator role mid-session, or a shadow process attempts execution.

## 7. Post-Session Review
- **Evidence Collection:** Aggregate the `audit.log`, trade ledger, and `TradeDecisionOrchestrator` snapshots.
- **Trade Review:** Reconcile CSS internal ledger with the external broker statement.
- **Risk Review:** Evaluate how close the system came to triggering `AntiBleedGuard` or margin stops.
- **Incident Review:** File post-mortems for any WARNING or ERROR log entries.

## 8. Final Recommendation
**GO**

*Justification:* The codebase demonstrates mathematically proven boundaries between Paper and Live modes. The test suite is universally green, and all governance, risk, and operational guardrails are heavily documented and verified as fail-closed. 
