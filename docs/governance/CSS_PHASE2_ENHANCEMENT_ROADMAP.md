# CSS Phase 2 Enhancement Roadmap

The following GitHub issues have been explicitly deferred to Phase 2, as they represent enhancements, advanced functionality, or expansions beyond the core Equities Phase 1 mandate.

## Enhancements

**Issue #9: Need "Print from any screen" review capability**
* **Category:** UX / Reporting
* **Priority:** Medium
* **Rationale:** Ad-hoc printing/export is a reporting enhancement for auditors but is not a blocker for live autonomous system execution.

**Issue #21: Mobile App: Allow manual override of automated orders**
* **Category:** Mobile / Execution
* **Priority:** Low
* **Rationale:** Manual override capabilities introduce significant compliance edge cases. Phase 1 relies strictly on the global kill switch for manual intervention.

**Issue #24: Options Profitability Phase 2**
* **Category:** Instrument / Pricing
* **Priority:** High
* **Rationale:** Phase 1 explicitly covers Equities and Cash. Options pricing, greeks, and margin impacts require their own dedicated cycle.

**Issue #25: PnL Engine Integration (Non-Regression Controlled Rollout)**
* **Category:** Architecture
* **Priority:** Low (Duplicate/Superseded)
* **Rationale:** PnL Engine visibility was fully satisfied and deployed under Issue #22. This ticket is effectively closed but kept for Phase 2 reconciliation if needed.

**Issue #27: CSS Institutional Intelligence Layer — Macro Event Awareness & Adaptive Risk Engine**
* **Category:** Intelligence / AI
* **Priority:** High
* **Rationale:** Macro event integration represents advanced AI risk adjustment. Phase 1 relies on strict static/dynamic technical boundaries.

**Issue #28: CSS Futures & Options Production Readiness Framework**
* **Category:** Instrument / Governance
* **Priority:** High
* **Rationale:** Requires new broker capabilities, new risk gates, and separate margin requirement calculations distinct from Phase 1 Equities.

**Issue #29: CSS Institutional Deployment Roadmap & Strategic Execution Framework**
* **Category:** Operations
* **Priority:** Medium
* **Rationale:** Forward-looking operational scaling documentation applicable only after the Phase 1 pilot is active.

**Issue #32: CSS Profitability & Edge Validation Framework**
* **Category:** Analytics
* **Priority:** High
* **Rationale:** While execution is live in Phase 1, the formal automated edge verification and strategy analytics platform is a distinct intelligence layer delivery.

**Issue #36: Implement Portfolio-Level Stress Testing Simulation Engine**
* **Category:** Risk
* **Priority:** Medium
* **Rationale:** Phase 1 uses active real-time risk guards (AntiBleed, Margin). Offline simulated portfolio stress testing is a Phase 2 requirement.
